"""WNBA Step 5T immutable release identity, activation, and rollback readiness.

Step 5T adds release controls around frozen Steps 5R/5S. It does not change
sportsbook collection, model inputs, Monte Carlo, ranking, publication,
archive, scheduler cadence, or locking semantics.

The production sequence is intentionally two phase:
1. deploy an immutable release with WNBA_PRODUCTION_RUNTIME_ENABLED=false;
2. verify deployment/release/storage identity with read-only smoke checks;
3. only then enable the frozen Step-5R production switch.

Rollback is also fail-safe: preserve the persistent volume, disable scheduler
writes first, and redeploy a previously recorded immutable image when one
exists. Step 5T never deletes or rewinds SQLite data.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import hashlib
import json
import os
import re
from typing import Any

import httpx

from sports_api.wnba_deployment_smoke_readiness import (
    DEPLOYMENT_REVISION_ENV,
    PERSISTENT_ROOT_ENV,
    get_deployment_readiness,
    normalize_smoke_base_url,
)
from sports_api.wnba_production_runtime_readiness import ACTIVATION_ENV

MODEL_SOURCE = "Kyre Sports API WNBA Step 5T release + rollback readiness"
MODEL_VERSION = "wnba_step_5t_release_activation_readiness_v1"
SCHEMA_VERSION = "wnba_step_5t_release_activation_readiness_v1"

RELEASE_ID_ENV = "WNBA_RELEASE_ID"
RELEASE_CHANNEL_ENV = "WNBA_RELEASE_CHANNEL"
DEPLOYMENT_IMAGE_REF_ENV = "WNBA_DEPLOYMENT_IMAGE_REF"
PREVIOUS_REVISION_ENV = "WNBA_PREVIOUS_DEPLOYMENT_REVISION"
PREVIOUS_IMAGE_REF_ENV = "WNBA_PREVIOUS_DEPLOYMENT_IMAGE_REF"
INITIAL_RELEASE_ENV = "WNBA_RELEASE_INITIAL_DEPLOYMENT"
RELEASE_CREATED_AT_ENV = "WNBA_RELEASE_CREATED_AT_UTC"

DEFAULT_RELEASE_CHANNEL = "production"
_REVISION_RE = re.compile(r"^[0-9a-f]{40}$")
_IMAGE_REF_RE = re.compile(r"^[^\s@]+@sha256:[0-9a-f]{64}$")
_RELEASE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{2,127}$")


class WNBAReleaseReadinessError(RuntimeError):
    pass


class WNBAReleaseNotReadyError(WNBAReleaseReadinessError):
    pass


class WNBAReleaseVerificationError(WNBAReleaseReadinessError):
    pass


def _environment(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if env is None else env


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _truthy(environment: Mapping[str, str], name: str, default: bool = False) -> bool:
    raw = environment.get(name)
    if raw is None:
        return default
    return str(raw).strip().casefold() not in {"", "0", "false", "no", "off", "disabled"}


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()


def _valid_revision(value: str | None) -> bool:
    return bool(value and _REVISION_RE.fullmatch(value.casefold()))


def _valid_image_ref(value: str | None) -> bool:
    return bool(value and _IMAGE_REF_RE.fullmatch(value.casefold()))


def _valid_release_id(value: str | None) -> bool:
    return bool(value and _RELEASE_ID_RE.fullmatch(value))


def _parse_created_at(value: str | None) -> str | None:
    if not value:
        return None
    text = value[:-1] + "+00:00" if value.endswith(("Z", "z")) else value
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc).isoformat()


def _storage_identity(step5s: Mapping[str, Any]) -> str:
    deployment = step5s.get("deployment") or {}
    runtime_paths = step5s.get("runtime_paths") or {}
    payload = {
        "persistent_volume_root": deployment.get("persistent_volume_root"),
        "runtime_paths": {
            "board_store": runtime_paths.get("board_store"),
            "feed_store": runtime_paths.get("feed_store"),
            "backtest_store": runtime_paths.get("backtest_store"),
            "scheduler_lock_store": runtime_paths.get("scheduler_lock_store"),
        },
    }
    return _hash(payload)


def get_release_readiness(*, env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Return sanitized immutable-release and rollback readiness."""
    environment = _environment(env)
    step5s = get_deployment_readiness(env=environment)
    checks: list[dict[str, Any]] = []
    blockers: list[str] = []

    def add(name: str, passed: bool, detail: str, *, required: bool = True) -> None:
        row = {"name": name, "required": required, "passed": bool(passed), "detail": detail}
        checks.append(row)
        if required and not passed:
            blockers.append(f"{name}: {detail}")

    release_id = _clean(environment.get(RELEASE_ID_ENV))
    channel = (_clean(environment.get(RELEASE_CHANNEL_ENV)) or DEFAULT_RELEASE_CHANNEL).casefold()
    revision = (_clean(environment.get(DEPLOYMENT_REVISION_ENV)) or "").casefold() or None
    image_ref = (_clean(environment.get(DEPLOYMENT_IMAGE_REF_ENV)) or "").casefold() or None
    previous_revision = (_clean(environment.get(PREVIOUS_REVISION_ENV)) or "").casefold() or None
    previous_image_ref = (_clean(environment.get(PREVIOUS_IMAGE_REF_ENV)) or "").casefold() or None
    initial_release = _truthy(environment, INITIAL_RELEASE_ENV, False)
    activation_requested = _truthy(environment, ACTIVATION_ENV, False)
    created_at = _parse_created_at(_clean(environment.get(RELEASE_CREATED_AT_ENV)))

    add(
        "step_5s_deployment_ready",
        step5s.get("deployment_ready") is True,
        "Frozen Step 5S deployment gate is green." if step5s.get("deployment_ready") is True else "Frozen Step 5S deployment gate is not green.",
    )
    add(
        "release_id_valid",
        _valid_release_id(release_id),
        "Release ID is explicit and format-valid." if _valid_release_id(release_id) else f"{RELEASE_ID_ENV} must be 3-128 characters using letters, digits, '.', '_' or '-'.",
    )
    add(
        "production_release_channel",
        channel == DEFAULT_RELEASE_CHANNEL,
        "Production release channel is explicit." if channel == DEFAULT_RELEASE_CHANNEL else f"{RELEASE_CHANNEL_ENV} must be '{DEFAULT_RELEASE_CHANNEL}' for this gate.",
    )
    add(
        "immutable_git_revision",
        _valid_revision(revision),
        "Deployment revision is a full 40-character Git SHA." if _valid_revision(revision) else f"{DEPLOYMENT_REVISION_ENV} must be a full 40-character Git SHA.",
    )
    add(
        "immutable_container_image",
        _valid_image_ref(image_ref),
        "Deployment image is pinned by sha256 digest." if _valid_image_ref(image_ref) else f"{DEPLOYMENT_IMAGE_REF_ENV} must use immutable name@sha256:<64-hex> form.",
    )

    step5s_revision = ((step5s.get("deployment") or {}).get("revision") or "").casefold() or None
    add(
        "step_5s_revision_matches_release",
        bool(revision and step5s_revision == revision),
        "Step 5S deployment revision matches the Step 5T release manifest." if revision and step5s_revision == revision else "Step 5S deployment revision does not match the Step 5T release revision.",
    )

    previous_required = not initial_release
    previous_revision_valid = _valid_revision(previous_revision)
    previous_image_valid = _valid_image_ref(previous_image_ref)
    add(
        "rollback_revision_recorded",
        previous_revision_valid or initial_release,
        (
            "Previous full Git revision is recorded for rollback."
            if previous_revision_valid
            else "Initial deployment explicitly selected; no previous revision exists yet."
            if initial_release
            else f"{PREVIOUS_REVISION_ENV} must record the previous full Git SHA."
        ),
        required=previous_required,
    )
    add(
        "rollback_image_recorded",
        previous_image_valid or initial_release,
        (
            "Previous immutable image digest is recorded for rollback."
            if previous_image_valid
            else "Initial deployment explicitly selected; emergency rollback is scheduler disablement."
            if initial_release
            else f"{PREVIOUS_IMAGE_REF_ENV} must record the previous immutable image."
        ),
        required=previous_required,
    )

    distinct_revision = initial_release or bool(revision and previous_revision and revision != previous_revision)
    distinct_image = initial_release or bool(image_ref and previous_image_ref and image_ref != previous_image_ref)
    add(
        "rollback_target_differs_from_current_revision",
        distinct_revision,
        "Rollback revision differs from current release." if distinct_revision else "Rollback revision must differ from the current revision.",
        required=previous_required,
    )
    add(
        "rollback_target_differs_from_current_image",
        distinct_image,
        "Rollback image differs from current release." if distinct_image else "Rollback image must differ from the current image.",
        required=previous_required,
    )

    persistent_root = ((step5s.get("deployment") or {}).get("persistent_volume_root"))
    add(
        "persistent_volume_identity_present",
        bool(persistent_root),
        "Persistent volume identity is present and will be reused across release/rollback." if persistent_root else f"{PERSISTENT_ROOT_ENV} is not available from Step 5S.",
    )

    if _clean(environment.get(RELEASE_CREATED_AT_ENV)) is not None:
        add(
            "release_created_at_valid",
            created_at is not None,
            "Optional release creation timestamp is a timezone-aware ISO-8601 value." if created_at else f"{RELEASE_CREATED_AT_ENV} is not a valid timezone-aware ISO-8601 timestamp.",
        )

    release_ready = not blockers
    step5r = step5s.get("step_5r") or {}
    preflight_ready = step5r.get("preflight_ready") is True
    live_write_ready = step5s.get("live_write_ready") is True
    safe_to_activate = release_ready and preflight_ready and not activation_requested
    active_release_healthy = release_ready and activation_requested and live_write_ready
    rollback_ready = release_ready and (initial_release or (previous_revision_valid and previous_image_valid))

    if activation_requested:
        phase = "active" if active_release_healthy else "activation_blocked"
    else:
        phase = "pre_activation_ready" if safe_to_activate else "pre_activation_blocked"

    storage_identity = _storage_identity(step5s)
    manifest_payload = {
        "release_id": release_id,
        "channel": channel,
        "revision": revision,
        "image_ref": image_ref,
        "initial_release": initial_release,
        "previous_revision": previous_revision,
        "previous_image_ref": previous_image_ref,
        "persistent_volume_root": persistent_root,
        "storage_identity_sha256": storage_identity,
        "step5s_configuration_fingerprint_sha256": step5s.get("configuration_fingerprint_sha256"),
    }
    manifest_fingerprint = _hash(manifest_payload)

    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_release_activation_and_rollback_readiness",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _iso_now(),
        "release_ready": release_ready,
        "safe_to_activate": safe_to_activate,
        "active_release_healthy": active_release_healthy,
        "rollback_ready": rollback_ready,
        "phase": phase,
        "activation_requested": activation_requested,
        "release": {
            "release_id": release_id,
            "channel": channel,
            "revision": revision,
            "image_ref": image_ref,
            "created_at_utc": created_at,
            "initial_deployment": initial_release,
            "manifest_fingerprint_sha256": manifest_fingerprint,
        },
        "rollback_target": {
            "mode": "disable_runtime_only" if initial_release else "redeploy_previous_immutable_image",
            "revision": previous_revision,
            "image_ref": previous_image_ref,
            "persistent_volume_root": persistent_root,
            "preserve_persistent_volume": True,
            "delete_database_files": False,
            "reverse_schema_migrations": False,
        },
        "storage_identity_sha256": storage_identity,
        "step_5s": {
            "deployment_ready": step5s.get("deployment_ready") is True,
            "live_write_ready": live_write_ready,
            "configuration_fingerprint_sha256": step5s.get("configuration_fingerprint_sha256"),
        },
        "checks": checks,
        "blocking_reasons": blockers,
        "semantics": {
            "two_phase_activation_required": True,
            "deploy_with_runtime_disabled_first": True,
            "read_only_verification_before_activation": True,
            "frozen_step_5r_remains_activation_authority": True,
            "frozen_step_5s_remains_deployment_authority": True,
            "rollback_preserves_persistent_storage": True,
            "rollback_disables_scheduler_before_image_change": True,
            "release_gate_does_not_call_sportsbook": True,
            "release_gate_does_not_run_monte_carlo": True,
        },
    }


def require_release_ready(*, env: Mapping[str, str] | None = None) -> dict[str, Any]:
    report = get_release_readiness(env=env)
    if report.get("release_ready") is not True:
        raise WNBAReleaseNotReadyError("WNBA Step 5T release gate is not ready: " + "; ".join(report.get("blocking_reasons") or []))
    return report


def build_activation_plan(*, env: Mapping[str, str] | None = None, base_url: str | None = None) -> dict[str, Any]:
    report = get_release_readiness(env=env)
    normalized = normalize_smoke_base_url(base_url) if base_url else None
    revision = (report.get("release") or {}).get("revision")
    image_ref = (report.get("release") or {}).get("image_ref")
    steps = [
        {"order": 1, "action": "deploy_immutable_image", "requirement": image_ref, "write_capable": False},
        {"order": 2, "action": "keep_production_runtime_disabled", "requirement": f"{ACTIVATION_ENV}=false", "write_capable": False},
        {"order": 3, "action": "mount_existing_persistent_volume", "requirement": (report.get("rollback_target") or {}).get("persistent_volume_root"), "write_capable": False},
        {"order": 4, "action": "run_step_5s_read_only_smoke", "requirement": normalized, "write_capable": False},
        {"order": 5, "action": "verify_step_5t_release_identity", "requirement": {"revision": revision, "image_ref": image_ref}, "write_capable": False},
        {"order": 6, "action": "enable_frozen_step_5r_runtime_switch", "requirement": f"{ACTIVATION_ENV}=true", "write_capable": True},
        {"order": 7, "action": "require_runtime_health_200", "requirement": "/api/v1/wnba/runtime/health", "write_capable": False},
        {"order": 8, "action": "run_active_read_only_smoke", "requirement": "expect_scheduler_ready=true", "write_capable": False},
        {"order": 9, "action": "verify_current_board_publication", "requirement": "/api/v1/wnba/rankings/player-props/current?require_current=true", "write_capable": False},
        {"order": 10, "action": "restart_once_and_reverify_storage_identity", "requirement": report.get("storage_identity_sha256"), "write_capable": False},
    ]
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_release_activation_plan",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _iso_now(),
        "release_ready": report.get("release_ready") is True,
        "safe_to_activate_now": report.get("safe_to_activate") is True,
        "base_url": normalized,
        "release": report.get("release"),
        "storage_identity_sha256": report.get("storage_identity_sha256"),
        "steps": steps,
        "safety": {
            "steps_before_activation_are_read_only": all(not row["write_capable"] for row in steps[:5]),
            "first_write_capable_step_is_explicit_runtime_activation": True,
            "manual_refresh_endpoint_is_never_required": True,
            "sportsbook_collection_is_not_triggered_by_this_plan_builder": True,
            "monte_carlo_is_not_triggered_by_this_plan_builder": True,
        },
    }


def build_rollback_plan(*, env: Mapping[str, str] | None = None) -> dict[str, Any]:
    report = get_release_readiness(env=env)
    target = report.get("rollback_target") or {}
    initial = (report.get("release") or {}).get("initial_deployment") is True
    steps = [
        {"order": 1, "action": "disable_production_runtime", "requirement": f"{ACTIVATION_ENV}=false"},
        {"order": 2, "action": "stop_or_replace_current_replica", "requirement": "single service replica"},
        {"order": 3, "action": "preserve_persistent_volume", "requirement": target.get("persistent_volume_root")},
    ]
    if not initial:
        steps.append({"order": 4, "action": "redeploy_previous_immutable_image", "requirement": target.get("image_ref")})
        steps.append({"order": 5, "action": "verify_previous_revision_identity", "requirement": target.get("revision")})
        next_order = 6
    else:
        steps.append({"order": 4, "action": "hold_runtime_disabled_for_operator_recovery", "requirement": "no previous release exists"})
        next_order = 5
    steps.extend(
        [
            {"order": next_order, "action": "run_read_only_smoke", "requirement": "scheduler may remain disabled"},
            {"order": next_order + 1, "action": "verify_storage_identity_unchanged", "requirement": report.get("storage_identity_sha256")},
            {"order": next_order + 2, "action": "re_enable_runtime_only_after_green_checks", "requirement": "manual operator decision"},
        ]
    )
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_release_rollback_plan",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _iso_now(),
        "rollback_ready": report.get("rollback_ready") is True,
        "current_release": report.get("release"),
        "target": target,
        "steps": steps,
        "invariants": {
            "persistent_volume_is_never_deleted": True,
            "sqlite_files_are_never_recreated_as_part_of_rollback": True,
            "schema_is_never_migrated_backward": True,
            "scheduler_is_disabled_before_image_replacement": True,
            "rollback_plan_builder_performs_no_network_calls": True,
        },
    }


def _safe_json(response: Any) -> Any:
    try:
        return response.json()
    except Exception:
        return None


def run_release_verification(
    base_url: str,
    *,
    expected_revision: str,
    expected_image_ref: str,
    expected_release_id: str | None = None,
    expected_storage_identity: str | None = None,
    timeout_seconds: float = 10.0,
    client: Any | None = None,
) -> dict[str, Any]:
    """Read-only verification that the deployed server is the intended release."""
    if not _valid_revision(expected_revision.casefold()):
        raise WNBAReleaseVerificationError("expected_revision must be a full 40-character Git SHA.")
    if not _valid_image_ref(expected_image_ref.casefold()):
        raise WNBAReleaseVerificationError("expected_image_ref must use immutable name@sha256:<64-hex> form.")
    if expected_release_id is not None and not _valid_release_id(expected_release_id):
        raise WNBAReleaseVerificationError("expected_release_id is invalid.")
    if expected_storage_identity is not None and not re.fullmatch(r"[0-9a-f]{64}", expected_storage_identity.casefold()):
        raise WNBAReleaseVerificationError("expected_storage_identity must be a 64-character SHA256 hex value.")
    if timeout_seconds <= 0 or timeout_seconds > 60:
        raise ValueError("timeout_seconds must be greater than 0 and no more than 60.")

    normalized = normalize_smoke_base_url(base_url)
    owned_client = client is None
    http_client = client or httpx.Client(timeout=timeout_seconds, follow_redirects=False)
    checks: list[dict[str, Any]] = []
    try:
        for name, path in (
            ("service_health", "/health"),
            ("step_5s_deployment", "/api/v1/wnba/runtime/deployment"),
            ("step_5t_release", "/api/v1/wnba/runtime/release"),
        ):
            try:
                response = http_client.get(normalized + path, timeout=timeout_seconds)
                body = _safe_json(response)
                passed = int(response.status_code) == 200 and isinstance(body, dict)
                detail = f"HTTP {int(response.status_code)}"
            except Exception as exc:
                response = None
                body = None
                passed = False
                detail = f"{type(exc).__name__}: {exc}"
            checks.append({"name": name, "method": "GET", "path": path, "passed": passed, "detail": detail, "body": body})
    finally:
        if owned_client:
            http_client.close()

    release_row = next((row for row in checks if row["name"] == "step_5t_release"), {})
    body = release_row.get("body") if isinstance(release_row.get("body"), dict) else {}
    release = body.get("release") if isinstance(body, dict) else {}
    if not isinstance(release, dict):
        release = {}

    identity_checks = [
        {"name": "revision_matches", "passed": str(release.get("revision") or "").casefold() == expected_revision.casefold()},
        {"name": "image_ref_matches", "passed": str(release.get("image_ref") or "").casefold() == expected_image_ref.casefold()},
    ]
    if expected_release_id is not None:
        identity_checks.append({"name": "release_id_matches", "passed": release.get("release_id") == expected_release_id})
    if expected_storage_identity is not None:
        identity_checks.append(
            {
                "name": "storage_identity_matches",
                "passed": str(body.get("storage_identity_sha256") or "").casefold() == expected_storage_identity.casefold(),
            }
        )

    passed = all(row.get("passed") is True for row in checks) and all(row["passed"] for row in identity_checks)
    sanitized_checks = [{k: v for k, v in row.items() if k != "body"} for row in checks]
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_release_remote_verification",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _iso_now(),
        "base_url": normalized,
        "passed": passed,
        "checks": sanitized_checks,
        "identity_checks": identity_checks,
        "observed": {
            "release_id": release.get("release_id"),
            "revision": release.get("revision"),
            "image_ref": release.get("image_ref"),
            "storage_identity_sha256": body.get("storage_identity_sha256") if isinstance(body, dict) else None,
            "phase": body.get("phase") if isinstance(body, dict) else None,
        },
        "safety": {
            "read_only": True,
            "all_methods_are_get": True,
            "manual_refresh_endpoint_is_not_called": True,
            "sportsbook_collection_is_not_intentionally_triggered": True,
            "monte_carlo_rebuild_is_not_intentionally_triggered": True,
        },
    }
