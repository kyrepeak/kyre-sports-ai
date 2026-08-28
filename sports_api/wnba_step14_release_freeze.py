"""WNBA Step 14D: final durable-persistence release freeze.

Step 14D adds no runtime behavior. It seals the certified Step-14A checkpoint
contract, Step-14B PostgreSQL checkpoint adapter, and Step-14C durable restart
plus cross-process lease into one content-addressed release manifest.

The frozen release remains default-OFF, explicit-invocation only, foreground-only,
and non-production. Global persistence activation, background workers, public
persistence APIs, Supabase REST writes, sportsbook authentication/cookies,
wagering, and all frozen basketball-model/ranking behavior remain unchanged.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from sports_api import wnba_step13_release_freeze as step13_release
from sports_api import wnba_step14a_persistence_contract as step14a
from sports_api import wnba_step14b_database_checkpoint_adapter as step14b
from sports_api import wnba_step14c_durable_restart_lease as step14c

SOURCE = "Kyre Sports API WNBA Step 14 final durable persistence release freeze"
SCHEMA_VERSION = "wnba_step_14_final_persistence_release_freeze_v1"
INTEGRATION_VERSION = "wnba_step14d_final_persistence_freeze_v1"
RELEASE_ID = "wnba_step14_durable_persistence_restart_lease_2026_regular_season_frozen_v1"
SEASON = 2026
SEASON_TYPE = "Regular Season"
BRANCH = "wnba-step14d-final-persistence-freeze-20260828"

STEP14A_FROZEN_SHA = "aa1d770cd9840dac7e31139ab177fa4aa3ac9020"
STEP14B_FROZEN_SHA = "dfea123c0702331ecccf3ca285baf1d69b8f3c2e"
STEP14C_FROZEN_SHA = "e2ff1f8c3729b1dd80189501cd64ddd7393cf077"
STEP13D_FROZEN_SHA = step14a.STEP13D_FROZEN_SHA
STEP13_RELEASE_ID = step14a.STEP13_RELEASE_ID
STEP13_RELEASE_CONTENT_SHA256 = step14a.STEP13_RELEASE_CONTENT_SHA256
STEP14A_CONTRACT_ID = step14a.CONTRACT_ID
STEP14A_MANIFEST_CONTENT_SHA256 = step14b.STEP14A_MANIFEST_CONTENT_SHA256
STEP14A_SQL_SCHEMA_SHA256 = step14b.STEP14A_SQL_SCHEMA_SHA256
STEP14C_LEASE_SQL_SCHEMA_SHA256 = step14c.LEASE_SQL_SCHEMA_SHA256

STEP14D_FINAL_PERSISTENCE_FREEZE_ENABLED_ENV = "WNBA_STEP14D_FINAL_PERSISTENCE_FREEZE_ENABLED"

DEFAULT_ENABLED = False
PRODUCTION_ACTIVATION_ALLOWED = False
GLOBAL_PERSISTENCE_RUNTIME_ENABLED = False
AUTOMATIC_PRODUCTION_RESTART_ACTIVATION_ALLOWED = False
SUPABASE_REST_WRITE_ALLOWED = False
PUBLIC_FASTAPI_ACTIVATION_ALLOWED = False
WAGERING_ALLOWED = False
AUTHENTICATION_ALLOWED = False
COOKIES_ALLOWED = False
BACKGROUND_DAEMON_ALLOWED = False
BACKGROUND_THREAD_ALLOWED = False
BASKETBALL_MODEL_MUTATION_ALLOWED = False
RANKING_MUTATION_ALLOWED = False
RUNTIME_MUTATION_ALLOWED = False

POSTGRESQL_CHECKPOINT_ADAPTER_CERTIFIED = True
APPEND_ONLY_CHECKPOINT_HISTORY_CERTIFIED = True
CHECKPOINT_HEAD_CAS_CERTIFIED = True
DURABLE_RESTART_RECOVERY_CERTIFIED = True
DURABLE_DISTRIBUTED_LEASE_CERTIFIED = True
CROSS_PROCESS_DUPLICATE_RUN_GUARD_CERTIFIED = True
FENCING_GENERATION_CERTIFIED = True
LEASE_EXPIRY_CERTIFIED = True
STALE_OWNER_FENCING_CERTIFIED = True
CHECKPOINT_PERSIST_AFTER_SUCCESS_CERTIFIED = True
SUPABASE_POSTGRES_COMPATIBLE_CERTIFIED = True
FOREGROUND_ONLY_CERTIFIED = True
EXPLICIT_INVOCATION_REQUIRED = True

SAFETY_CONTRACT = {
    "default_enablement": False,
    "production_runtime": False,
    "production_activation": False,
    "global_persistence_runtime": False,
    "automatic_production_restart_activation": False,
    "supabase_rest_write": False,
    "public_fastapi_activation": False,
    "wager_action": False,
    "authentication": False,
    "cookies": False,
    "background_daemon": False,
    "background_thread": False,
    "basketball_model_change": False,
    "step8_distribution_change": False,
    "step9_ranking_change": False,
    "step9_qualification_change": False,
    "step12_presentation_change": False,
    "runtime_mutation": False,
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
    "WNBA_STEP14C_DURABLE_RESTART_LEASE_ENABLED",
    "WNBA_STEP14B_DATABASE_CHECKPOINT_ADAPTER_ENABLED",
    "WNBA_STEP14B_DATABASE_READ_ENABLED",
    "WNBA_STEP14B_DATABASE_WRITE_ENABLED",
    "WNBA_STEP14A_PERSISTENCE_CONTRACT_ENABLED",
    "WNBA_STEP13D_FINAL_SCHEDULER_FREEZE_ENABLED",
    "WNBA_STEP13C_RELIABILITY_RECOVERY_ENABLED",
    "WNBA_STEP13B_RUNTIME_SUPERVISOR_ENABLED",
    "WNBA_STEP13A_BOUNDED_SCHEDULER_ENABLED",
    "WNBA_STEP12D_FINAL_RUNTIME_FREEZE_ENABLED",
    "WNBA_STEP12C_LIVE_BOARD_RUNTIME_ENABLED",
    "WNBA_STEP12B_LIVE_RUNTIME_ASSEMBLY_ENABLED",
    "WNBA_STEP12A_SHADOW_RUNNER_ENABLED",
    "WNBA_STEP11E_CONTROLLED_AUTOMATION_ENABLED",
)


class WNBAStep14FinalFreezeDisabledError(RuntimeError):
    """Raised when the isolated Step-14D freeze gate is not safely enabled."""


class WNBAStep14FinalFreezeIntegrityError(RuntimeError):
    """Raised when frozen Step-14 lineage, schemas, or safety boundaries drift."""


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled"
    }


def step14d_final_persistence_freeze_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(STEP14D_FINAL_PERSISTENCE_FREEZE_ENABLED_ENV))


def _canonical_hash(value: Any) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _file_sha256(path: str) -> str:
    try:
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()
    except OSError as exc:
        raise WNBAStep14FinalFreezeIntegrityError(
            f"Step 14D cannot read frozen schema file: {path}."
        ) from exc


def _assert_release_integrity(env: Mapping[str, str] | None = None) -> None:
    source = os.environ if env is None else env
    if not step14d_final_persistence_freeze_enabled(source):
        raise WNBAStep14FinalFreezeDisabledError(
            f"Step 14D requires {STEP14D_FINAL_PERSISTENCE_FREEZE_ENABLED_ENV}=true."
        )
    bad = [name for name in _FORBIDDEN_TRUE_ENV_KEYS if _truthy(source.get(name))]
    if bad:
        raise WNBAStep14FinalFreezeDisabledError(
            "Step 14D refuses production/global-persistence/write/wagering switches: "
            + ", ".join(bad)
        )
    missing = [name for name in _REQUIRED_TRUE_ENV_KEYS if not _truthy(source.get(name))]
    if missing:
        raise WNBAStep14FinalFreezeDisabledError(
            "Step 14D requires the frozen Step-14/13/12 runtime gates: "
            + ", ".join(missing)
        )

    exact = {
        "step14c_parent": step14c.STEP14B_FROZEN_SHA == STEP14B_FROZEN_SHA,
        "step14b_parent": step14b.STEP14A_FROZEN_SHA == STEP14A_FROZEN_SHA,
        "step14a_contract_id": step14a.CONTRACT_ID == STEP14A_CONTRACT_ID,
        "step14a_step13d": step14a.STEP13D_FROZEN_SHA == STEP13D_FROZEN_SHA,
        "step13_release_id": step13_release.RELEASE_ID == STEP13_RELEASE_ID,
        "step13_release_hash": step13_release.build_step13d_release_manifest(
            env=source, generated_at_utc="2026-08-28T00:00:00+00:00"
        ).get("release_content_sha256") == STEP13_RELEASE_CONTENT_SHA256,
        "step14a_sql_hash": _file_sha256(step14a.SQL_SCHEMA_PATH) == STEP14A_SQL_SCHEMA_SHA256,
        "step14c_lease_sql_hash": _file_sha256(step14c.LEASE_SQL_SCHEMA_PATH) == STEP14C_LEASE_SQL_SCHEMA_SHA256,
    }
    failed = [name for name, ok in exact.items() if not ok]
    if failed:
        raise WNBAStep14FinalFreezeIntegrityError(
            "Step 14D frozen lineage/schema drift: " + ", ".join(failed)
        )

    step14a_manifest = step14a.build_step14a_schema_manifest(env=source)
    if step14a_manifest.get("manifest_content_sha256") != STEP14A_MANIFEST_CONTENT_SHA256:
        raise WNBAStep14FinalFreezeIntegrityError("Step 14D Step-14A manifest hash drift.")

    parent_false = {
        "step14a_database_read": step14a.DATABASE_READ_ALLOWED,
        "step14a_database_write": step14a.DATABASE_WRITE_ALLOWED,
        "step14a_persistence_runtime": step14a.PERSISTENCE_RUNTIME_ENABLED,
        "step14a_distributed_lease": step14a.DURABLE_DISTRIBUTED_LEASE_ALLOWED,
        "step14b_persistence_runtime": step14b.PERSISTENCE_RUNTIME_ENABLED,
        "step14b_restart_recovery": step14b.DURABLE_RESTART_RECOVERY_ALLOWED,
        "step14b_distributed_lease": step14b.DURABLE_DISTRIBUTED_LEASE_ALLOWED,
        "step14b_cross_process_guard": step14b.CROSS_PROCESS_DUPLICATE_RUN_GUARD_ALLOWED,
        "step14b_production": step14b.PRODUCTION_ACTIVATION_ALLOWED,
        "step14c_default": step14c.DEFAULT_ENABLED,
        "step14c_persistence_runtime": step14c.PERSISTENCE_RUNTIME_ENABLED,
        "step14c_auto_production_restart": step14c.AUTOMATIC_PRODUCTION_RESTART_ACTIVATION_ALLOWED,
        "step14c_supabase_rest": step14c.SUPABASE_REST_WRITE_ALLOWED,
        "step14c_production": step14c.PRODUCTION_ACTIVATION_ALLOWED,
        "step14c_public_api": step14c.PUBLIC_FASTAPI_ACTIVATION_ALLOWED,
        "step14c_wagering": step14c.WAGERING_ALLOWED,
        "step14c_auth": step14c.AUTHENTICATION_ALLOWED,
        "step14c_cookies": step14c.COOKIES_ALLOWED,
        "step14c_background_daemon": step14c.BACKGROUND_DAEMON_ALLOWED,
        "step14c_background_thread": step14c.BACKGROUND_THREAD_ALLOWED,
        "step14c_model_mutation": step14c.BASKETBALL_MODEL_MUTATION_ALLOWED,
        "step14c_ranking_mutation": step14c.RANKING_MUTATION_ALLOWED,
    }
    drift_false = [name for name, value in parent_false.items() if value is not False]
    if drift_false:
        raise WNBAStep14FinalFreezeIntegrityError(
            "Step 14D frozen parent safety drift: " + ", ".join(drift_false)
        )

    parent_true = {
        "step14b_database_read": step14b.POSTGRESQL_DATABASE_READ_ALLOWED,
        "step14b_database_write": step14b.POSTGRESQL_DATABASE_WRITE_ALLOWED,
        "step14b_checkpoint_load": step14b.CHECKPOINT_LOAD_ALLOWED,
        "step14b_checkpoint_save": step14b.CHECKPOINT_SAVE_ALLOWED,
        "step14b_head_cas": step14b.ATOMIC_HEAD_COMPARE_AND_SWAP_ALLOWED,
        "step14b_append_only_history": step14b.APPEND_ONLY_HISTORY_REQUIRED,
        "step14b_supabase_postgres": step14b.SUPABASE_POSTGRES_COMPATIBLE,
        "step14c_foreground_orchestration": step14c.FOREGROUND_DURABLE_RESTART_ORCHESTRATION_ALLOWED,
        "step14c_restart_recovery": step14c.DURABLE_RESTART_RECOVERY_ALLOWED,
        "step14c_distributed_lease": step14c.DURABLE_DISTRIBUTED_LEASE_ALLOWED,
        "step14c_cross_process_guard": step14c.CROSS_PROCESS_DUPLICATE_RUN_GUARD_ALLOWED,
        "step14c_checkpoint_persist": step14c.CHECKPOINT_PERSIST_AFTER_SUCCESS_ALLOWED,
        "step14c_fencing_generation": step14c.FENCING_GENERATION_REQUIRED,
        "step14c_lease_expiry": step14c.LEASE_EXPIRY_REQUIRED,
    }
    drift_true = [name for name, value in parent_true.items() if value is not True]
    if drift_true:
        raise WNBAStep14FinalFreezeIntegrityError(
            "Step 14D frozen persistence capability drift: " + ", ".join(drift_true)
        )

    own_false = (
        DEFAULT_ENABLED, PRODUCTION_ACTIVATION_ALLOWED, GLOBAL_PERSISTENCE_RUNTIME_ENABLED,
        AUTOMATIC_PRODUCTION_RESTART_ACTIVATION_ALLOWED, SUPABASE_REST_WRITE_ALLOWED,
        PUBLIC_FASTAPI_ACTIVATION_ALLOWED, WAGERING_ALLOWED, AUTHENTICATION_ALLOWED,
        COOKIES_ALLOWED, BACKGROUND_DAEMON_ALLOWED, BACKGROUND_THREAD_ALLOWED,
        BASKETBALL_MODEL_MUTATION_ALLOWED, RANKING_MUTATION_ALLOWED, RUNTIME_MUTATION_ALLOWED,
    )
    if any(value is not False for value in own_false):
        raise WNBAStep14FinalFreezeIntegrityError("Step 14D own safety constant drift.")

    own_true = (
        POSTGRESQL_CHECKPOINT_ADAPTER_CERTIFIED, APPEND_ONLY_CHECKPOINT_HISTORY_CERTIFIED,
        CHECKPOINT_HEAD_CAS_CERTIFIED, DURABLE_RESTART_RECOVERY_CERTIFIED,
        DURABLE_DISTRIBUTED_LEASE_CERTIFIED, CROSS_PROCESS_DUPLICATE_RUN_GUARD_CERTIFIED,
        FENCING_GENERATION_CERTIFIED, LEASE_EXPIRY_CERTIFIED, STALE_OWNER_FENCING_CERTIFIED,
        CHECKPOINT_PERSIST_AFTER_SUCCESS_CERTIFIED, SUPABASE_POSTGRES_COMPATIBLE_CERTIFIED,
        FOREGROUND_ONLY_CERTIFIED, EXPLICIT_INVOCATION_REQUIRED,
    )
    if any(value is not True for value in own_true):
        raise WNBAStep14FinalFreezeIntegrityError("Step 14D certification constant drift.")


def build_step14d_release_manifest(
    *, env: Mapping[str, str] | None = None, generated_at_utc: str | None = None
) -> dict[str, Any]:
    """Return the content-addressed final Step-14 persistence release manifest."""
    _assert_release_integrity(env)
    generated = generated_at_utc or datetime.now(timezone.utc).isoformat()
    result = {
        "data_type": "wnba_step14_final_persistence_release_freeze",
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        "integration_version": INTEGRATION_VERSION,
        "release_id": RELEASE_ID,
        "generated_at_utc": generated,
        "season": SEASON,
        "season_type": SEASON_TYPE,
        "branch": BRANCH,
        "lineage": {
            "step14a_frozen_sha": STEP14A_FROZEN_SHA,
            "step14b_frozen_sha": STEP14B_FROZEN_SHA,
            "step14c_frozen_sha": STEP14C_FROZEN_SHA,
            "step13d_frozen_sha": STEP13D_FROZEN_SHA,
            "step13_release_id": STEP13_RELEASE_ID,
            "step13_release_content_sha256": STEP13_RELEASE_CONTENT_SHA256,
            "step14a_contract_id": STEP14A_CONTRACT_ID,
            "step14a_manifest_content_sha256": STEP14A_MANIFEST_CONTENT_SHA256,
            "step14a_sql_schema_sha256": STEP14A_SQL_SCHEMA_SHA256,
            "step14c_lease_sql_schema_sha256": STEP14C_LEASE_SQL_SCHEMA_SHA256,
        },
        "persistence_contract": {
            "postgresql_checkpoint_adapter": True,
            "append_only_checkpoint_history": True,
            "checkpoint_head_compare_and_swap": True,
            "deterministic_checkpoint_identity": True,
            "exact_controller_state_restart_handoff": True,
            "durable_restart_recovery": True,
            "cross_process_duplicate_run_guard": True,
            "durable_distributed_lease": True,
            "uuid_lease_token": True,
            "monotonic_fencing_generation": True,
            "lease_expiry_and_takeover": True,
            "stale_owner_blocked_from_renew_release_or_persist": True,
            "lease_revalidated_before_checkpoint_persist": True,
            "checkpoint_persist_after_success": True,
            "supabase_postgres_compatible": True,
            "live_database_required_for_release_manifest": False,
        },
        "activation_contract": {
            "explicit_foreground_invocation_required": True,
            "foreground_only": True,
            "global_persistence_runtime_enabled": False,
            "automatic_production_restart_activation": False,
            "background_lease_renewal_thread": False,
            "production_runtime_enabled": False,
        },
        "analytical_contract": {
            "frozen_step8_distribution_preserved": True,
            "frozen_step9_ranking_preserved": True,
            "frozen_step9_qualification_preserved": True,
            "frozen_step12_presentation_preserved": True,
            "basketball_projection_changed": False,
        },
        "safety_contract": deepcopy(SAFETY_CONTRACT),
        "phase_boundary": {
            "step14_complete": True,
            "step14a_checkpoint_contract_frozen": True,
            "step14b_database_adapter_frozen": True,
            "step14c_restart_and_lease_frozen": True,
            "production_activation_not_started": True,
            "global_persistence_autostart_not_started": True,
            "public_persistence_api_not_started": True,
            "supabase_rest_write_not_started": True,
            "wagering_not_started": True,
        },
    }
    hash_surface = deepcopy(result)
    hash_surface.pop("generated_at_utc", None)
    result["release_content_sha256"] = _canonical_hash(hash_surface)
    _assert_release_integrity(env)
    return result


__all__ = [
    "BRANCH", "DEFAULT_ENABLED", "INTEGRATION_VERSION", "RELEASE_ID", "SAFETY_CONTRACT",
    "SCHEMA_VERSION", "SEASON", "SEASON_TYPE", "SOURCE", "STEP13_RELEASE_CONTENT_SHA256",
    "STEP13_RELEASE_ID", "STEP14A_FROZEN_SHA", "STEP14A_MANIFEST_CONTENT_SHA256",
    "STEP14A_SQL_SCHEMA_SHA256", "STEP14B_FROZEN_SHA", "STEP14C_FROZEN_SHA",
    "STEP14C_LEASE_SQL_SCHEMA_SHA256", "STEP14D_FINAL_PERSISTENCE_FREEZE_ENABLED_ENV",
    "WNBAStep14FinalFreezeDisabledError", "WNBAStep14FinalFreezeIntegrityError",
    "build_step14d_release_manifest", "step14d_final_persistence_freeze_enabled",
]
