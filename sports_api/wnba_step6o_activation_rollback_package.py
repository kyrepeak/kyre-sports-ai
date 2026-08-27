"""WNBA Step 6O deterministic activation + rollback package.

Step 6O does not activate hosting, mutate environment variables, start the
scheduler, refresh DraftKings, write the Kyre feed, or execute a model. It
packages the already-proven Step 5T and Steps 6J-6N contracts into one
canonical operator handoff with an ordered fail-closed rollback.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
import hashlib
import json
import os
import re
from typing import Any

from sports_api.wnba_release_activation_readiness import get_release_readiness
from sports_api.wnba_step6m_scheduler_orchestration import get_step6m_scheduler_orchestration_status
from sports_api.wnba_step6n_production_observability import build_step6n_production_observability

MODEL_SOURCE = "Kyre Sports API WNBA Step 6O activation + rollback package"
MODEL_VERSION = "wnba_step_6o_activation_rollback_package_v1"
SCHEMA_VERSION = MODEL_VERSION

TARGET_REVISION_ENV = "WNBA_STEP6O_TARGET_REVISION"
TARGET_IMAGE_REF_ENV = "WNBA_STEP6O_TARGET_IMAGE_REF"

FROZEN_STEP6I_REVISION = "2195b1839f47745737c2d0e788c319743cda3ee0"
CORRECTED_STEP6M_REVISION = "1115ef42d522937a2bf17afaf3f73ff990daa054"
FROZEN_STEP6N_REVISION = "a5bdcbbd5312c0db0dd931d71844eed865542908"

_REVISION_RE = re.compile(r"^[0-9a-f]{40}$")
_IMAGE_RE = re.compile(r"^[^\s@]+@sha256:[0-9a-f]{64}$")


class WNBAStep6OPackageError(RuntimeError):
    pass


class WNBAStep6ONotReadyError(WNBAStep6OPackageError):
    pass


def _environment(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if env is None else env


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _valid_revision(value: str | None) -> bool:
    return bool(value and _REVISION_RE.fullmatch(value.casefold()))


def _valid_image(value: str | None) -> bool:
    return bool(value and _IMAGE_RE.fullmatch(value.casefold()))


def _activation_steps() -> list[dict[str, Any]]:
    return [
        {"order": 1, "action": "verify_step6o_manifest_and_immutable_release_identity", "mutation": False},
        {"order": 2, "action": "deploy_or_verify_target_image_with_production_runtime_disabled", "mutation": True},
        {"order": 3, "action": "attach_and_preserve_existing_persistent_volume", "mutation": True},
        {"order": 4, "action": "verify_global_step6j_canary_direct_reconciled_switches_off", "mutation": False},
        {"order": 5, "action": "complete_exactly_one_step6j_durable_canary_and_automatic_rollback_proof", "mutation": True},
        {"order": 6, "action": "verify_step6j_temporary_switches_restored_off", "mutation": False},
        {"order": 7, "action": "require_step6k_scheduler_authorization", "mutation": False},
        {"order": 8, "action": "enable_step6l_production_refresh_authority_only", "mutation": True},
        {"order": 9, "action": "enable_production_runtime_and_restart_once", "mutation": True},
        {"order": 10, "action": "require_step6m_owned_feed_scheduler_ready", "mutation": False},
        {"order": 11, "action": "require_step6n_state_healthy", "mutation": False},
        {"order": 12, "action": "verify_current_publication_when_official_slate_is_playable", "mutation": False},
    ]


def _rollback_steps(has_previous_release: bool) -> list[dict[str, Any]]:
    steps = [
        {"order": 1, "action": "disable_production_runtime", "mutation": True},
        {"order": 2, "action": "disable_step6l_production_refresh_authority", "mutation": True},
        {"order": 3, "action": "force_global_step6j_canary_direct_reconciled_switches_off", "mutation": True},
        {"order": 4, "action": "restart_or_stop_current_replica_with_runtime_disabled", "mutation": True},
        {"order": 5, "action": "preserve_persistent_volume_feed_and_sqlite_history", "mutation": False},
    ]
    if has_previous_release:
        steps.extend([
            {"order": 6, "action": "redeploy_previous_immutable_image_with_runtime_disabled", "mutation": True},
            {"order": 7, "action": "verify_previous_revision_and_image_identity", "mutation": False},
        ])
        next_order = 8
    else:
        steps.append({"order": 6, "action": "hold_current_image_runtime_disabled_for_operator_recovery", "mutation": False})
        next_order = 7
    steps.extend([
        {"order": next_order, "action": "run_read_only_release_and_storage_verification", "mutation": False},
        {"order": next_order + 1, "action": "inspect_step6n_and_resolve_all_critical_incidents_before_reenable", "mutation": False},
        {"order": next_order + 2, "action": "require_new_explicit_operator_decision_before_any_reactivation", "mutation": False},
    ])
    return steps


def build_step6o_activation_rollback_package(
    *,
    env: Mapping[str, str] | None = None,
    release_getter: Callable[..., dict[str, Any]] = get_release_readiness,
    step6m_getter: Callable[..., dict[str, Any]] = get_step6m_scheduler_orchestration_status,
    observability_getter: Callable[..., dict[str, Any]] = build_step6n_production_observability,
) -> dict[str, Any]:
    """Build the zero-mutation activation/rollback handoff package."""
    environment = _environment(env)
    release = release_getter(env=environment)
    step6m = step6m_getter(env=environment)
    observability = observability_getter(env=environment)

    target_revision = (_clean(environment.get(TARGET_REVISION_ENV)) or _clean((release.get("release") or {}).get("revision")))
    target_image = (_clean(environment.get(TARGET_IMAGE_REF_ENV)) or _clean((release.get("release") or {}).get("image_ref")))
    target_revision = target_revision.casefold() if target_revision else None
    target_image = target_image.casefold() if target_image else None

    release_revision = _clean((release.get("release") or {}).get("revision"))
    release_image = _clean((release.get("release") or {}).get("image_ref"))
    release_revision = release_revision.casefold() if release_revision else None
    release_image = release_image.casefold() if release_image else None

    step6l = step6m.get("step_6l") or {}
    step6k = step6l.get("step_6k") or {}
    rollback_target = release.get("rollback_target") or {}
    has_previous_release = bool(rollback_target.get("revision") and rollback_target.get("image_ref"))

    package_checks = {
        "step6n_observer_is_noncritical": observability.get("state") in {"safe_deferred", "healthy", "degraded"},
        "rollback_preserves_persistent_volume": rollback_target.get("preserve_persistent_volume") is True,
        "rollback_never_deletes_database_files": rollback_target.get("delete_database_files") is False,
        "activation_plan_starts_with_identity_verification": _activation_steps()[0]["mutation"] is False,
        "rollback_disables_runtime_first": _rollback_steps(has_previous_release)[0]["action"] == "disable_production_runtime",
    }
    package_ready = all(package_checks.values())

    activation_blockers: list[str] = []
    def need(condition: bool, reason: str) -> None:
        if not condition:
            activation_blockers.append(reason)

    need(release.get("release_ready") is True, "Step 5T immutable release gate is not ready.")
    need(release.get("rollback_ready") is True, "Step 5T rollback target is not ready.")
    need(_valid_revision(target_revision), f"{TARGET_REVISION_ENV} or Step 5T release revision must be a full Git SHA.")
    need(_valid_image(target_image), f"{TARGET_IMAGE_REF_ENV} or Step 5T release image must be digest-pinned.")
    if _valid_revision(target_revision) and release_revision:
        need(target_revision == release_revision, "Step 6O target revision drifts from the Step 5T release revision.")
    if _valid_image(target_image) and release_image:
        need(target_image == release_image, "Step 6O target image drifts from the Step 5T release image.")
    need(step6k.get("scheduler_authorized") is True, "Step 6K scheduler authorization is not complete.")
    need(step6l.get("production_refresh_ready") is True, "Step 6L production refresh authority is not ready.")
    need(step6m.get("scheduler_cycle_ready") is True, "Step 6M owned-feed scheduler cycle is not ready.")
    need(observability.get("state") == "healthy", "Step 6N must be healthy for final live acceptance.")

    live_activation_ready = package_ready and not activation_blockers
    state = "activation_ready" if live_activation_ready else "safe_deferred" if observability.get("state") == "safe_deferred" else "activation_blocked"

    activation_steps = _activation_steps()
    rollback_steps = _rollback_steps(has_previous_release)
    manifest_payload = {
        "schema_version": SCHEMA_VERSION,
        "frozen_anchors": {
            "step6i": FROZEN_STEP6I_REVISION,
            "corrected_step6m": CORRECTED_STEP6M_REVISION,
            "step6n": FROZEN_STEP6N_REVISION,
        },
        "target_revision": target_revision,
        "target_image_ref": target_image,
        "release_manifest_fingerprint_sha256": (release.get("release") or {}).get("manifest_fingerprint_sha256"),
        "storage_identity_sha256": release.get("storage_identity_sha256"),
        "activation_actions": [row["action"] for row in activation_steps],
        "rollback_actions": [row["action"] for row in rollback_steps],
    }
    manifest_sha256 = _hash(manifest_payload)

    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_step6o_activation_rollback_package",
        "schema_version": SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _utc_now(),
        "state": state,
        "package_ready": package_ready,
        "live_activation_ready": live_activation_ready,
        "activation_blocking_reasons": activation_blockers,
        "manifest": {
            **manifest_payload,
            "manifest_sha256": manifest_sha256,
            "canonical_json_sha256": manifest_sha256,
        },
        "package_checks": package_checks,
        "activation_plan": {
            "steps": activation_steps,
            "post_activation_acceptance": {
                "step6m_scheduler_cycle_ready": True,
                "step6n_required_state": "healthy",
                "current_publication_required_only_for_playable_official_slate": True,
            },
        },
        "rollback_plan": {
            "steps": rollback_steps,
            "target": rollback_target,
            "has_previous_immutable_release": has_previous_release,
            "persistent_storage_preserved": True,
        },
        "evidence": {
            "step_5t": {
                "release_ready": release.get("release_ready"),
                "rollback_ready": release.get("rollback_ready"),
                "phase": release.get("phase"),
            },
            "step_6k_scheduler_authorized": step6k.get("scheduler_authorized"),
            "step_6l_production_refresh_ready": step6l.get("production_refresh_ready"),
            "step_6m_scheduler_cycle_ready": step6m.get("scheduler_cycle_ready"),
            "step_6n_state": observability.get("state"),
            "step_6n_incident_active": observability.get("incident_active"),
        },
        "semantics": {
            "package_builder_is_read_only": True,
            "package_builder_uses_network": False,
            "paid_host_created": False,
            "environment_mutated": False,
            "scheduler_started": False,
            "draftkings_called": False,
            "feed_write_performed": False,
            "monte_carlo_run": False,
            "wager_action_performed": False,
            "live_activation_requires_separate_operator_boundary": True,
            "rollback_disables_runtime_before_refresh_or_image_recovery": True,
            "rollback_preserves_persistent_storage": True,
        },
    }


def require_step6o_live_activation_ready(*, env: Mapping[str, str] | None = None) -> dict[str, Any]:
    report = build_step6o_activation_rollback_package(env=env)
    if report.get("live_activation_ready") is not True:
        raise WNBAStep6ONotReadyError(
            "WNBA Step 6O live activation is not ready: "
            + "; ".join(report.get("activation_blocking_reasons") or ["unknown blocker"])
        )
    return report
