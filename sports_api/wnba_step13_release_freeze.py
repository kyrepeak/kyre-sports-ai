"""WNBA Step 13D: final Step-13 scheduler and refresh-automation release freeze.

This module adds no scheduler behavior. It freezes the certified Step-13A/B/C
lineage and safety boundary before Step 14 may introduce durable persistence.
The frozen Step-13 release remains shadow-only, foreground-controlled, read-only,
and default-OFF. Step 11E continues to own refresh cadence and circuit timing.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from typing import Any

from sports_api import wnba_step12_release_freeze as step12_release
from sports_api import wnba_step13a_bounded_scheduler as step13a
from sports_api import wnba_step13b_runtime_supervisor as step13b
from sports_api import wnba_step13c_reliability_recovery as step13c

SOURCE = "Kyre Sports API WNBA Step 13 final scheduler refresh-automation release freeze"
SCHEMA_VERSION = "wnba_step_13_final_scheduler_release_freeze_v1"
INTEGRATION_VERSION = "wnba_step13d_scheduler_refresh_freeze_v1"
RELEASE_ID = "wnba_step13_scheduler_refresh_automation_2026_regular_season_frozen_v1"
SEASON = 2026
SEASON_TYPE = "Regular Season"
BRANCH = "wnba-step13d-final-scheduler-freeze-20260828"

STEP13A_FROZEN_SHA = "eaa744ae097a94d5f54c490ab13ca7d66bb725c2"
STEP13B_FROZEN_SHA = "0a0e4381d0a4deac6bbd3741f893214e99afef7b"
STEP13C_FROZEN_SHA = "23c1a9d4bb977a38048073ce7937b8efd983b998"
STEP12D_FROZEN_SHA = "48517bac86ee3f55aa4c21d6caba06c41a0a7d60"
STEP12C_FROZEN_SHA = step12_release.STEP12C_FROZEN_SHA
STEP12B_FROZEN_SHA = step12_release.STEP12B_FROZEN_SHA
STEP12A_FROZEN_SHA = step12_release.STEP12A_FROZEN_SHA
STEP11E_FROZEN_SHA = step12_release.STEP11E_FROZEN_SHA
STEP10_FROZEN_SHA = step12_release.STEP10_FROZEN_SHA
STEP9_FROZEN_SHA = step12_release.STEP9_FROZEN_SHA
STEP8_FROZEN_SHA = step12_release.STEP8_FROZEN_SHA
STEP12_RELEASE_ID = step12_release.RELEASE_ID
STEP12_RELEASE_CONTENT_SHA256 = "b557bcf8a8f585df1d91c6e5a178fd0d87ddfd5dd4a543d323b9d16d848d3c46"

STEP13D_FINAL_SCHEDULER_FREEZE_ENABLED_ENV = "WNBA_STEP13D_FINAL_SCHEDULER_FREEZE_ENABLED"

DEFAULT_ENABLED = False
PRODUCTION_ACTIVATION_ALLOWED = False
PERSISTENCE_ALLOWED = False
SUPABASE_WRITE_ALLOWED = False
PUBLIC_FASTAPI_ACTIVATION_ALLOWED = False
WAGERING_ALLOWED = False
AUTHENTICATION_ALLOWED = False
COOKIES_ALLOWED = False
BACKGROUND_DAEMON_ALLOWED = False
BACKGROUND_THREAD_ALLOWED = False
DURABLE_DISTRIBUTED_LEASE_ALLOWED = False
RUNTIME_MUTATION_ALLOWED = False
FOREGROUND_BOUNDED_SCHEDULER_CERTIFIED = True
FOREGROUND_RUNTIME_SUPERVISOR_CERTIFIED = True
FOREGROUND_RELIABILITY_MANAGER_CERTIFIED = True
PROCESS_LOCAL_ACTIVE_RUN_LEASE_CERTIFIED = True
CERTIFIED_SIMULATIONS = step12_release.CERTIFIED_SIMULATIONS
CERTIFIED_BATCH_SIZE = step12_release.CERTIFIED_BATCH_SIZE
MAX_CERTIFIED_RECOVERY_ATTEMPTS = step13c.MAX_RECOVERY_ATTEMPTS

SAFETY_CONTRACT = {
    "default_enablement": False,
    "production_runtime": False,
    "production_activation": False,
    "background_daemon": False,
    "background_thread": False,
    "persistence": False,
    "supabase_write": False,
    "public_fastapi_activation": False,
    "wager_action": False,
    "authentication": False,
    "cookies": False,
    "durable_distributed_lease": False,
    "cross_process_duplicate_run_guard": False,
    "durable_restart_recovery": False,
    "runtime_mutation": False,
    "basketball_model_change": False,
    "step8_distribution_change": False,
    "step9_ranking_change": False,
    "step9_qualification_change": False,
    "step12_presentation_change": False,
    "refresh_cadence_reinterpretation": False,
}

_FORBIDDEN_TRUE_ENV_KEYS = (
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_KYRE_DIRECT_SYNC_ENABLED",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
    "WNBA_STEP6J_CANARY_ENABLED",
    "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED",
    "WNBA_PERSISTENCE_ENABLED",
    "WNBA_SUPABASE_WRITE_ENABLED",
    "WNBA_WAGERING_ENABLED",
    "WNBA_PUBLIC_STEP11E_FASTAPI_ENABLED",
    "WNBA_STEP12_SCHEDULER_ENABLED",
)

_REQUIRED_TRUE_ENV_KEYS = (
    "WNBA_STEP13C_RELIABILITY_RECOVERY_ENABLED",
    "WNBA_STEP13B_RUNTIME_SUPERVISOR_ENABLED",
    "WNBA_STEP13A_BOUNDED_SCHEDULER_ENABLED",
    "WNBA_STEP12D_FINAL_RUNTIME_FREEZE_ENABLED",
    "WNBA_STEP12C_LIVE_BOARD_RUNTIME_ENABLED",
    "WNBA_STEP12B_LIVE_RUNTIME_ASSEMBLY_ENABLED",
    "WNBA_STEP12A_SHADOW_RUNNER_ENABLED",
    "WNBA_STEP11E_CONTROLLED_AUTOMATION_ENABLED",
)


class WNBAStep13FinalFreezeDisabledError(RuntimeError):
    """Raised when the Step-13 final freeze certification gate is not isolated."""


class WNBAStep13FinalFreezeIntegrityError(RuntimeError):
    """Raised when frozen Step-13 lineage or safety constants drift."""


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled"
    }


def step13d_final_scheduler_freeze_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(STEP13D_FINAL_SCHEDULER_FREEZE_ENABLED_ENV))


def _canonical_hash(value: Any) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _assert_release_integrity(env: Mapping[str, str] | None = None) -> None:
    source = os.environ if env is None else env
    if not step13d_final_scheduler_freeze_enabled(source):
        raise WNBAStep13FinalFreezeDisabledError(
            f"Step 13D requires {STEP13D_FINAL_SCHEDULER_FREEZE_ENABLED_ENV}=true."
        )
    bad = [name for name in _FORBIDDEN_TRUE_ENV_KEYS if _truthy(source.get(name))]
    if bad:
        raise WNBAStep13FinalFreezeDisabledError(
            "Step 13D refuses production/persistence/write/legacy scheduler switches: "
            + ", ".join(bad)
        )
    missing = [name for name in _REQUIRED_TRUE_ENV_KEYS if not _truthy(source.get(name))]
    if missing:
        raise WNBAStep13FinalFreezeDisabledError(
            "Step 13D requires the frozen Step-13/Step-12 runtime gates: "
            + ", ".join(missing)
        )

    exact = {
        "step13c_parent": step13c.STEP13B_FROZEN_SHA == STEP13B_FROZEN_SHA,
        "step13c_step13a": step13c.STEP13A_FROZEN_SHA == STEP13A_FROZEN_SHA,
        "step13c_step12d": step13c.STEP12D_FROZEN_SHA == STEP12D_FROZEN_SHA,
        "step13b_parent": step13b.STEP13A_FROZEN_SHA == STEP13A_FROZEN_SHA,
        "step13b_step12d": step13b.STEP12D_FROZEN_SHA == STEP12D_FROZEN_SHA,
        "step13a_parent": step13a.STEP12D_FROZEN_SHA == STEP12D_FROZEN_SHA,
        "step12c": step12_release.STEP12C_FROZEN_SHA == STEP12C_FROZEN_SHA,
        "step12b": step12_release.STEP12B_FROZEN_SHA == STEP12B_FROZEN_SHA,
        "step12a": step12_release.STEP12A_FROZEN_SHA == STEP12A_FROZEN_SHA,
        "step11e": step12_release.STEP11E_FROZEN_SHA == STEP11E_FROZEN_SHA,
        "step10": step12_release.STEP10_FROZEN_SHA == STEP10_FROZEN_SHA,
        "step9": step12_release.STEP9_FROZEN_SHA == STEP9_FROZEN_SHA,
        "step8": step12_release.STEP8_FROZEN_SHA == STEP8_FROZEN_SHA,
        "simulation_count": CERTIFIED_SIMULATIONS == 5_000_000,
    }
    failed = [name for name, ok in exact.items() if not ok]
    if failed:
        raise WNBAStep13FinalFreezeIntegrityError(
            "Step 13D frozen lineage drift: " + ", ".join(failed)
        )

    false_constants = {
        "step13d_default": DEFAULT_ENABLED,
        "step13d_production": PRODUCTION_ACTIVATION_ALLOWED,
        "step13d_persistence": PERSISTENCE_ALLOWED,
        "step13d_supabase": SUPABASE_WRITE_ALLOWED,
        "step13d_public_api": PUBLIC_FASTAPI_ACTIVATION_ALLOWED,
        "step13d_wagering": WAGERING_ALLOWED,
        "step13d_auth": AUTHENTICATION_ALLOWED,
        "step13d_cookies": COOKIES_ALLOWED,
        "step13d_background_daemon": BACKGROUND_DAEMON_ALLOWED,
        "step13d_background_thread": BACKGROUND_THREAD_ALLOWED,
        "step13d_distributed_lease": DURABLE_DISTRIBUTED_LEASE_ALLOWED,
        "step13d_runtime_mutation": RUNTIME_MUTATION_ALLOWED,
        "step13a_default": step13a.DEFAULT_ENABLED,
        "step13a_production": step13a.PRODUCTION_ACTIVATION_ALLOWED,
        "step13a_persistence": step13a.PERSISTENCE_ALLOWED,
        "step13a_supabase": step13a.SUPABASE_WRITE_ALLOWED,
        "step13a_public_api": step13a.PUBLIC_FASTAPI_ACTIVATION_ALLOWED,
        "step13a_wagering": step13a.WAGERING_ALLOWED,
        "step13a_auth": step13a.AUTHENTICATION_ALLOWED,
        "step13a_cookies": step13a.COOKIES_ALLOWED,
        "step13a_background_daemon": step13a.BACKGROUND_DAEMON_ALLOWED,
        "step13b_default": step13b.DEFAULT_ENABLED,
        "step13b_production": step13b.PRODUCTION_ACTIVATION_ALLOWED,
        "step13b_persistence": step13b.PERSISTENCE_ALLOWED,
        "step13b_supabase": step13b.SUPABASE_WRITE_ALLOWED,
        "step13b_public_api": step13b.PUBLIC_FASTAPI_ACTIVATION_ALLOWED,
        "step13b_wagering": step13b.WAGERING_ALLOWED,
        "step13b_auth": step13b.AUTHENTICATION_ALLOWED,
        "step13b_cookies": step13b.COOKIES_ALLOWED,
        "step13b_background_daemon": step13b.BACKGROUND_DAEMON_ALLOWED,
        "step13b_background_thread": step13b.BACKGROUND_THREAD_ALLOWED,
        "step13c_default": step13c.DEFAULT_ENABLED,
        "step13c_production": step13c.PRODUCTION_ACTIVATION_ALLOWED,
        "step13c_persistence": step13c.PERSISTENCE_ALLOWED,
        "step13c_supabase": step13c.SUPABASE_WRITE_ALLOWED,
        "step13c_public_api": step13c.PUBLIC_FASTAPI_ACTIVATION_ALLOWED,
        "step13c_wagering": step13c.WAGERING_ALLOWED,
        "step13c_auth": step13c.AUTHENTICATION_ALLOWED,
        "step13c_cookies": step13c.COOKIES_ALLOWED,
        "step13c_background_daemon": step13c.BACKGROUND_DAEMON_ALLOWED,
        "step13c_background_thread": step13c.BACKGROUND_THREAD_ALLOWED,
        "step13c_distributed_lease": step13c.DURABLE_DISTRIBUTED_LEASE_ALLOWED,
    }
    drift = [name for name, value in false_constants.items() if value is not False]
    if drift:
        raise WNBAStep13FinalFreezeIntegrityError(
            "Step 13D safety constant drift: " + ", ".join(drift)
        )

    true_constants = {
        "step13a_foreground_scheduler": step13a.FOREGROUND_BOUNDED_SCHEDULER_ALLOWED,
        "step13b_foreground_supervisor": step13b.FOREGROUND_RUNTIME_SUPERVISOR_ALLOWED,
        "step13c_foreground_reliability": step13c.FOREGROUND_RELIABILITY_MANAGER_ALLOWED,
        "step13c_process_local_lease": step13c.PROCESS_LOCAL_ACTIVE_RUN_LEASE_ALLOWED,
        "step13d_foreground_scheduler_certified": FOREGROUND_BOUNDED_SCHEDULER_CERTIFIED,
        "step13d_foreground_supervisor_certified": FOREGROUND_RUNTIME_SUPERVISOR_CERTIFIED,
        "step13d_foreground_reliability_certified": FOREGROUND_RELIABILITY_MANAGER_CERTIFIED,
        "step13d_process_local_lease_certified": PROCESS_LOCAL_ACTIVE_RUN_LEASE_CERTIFIED,
    }
    missing_true = [name for name, value in true_constants.items() if value is not True]
    if missing_true:
        raise WNBAStep13FinalFreezeIntegrityError(
            "Step 13D scheduler capability drift: " + ", ".join(missing_true)
        )
    if step13c.MAX_RECOVERY_ATTEMPTS != MAX_CERTIFIED_RECOVERY_ATTEMPTS:
        raise WNBAStep13FinalFreezeIntegrityError("Step 13D recovery-attempt ceiling drift.")
    if MAX_CERTIFIED_RECOVERY_ATTEMPTS != 5:
        raise WNBAStep13FinalFreezeIntegrityError("Step 13D expected recovery ceiling is five.")

    step12_manifest = step12_release.build_step12d_release_manifest(
        env=source,
        generated_at_utc="2026-08-28T00:00:00+00:00",
    )
    if step12_manifest.get("release_id") != STEP12_RELEASE_ID:
        raise WNBAStep13FinalFreezeIntegrityError("Step 13D frozen Step-12 release ID drift.")
    if step12_manifest.get("release_content_sha256") != STEP12_RELEASE_CONTENT_SHA256:
        raise WNBAStep13FinalFreezeIntegrityError("Step 13D frozen Step-12 release hash drift.")


def build_step13d_release_manifest(
    *, env: Mapping[str, str] | None = None, generated_at_utc: str | None = None
) -> dict[str, Any]:
    """Return a content-addressed manifest for the certified Step-13 frozen release."""
    _assert_release_integrity(env)
    generated = generated_at_utc or datetime.now(timezone.utc).isoformat()
    result = {
        "data_type": "wnba_step13_final_scheduler_release_freeze",
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        "integration_version": INTEGRATION_VERSION,
        "release_id": RELEASE_ID,
        "generated_at_utc": generated,
        "season": SEASON,
        "season_type": SEASON_TYPE,
        "branch": BRANCH,
        "lineage": {
            "step13a_frozen_sha": STEP13A_FROZEN_SHA,
            "step13b_frozen_sha": STEP13B_FROZEN_SHA,
            "step13c_frozen_sha": STEP13C_FROZEN_SHA,
            "step12d_frozen_sha": STEP12D_FROZEN_SHA,
            "step12c_frozen_sha": STEP12C_FROZEN_SHA,
            "step12b_frozen_sha": STEP12B_FROZEN_SHA,
            "step12a_frozen_sha": STEP12A_FROZEN_SHA,
            "step11e_frozen_sha": STEP11E_FROZEN_SHA,
            "step10_frozen_sha": STEP10_FROZEN_SHA,
            "step9_frozen_sha": STEP9_FROZEN_SHA,
            "step8_frozen_sha": STEP8_FROZEN_SHA,
            "step12_release_id": STEP12_RELEASE_ID,
            "step12_release_content_sha256": STEP12_RELEASE_CONTENT_SHA256,
        },
        "scheduler_contract": {
            "foreground_bounded_scheduler": True,
            "foreground_runtime_supervisor": True,
            "foreground_reliability_manager": True,
            "frozen_step11e_owns_refresh_cadence": True,
            "frozen_next_refresh_due_drives_waiting": True,
            "controller_state_carried_in_memory": True,
            "slate_rollover_resets_controller_state": True,
            "graceful_shutdown_supported": True,
            "process_local_duplicate_run_guard": True,
            "cross_process_duplicate_run_guard": False,
            "bounded_transport_recovery": True,
            "recoverable_error_types": ["TimeoutError", "ConnectionError"],
            "max_recovery_attempts": MAX_CERTIFIED_RECOVERY_ATTEMPTS,
            "integrity_errors_never_retried": True,
            "unknown_exceptions_fail_closed": True,
        },
        "analytical_contract": {
            "shadow_only": True,
            "read_only": True,
            "certified_simulations_per_projection": CERTIFIED_SIMULATIONS,
            "certified_batch_size": CERTIFIED_BATCH_SIZE,
            "frozen_step8_distribution_preserved": True,
            "frozen_step9_ranking_preserved": True,
            "frozen_step9_qualification_preserved": True,
            "frozen_step12_presentation_preserved": True,
            "top_five_never_forced": True,
        },
        "safety_contract": deepcopy(SAFETY_CONTRACT),
        "phase_boundary": {
            "step13_complete": True,
            "step14_persistence_not_started": True,
            "durable_distributed_lease_not_started": True,
            "durable_restart_recovery_not_started": True,
            "production_deployment_not_started": True,
            "wagering_not_started": True,
        },
    }
    hash_surface = deepcopy(result)
    hash_surface.pop("generated_at_utc", None)
    result["release_content_sha256"] = _canonical_hash(hash_surface)
    _assert_release_integrity(env)
    return result


__all__ = [
    "BRANCH",
    "CERTIFIED_BATCH_SIZE",
    "CERTIFIED_SIMULATIONS",
    "DEFAULT_ENABLED",
    "INTEGRATION_VERSION",
    "MAX_CERTIFIED_RECOVERY_ATTEMPTS",
    "RELEASE_ID",
    "SAFETY_CONTRACT",
    "SCHEMA_VERSION",
    "SEASON",
    "SEASON_TYPE",
    "SOURCE",
    "STEP12D_FROZEN_SHA",
    "STEP12_RELEASE_CONTENT_SHA256",
    "STEP12_RELEASE_ID",
    "STEP13A_FROZEN_SHA",
    "STEP13B_FROZEN_SHA",
    "STEP13C_FROZEN_SHA",
    "STEP13D_FINAL_SCHEDULER_FREEZE_ENABLED_ENV",
    "WNBAStep13FinalFreezeDisabledError",
    "WNBAStep13FinalFreezeIntegrityError",
    "build_step13d_release_manifest",
    "step13d_final_scheduler_freeze_enabled",
]
