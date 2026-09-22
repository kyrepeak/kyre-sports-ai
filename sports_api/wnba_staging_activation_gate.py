"""WNBA Step 5W explicit staging activation gate + first live-cycle verification.

Step 5W is the final fail-closed gate before the frozen Step 5P/5Q scheduler may
contact a sportsbook provider or run Monte Carlo on hosted staging.

The gate has two phases:
1. pre-activation: frozen Step 5V must be fully green and this module emits a
   stable activation checkpoint that intentionally excludes ephemeral Render
   instance IDs and activation-state-dependent fingerprints;
2. activation: the operator must explicitly approve that exact checkpoint,
   record an activation timestamp, and enable the frozen Step 5R runtime. The
   currently deployed release/host/storage identity must still hash to the same
   checkpoint before any scheduler cycle is allowed.

Readiness/checkpoint/verification helpers are network-free. First-live-cycle
verification reads only the durable Step 5P SQLite publication/run evidence.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
import re
from typing import Any

from sports_api.database.wnba_current_board_store import (
    get_latest_publication,
    list_publications,
    list_scheduler_runs,
)
from sports_api.wnba_hosted_staging_readiness import get_hosted_staging_readiness
from sports_api.wnba_production_runtime_readiness import (
    ACTIVATION_ENV,
    get_production_runtime_readiness,
)
from sports_api.wnba_release_publication_handoff import (
    get_release_publication_handoff_readiness,
)

MODEL_SOURCE = "Kyre Sports API WNBA Step 5W explicit staging activation gate"
MODEL_VERSION = "wnba_step_5w_staging_activation_gate_v1"
SCHEMA_VERSION = "wnba_step_5w_staging_activation_gate_v1"

APPROVAL_ENV = "WNBA_STAGING_ACTIVATION_APPROVED"
CHECKPOINT_ENV = "WNBA_STAGING_ACTIVATION_CHECKPOINT_SHA256"
ACTIVATED_AT_ENV = "WNBA_STAGING_ACTIVATED_AT_UTC"

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_ACTIVE_5U_FAILURES = frozenset({"pre_activation_phase_required", "runtime_remains_disabled"})
_ALLOWED_ACTIVE_5V_FAILURES = frozenset({"frozen_step_5u_host_contract_ready", "runtime_remains_disabled"})


class WNBAStagingActivationGateError(RuntimeError):
    pass


class WNBAStagingActivationNotReadyError(WNBAStagingActivationGateError):
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


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value[:-1] + "+00:00" if value.endswith(("Z", "z")) else value
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def _failed_required_checks(report: Mapping[str, Any]) -> set[str]:
    failed: set[str] = set()
    for row in report.get("checks") or []:
        if isinstance(row, Mapping) and row.get("required", True) and row.get("passed") is not True:
            name = _clean(row.get("name"))
            if name:
                failed.add(name)
    return failed


def _checkpoint_payload(
    step5u: Mapping[str, Any],
    step5v: Mapping[str, Any],
) -> dict[str, Any]:
    publication = step5v.get("publication") or {}
    release = step5v.get("release") or {}
    host = step5u.get("host") or {}
    # Deliberately exclude RENDER_INSTANCE_ID / host_identity_sha256 and the
    # Step-5R configuration fingerprint. Render may replace an instance during
    # the environment update, and Step 5R's fingerprint intentionally includes
    # the activation flag. Neither may make the pre-activation checkpoint drift.
    return {
        "checkpoint_version": MODEL_VERSION,
        "release": {
            "release_id": release.get("release_id"),
            "revision": release.get("revision"),
            "image_ref": release.get("image_ref"),
        },
        "publication": {
            "registry": publication.get("registry"),
            "image_repository": publication.get("image_repository"),
            "published_image_ref": publication.get("published_image_ref"),
            "image_digest_sha256": publication.get("image_digest_sha256"),
            "publisher": publication.get("publisher"),
            "source_repository": publication.get("source_repository"),
        },
        "host": {
            "provider": step5u.get("provider"),
            "environment": step5u.get("environment"),
            "external_url": step5u.get("external_url"),
            "service_id": host.get("service_id"),
            "service_name": host.get("service_name"),
            "service_type": host.get("service_type"),
            "repository": host.get("repository"),
            "git_branch": host.get("git_branch"),
            "git_commit": host.get("git_commit"),
        },
        "storage_identity_sha256": step5u.get("storage_identity_sha256"),
    }


def _checkpoint_fields_complete(payload: Mapping[str, Any]) -> bool:
    release = payload.get("release") or {}
    publication = payload.get("publication") or {}
    host = payload.get("host") or {}
    required = [
        release.get("release_id"),
        release.get("revision"),
        release.get("image_ref"),
        publication.get("published_image_ref"),
        publication.get("image_digest_sha256"),
        host.get("provider"),
        host.get("environment"),
        host.get("external_url"),
        host.get("service_id"),
        host.get("service_name"),
        host.get("repository"),
        host.get("git_branch"),
        host.get("git_commit"),
        payload.get("storage_identity_sha256"),
    ]
    return all(_clean(value) for value in required)


def get_staging_activation_gate(*, env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Return the network-free Step 5W pre-activation/activation decision."""
    environment = _environment(env)
    step5r = get_production_runtime_readiness(env=environment)
    step5u = get_hosted_staging_readiness(env=environment)
    step5v = get_release_publication_handoff_readiness(env=environment)

    activation_requested = _truthy(environment, ACTIVATION_ENV, False)
    approval_requested = _truthy(environment, APPROVAL_ENV, False)
    approved_checkpoint = (_clean(environment.get(CHECKPOINT_ENV)) or "").casefold() or None
    activated_at_raw = _clean(environment.get(ACTIVATED_AT_ENV))
    activated_at = _parse_timestamp(activated_at_raw)

    payload = _checkpoint_payload(step5u, step5v)
    checkpoint = _hash(payload)
    fields_complete = _checkpoint_fields_complete(payload)
    current_5u_failures = _failed_required_checks(step5u)
    current_5v_failures = _failed_required_checks(step5v)
    active_5u_structural_ready = current_5u_failures.issubset(_ALLOWED_ACTIVE_5U_FAILURES)
    active_5v_structural_ready = current_5v_failures.issubset(_ALLOWED_ACTIVE_5V_FAILURES)

    checks: list[dict[str, Any]] = []
    blockers: list[str] = []

    def add(name: str, passed: bool, detail: str, *, required: bool = True) -> None:
        checks.append({"name": name, "required": required, "passed": bool(passed), "detail": detail})
        if required and not passed:
            blockers.append(f"{name}: {detail}")

    add(
        "stable_checkpoint_fields_complete",
        fields_complete,
        "Stable release/host/storage checkpoint fields are complete." if fields_complete else "Stable activation identity fields are incomplete.",
    )

    if not activation_requested:
        add(
            "frozen_step_5v_handoff_ready",
            step5v.get("handoff_ready") is True,
            "Frozen Step 5V immutable handoff is green." if step5v.get("handoff_ready") is True else "Frozen Step 5V immutable handoff is not green.",
        )
        add(
            "runtime_still_disabled",
            True,
            "Production runtime remains disabled while the activation checkpoint is frozen.",
        )
        phase = "pre_activation_checkpoint_ready" if not blockers else "pre_activation_blocked"
        checkpoint_ready = not blockers
        live_cycle_allowed = False
    else:
        add(
            "explicit_activation_approval",
            approval_requested,
            f"{APPROVAL_ENV}=true is present." if approval_requested else f"{APPROVAL_ENV}=true is required before the first live cycle.",
        )
        add(
            "approved_checkpoint_is_sha256",
            bool(approved_checkpoint and _SHA256_RE.fullmatch(approved_checkpoint)),
            "Approved activation checkpoint is a 64-character SHA-256." if approved_checkpoint and _SHA256_RE.fullmatch(approved_checkpoint) else f"{CHECKPOINT_ENV} must be the exact 64-character pre-activation checkpoint.",
        )
        add(
            "approved_checkpoint_matches_current_identity",
            bool(approved_checkpoint and approved_checkpoint == checkpoint),
            "Approved checkpoint exactly matches the currently deployed immutable release/host/storage identity." if approved_checkpoint == checkpoint else "Approved checkpoint does not match the currently deployed stable activation identity.",
        )
        add(
            "activation_timestamp_valid",
            activated_at is not None,
            "Activation timestamp is timezone-aware ISO-8601." if activated_at is not None else f"{ACTIVATED_AT_ENV} must be a timezone-aware ISO-8601 timestamp.",
        )
        future_ok = activated_at is not None and activated_at <= datetime.now(timezone.utc) + timedelta(minutes=5)
        add(
            "activation_timestamp_not_materially_future",
            future_ok,
            "Activation timestamp is not materially in the future." if future_ok else "Activation timestamp may not be more than five minutes in the future.",
        )
        add(
            "frozen_step_5r_scheduler_allowed",
            step5r.get("scheduler_allowed") is True,
            "Frozen Step 5R production runtime preflight is green and activated." if step5r.get("scheduler_allowed") is True else "Frozen Step 5R scheduler gate is not ready.",
        )
        add(
            "step_5u_structural_identity_still_green",
            active_5u_structural_ready,
            "Step 5U host identity remains structurally green; only expected pre-activation-only checks may fail after activation." if active_5u_structural_ready else "Step 5U has structural failures beyond the expected activation-phase transition.",
        )
        add(
            "step_5v_structural_identity_still_green",
            active_5v_structural_ready,
            "Step 5V release/publication identity remains structurally green after activation." if active_5v_structural_ready else "Step 5V has immutable handoff failures beyond the expected activation-phase transition.",
        )
        phase = "active_gate_ready" if not blockers else "activation_blocked"
        checkpoint_ready = False
        live_cycle_allowed = not blockers

    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_staging_activation_gate",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _iso_now(),
        "phase": phase,
        "activation_requested": activation_requested,
        "explicit_approval": approval_requested,
        "checkpoint_ready": checkpoint_ready,
        "live_cycle_allowed": live_cycle_allowed,
        "activation_checkpoint_sha256": checkpoint,
        "approved_checkpoint_sha256": approved_checkpoint,
        "activated_at_utc": activated_at.isoformat() if activated_at else None,
        "checkpoint_payload": payload,
        "checks": checks,
        "blocking_reasons": blockers,
        "expected_active_only_step_5u_failures": sorted(_ALLOWED_ACTIVE_5U_FAILURES),
        "expected_active_only_step_5v_failures": sorted(_ALLOWED_ACTIVE_5V_FAILURES),
        "step_5r": {
            "preflight_ready": step5r.get("preflight_ready"),
            "scheduler_allowed": step5r.get("scheduler_allowed"),
            "configuration_fingerprint_sha256": step5r.get("configuration_fingerprint_sha256"),
        },
        "step_5u": {
            "host_contract_ready": step5u.get("host_contract_ready"),
            "structural_failures": sorted(current_5u_failures),
            "storage_identity_sha256": step5u.get("storage_identity_sha256"),
        },
        "step_5v": {
            "handoff_ready": step5v.get("handoff_ready"),
            "structural_failures": sorted(current_5v_failures),
            "published_image_ref": (step5v.get("publication") or {}).get("published_image_ref"),
        },
        "semantics": {
            "fail_closed": True,
            "checkpoint_excludes_ephemeral_render_instance_id": True,
            "checkpoint_excludes_activation_state_dependent_fingerprints": True,
            "explicit_operator_approval_required": True,
            "approved_checkpoint_must_match_current_deployment": True,
            "frozen_step_5r_remains_runtime_preflight_authority": True,
            "frozen_step_5q_remains_cycle_lock_authority": True,
            "readiness_makes_no_network_requests": True,
            "readiness_does_not_call_sportsbook": True,
            "readiness_does_not_run_monte_carlo": True,
        },
    }


def require_staging_activation_ready(*, env: Mapping[str, str] | None = None) -> dict[str, Any]:
    report = get_staging_activation_gate(env=env)
    if report.get("live_cycle_allowed") is not True:
        raise WNBAStagingActivationNotReadyError(
            "WNBA Step 5W staging activation gate is not ready: " + "; ".join(report.get("blocking_reasons") or [])
        )
    return report


def build_staging_activation_plan(*, env: Mapping[str, str] | None = None) -> dict[str, Any]:
    report = get_staging_activation_gate(env=env)
    checkpoint = report.get("activation_checkpoint_sha256")
    steps = [
        {"order": 1, "action": "freeze_preactivation_checkpoint", "requirement": checkpoint},
        {"order": 2, "action": "set_explicit_activation_approval", "requirement": f"{APPROVAL_ENV}=true"},
        {"order": 3, "action": "pin_activation_checkpoint", "requirement": f"{CHECKPOINT_ENV}={checkpoint or '<checkpoint>'}"},
        {"order": 4, "action": "record_activation_timestamp", "requirement": f"{ACTIVATED_AT_ENV}=<timezone-aware ISO-8601>"},
        {"order": 5, "action": "enable_frozen_step_5r_runtime", "requirement": f"{ACTIVATION_ENV}=true"},
        {"order": 6, "action": "redeploy_same_immutable_image_and_persistent_disk", "requirement": "release/image/storage identity must remain unchanged"},
        {"order": 7, "action": "verify_step_5w_gate", "requirement": "/api/v1/wnba/runtime/activation-gate -> live_cycle_allowed=true"},
        {"order": 8, "action": "verify_runtime_health", "requirement": "/api/v1/wnba/runtime/health -> 200"},
        {"order": 9, "action": "allow_background_scheduler_first_live_cycle", "requirement": "no manual refresh required"},
        {"order": 10, "action": "verify_durable_first_live_cycle", "requirement": "/api/v1/wnba/runtime/first-live-cycle -> first_live_cycle_verified=true"},
        {"order": 11, "action": "verify_current_board", "requirement": "/api/v1/wnba/rankings/player-props/current?require_current=true -> 200"},
    ]
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_staging_activation_plan",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _iso_now(),
        "phase": report.get("phase"),
        "activation_checkpoint_sha256": checkpoint,
        "step_count": len(steps),
        "steps": steps,
        "safety": {
            "plan_is_read_only": True,
            "manual_refresh_not_required": True,
            "sportsbook_call_occurs_only_after_step_5w_gate": True,
            "monte_carlo_occurs_only_after_step_5w_gate": True,
            "persistent_volume_is_preserved": True,
        },
    }


def get_first_live_cycle_verification(
    *,
    date: str | None = None,
    season: int | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Verify durable evidence of the first post-activation provider/publication cycle."""
    environment = _environment(env)
    gate = get_staging_activation_gate(env=environment)
    activated_at = _parse_timestamp(_clean(environment.get(ACTIVATED_AT_ENV)))
    if gate.get("live_cycle_allowed") is not True or activated_at is None:
        return {
            "source": MODEL_SOURCE,
            "data_type": "wnba_first_live_cycle_verification",
            "schema_version": SCHEMA_VERSION,
            "model_version": MODEL_VERSION,
            "generated_at_utc": _iso_now(),
            "first_live_cycle_verified": False,
            "activation_gate_ready": gate.get("live_cycle_allowed") is True,
            "activated_at_utc": activated_at.isoformat() if activated_at else None,
            "provider_cycle": None,
            "publication": None,
            "current_publication_id": None,
            "blocking_reasons": list(gate.get("blocking_reasons") or []) or ["Activation timestamp is unavailable."],
            "semantics": {
                "durable_store_read_only": True,
                "does_not_trigger_scheduler": True,
                "does_not_call_sportsbook": True,
                "does_not_run_monte_carlo": True,
            },
        }

    runs = list_scheduler_runs(date=date, season=season, limit=250, env=environment)
    eligible_runs: list[tuple[datetime, dict[str, Any]]] = []
    for run in runs:
        completed = _parse_timestamp(_clean(run.get("completed_at_utc"))) if isinstance(run, Mapping) else None
        if completed is None or completed < activated_at:
            continue
        if run.get("provider_collection_attempted") is True and _clean(run.get("publication_id")):
            eligible_runs.append((completed, dict(run)))
    eligible_runs.sort(key=lambda item: item[0])
    first_run = eligible_runs[0][1] if eligible_runs else None

    publications = list_publications(date=date, season=season, limit=250, env=environment)
    publication_by_id: dict[str, dict[str, Any]] = {}
    for publication in publications:
        if isinstance(publication, Mapping):
            publication_id = _clean(publication.get("publication_id"))
            if publication_id:
                publication_by_id[publication_id] = dict(publication)
    matched_publication = publication_by_id.get(_clean((first_run or {}).get("publication_id")) or "") if first_run else None

    latest = get_latest_publication(date=date, season=season, require_current=False, env=environment)
    latest_id = _clean((latest or {}).get("publication_id")) if isinstance(latest, Mapping) else None

    publication_time: datetime | None = None
    if matched_publication:
        content = matched_publication.get("content") if isinstance(matched_publication.get("content"), Mapping) else {}
        publication_time = _parse_timestamp(_clean(content.get("published_at_utc")))
    publication_after_activation = publication_time is not None and publication_time >= activated_at
    verified = bool(first_run and matched_publication and publication_after_activation and latest_id)

    blockers: list[str] = []
    if not first_run:
        blockers.append("No post-activation scheduler run has both a real provider collection attempt and a publication_id yet.")
    if first_run and not matched_publication:
        blockers.append("The first post-activation provider run does not resolve to an immutable Step 5P publication.")
    if matched_publication and not publication_after_activation:
        blockers.append("Matched publication predates the recorded activation timestamp.")
    if not latest_id:
        blockers.append("No durable Step 5P publication is currently present in the board store.")

    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_first_live_cycle_verification",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _iso_now(),
        "first_live_cycle_verified": verified,
        "activation_gate_ready": True,
        "activated_at_utc": activated_at.isoformat(),
        "provider_cycle": first_run,
        "publication": matched_publication,
        "current_publication_id": latest_id,
        "blocking_reasons": blockers,
        "semantics": {
            "requires_provider_collection_attempted_true": True,
            "requires_durable_publication_reference": True,
            "requires_publication_after_activation": True,
            "durable_store_read_only": True,
            "does_not_trigger_scheduler": True,
            "does_not_call_sportsbook": True,
            "does_not_run_monte_carlo": True,
        },
    }
