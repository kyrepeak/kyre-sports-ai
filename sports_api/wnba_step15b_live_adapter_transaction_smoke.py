"""WNBA Step 15B: live PostgreSQL transaction smoke over frozen Step-14 SQL.

Step 15B certifies real PostgreSQL transaction semantics against the Supabase
project prepared in Step 15A. The live smoke exercises the exact SQL behavior
owned by frozen Step 14B/14C: checkpoint create/load/idempotency/advance/CAS
rollback plus lease acquire/contention/renew/expiry takeover/fencing/release.

The connected Supabase management surface does not expose the database password
required by ``KYRE_DATABASE_URL``, so the live smoke executes the frozen adapter
SQL semantics through controlled Supabase SQL execution. The psycopg adapter code
itself remains frozen and separately regression-tested. No production scheduler,
global persistence runtime, background worker, public persistence API, wagering,
or model/ranking mutation is activated here.
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

from sports_api import wnba_step14b_database_checkpoint_adapter as step14b
from sports_api import wnba_step14c_durable_restart_lease as step14c
from sports_api import wnba_step14_release_freeze as step14d
from sports_api import wnba_step15a_live_postgres_preflight as step15a

SOURCE = "Kyre Sports API WNBA Step 15B live adapter transaction smoke"
SCHEMA_VERSION = "wnba_step_15b_live_adapter_transaction_smoke_v1"
INTEGRATION_VERSION = "wnba_step15b_live_postgres_transaction_smoke_v1"
BRANCH = "wnba-step15b-live-adapter-smoke-20260828"
SEASON = 2026
SEASON_TYPE = "Regular Season"

STEP15A_CERTIFIED_SHA = "9cc30b96c4583f6b18306910ca4a7fb70d93c325"
STEP15A_PREFLIGHT_CONTENT_SHA256 = "33a2c431a202b791180d6cca0aa8ad12f46ca6d561749c5753918f90b145223e"
STEP14D_FROZEN_SHA = "d5a7378d94fb1aa51a6bc5fbf5e5c0384f34a9d6"
STEP14_RELEASE_CONTENT_SHA256 = "70082ab06a58ddee4dce567626ff83bc64e67bf89f04e5f402d820a414b25e59"

LIVE_EVIDENCE_PATH = "sports_api/certification/wnba_step15b_live_adapter_transaction_smoke_evidence.json"
LIVE_EVIDENCE_CONTENT_SHA256 = "d99bc29535f4bfc09a6d38858beb9b8faf8646fdf37b01aa3a86a9b18c4ff75c"
EXPECTED_SUPABASE_PROJECT_REF = "jqajcdckalsfizbvngiu"
EXPECTED_SMOKE_SLATE_DATE = "2026-01-15"
EXPECTED_CHECKPOINT_KEY = "wnba:runtime:2026:regular-season:2026-01-15"
EXPECTED_LEASE_KEY = EXPECTED_CHECKPOINT_KEY + ":scheduler-lease"

STEP15B_LIVE_ADAPTER_SMOKE_ENABLED_ENV = "WNBA_STEP15B_LIVE_ADAPTER_SMOKE_ENABLED"

DEFAULT_ENABLED = False
LIVE_DATABASE_TRANSACTION_SMOKE_CERTIFIED = True
FROZEN_ADAPTER_SQL_SEMANTICS_CERTIFIED = True
CHECKPOINT_CREATE_LOAD_IDEMPOTENCY_CERTIFIED = True
CHECKPOINT_ADVANCE_CAS_CERTIFIED = True
STALE_CHECKPOINT_TRANSACTION_ROLLBACK_CERTIFIED = True
LEASE_CONTENTION_CERTIFIED = True
LEASE_RENEW_CERTIFIED = True
LEASE_EXPIRY_TAKEOVER_CERTIFIED = True
LEASE_FENCING_CERTIFIED = True
LEASE_RELEASE_CERTIFIED = True
LIVE_SMOKE_CLEANUP_CERTIFIED = True
DIRECT_PSYCOG_LIVE_CONNECTION_CERTIFIED = False

PRODUCTION_ACTIVATION_ALLOWED = False
GLOBAL_PERSISTENCE_RUNTIME_ENABLED = False
AUTOMATIC_RESTART_ACTIVATION_ALLOWED = False
BACKGROUND_DAEMON_ALLOWED = False
BACKGROUND_THREAD_ALLOWED = False
PUBLIC_PERSISTENCE_API_ALLOWED = False
SUPABASE_REST_WRITE_ALLOWED = False
WAGERING_ALLOWED = False
AUTHENTICATION_ALLOWED = False
COOKIES_ALLOWED = False
BASKETBALL_MODEL_MUTATION_ALLOWED = False
RANKING_MUTATION_ALLOWED = False
RUNTIME_MUTATION_ALLOWED = False

SAFETY_CONTRACT = {
    "default_enablement": False,
    "production_runtime": False,
    "production_activation": False,
    "global_persistence_runtime": False,
    "automatic_restart_activation": False,
    "background_daemon": False,
    "background_thread": False,
    "public_persistence_api": False,
    "supabase_rest_write": False,
    "wager_action": False,
    "authentication": False,
    "cookies": False,
    "basketball_model_change": False,
    "step8_distribution_change": False,
    "step9_ranking_change": False,
    "step9_qualification_change": False,
    "step12_presentation_change": False,
    "runtime_mutation": False,
}

SQL_FINGERPRINTS = {
    "step14b_head_select_for_update": "4e65fd96a8d4446a691ae84b138a37b912bcf652beafae6fb0b1b43f3967f59b",
    "step14b_insert_history": "8ca8275f451163805051b6d0fa864536954e5f0c35ef875043aad2e0965039cb",
    "step14b_insert_head": "c6fcb1bf96decf7e8db6db9226b6ea6b6a56664212cdb19d8a218bff3f9d5ebf",
    "step14b_update_head": "8828a15e2fd1dec911f3d571d204b09c9e7ed5af011d1b807288be224a171a8b",
    "step14c_acquire_lease": "4b156a13601bd722b4eeec752aa893011040a2b8eb9b4b144b22e8e8828e9a6e",
    "step14c_renew_lease": "e2b404afd3ae967b28f033d79b5be45aaf6ab328bd521ca9876a6982f605b2c9",
    "step14c_release_lease": "37f10b94548027d6ab243a96342697bfea1c3d65538a2aea66dbc8529d4aa56e",
}

_FORBIDDEN_TRUE_ENV_KEYS = (
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_PERSISTENCE_ENABLED",
    "WNBA_SUPABASE_WRITE_ENABLED",
    "WNBA_WAGERING_ENABLED",
    "WNBA_PUBLIC_STEP11E_FASTAPI_ENABLED",
    "WNBA_STEP12_SCHEDULER_ENABLED",
)

_REQUIRED_TRUE_ENV_KEYS = (
    "WNBA_STEP15A_LIVE_POSTGRES_PREFLIGHT_ENABLED",
    "WNBA_STEP14D_FINAL_PERSISTENCE_FREEZE_ENABLED",
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


class WNBAStep15BLiveSmokeDisabledError(RuntimeError):
    pass


class WNBAStep15BLiveSmokeIntegrityError(RuntimeError):
    pass


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled"
    }


def step15b_live_adapter_smoke_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(STEP15B_LIVE_ADAPTER_SMOKE_ENABLED_ENV))


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


def _sql_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _evidence_hash_surface(evidence: Mapping[str, Any]) -> dict[str, Any]:
    result = deepcopy(dict(evidence))
    result.pop("observed_at_utc", None)
    result.pop("evidence_content_sha256", None)
    return result


def load_step15b_live_evidence(path: str = LIVE_EVIDENCE_PATH) -> dict[str, Any]:
    try:
        evidence = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WNBAStep15BLiveSmokeIntegrityError(
            "Step 15B cannot load live transaction smoke evidence."
        ) from exc
    if not isinstance(evidence, dict):
        raise WNBAStep15BLiveSmokeIntegrityError("Step 15B evidence must be an object.")
    observed = str(evidence.get("evidence_content_sha256") or "").lower()
    expected = _canonical_hash(_evidence_hash_surface(evidence))
    if observed != expected or expected != LIVE_EVIDENCE_CONTENT_SHA256:
        raise WNBAStep15BLiveSmokeIntegrityError("Step 15B evidence content hash drift.")
    return evidence


def validate_frozen_sql_fingerprints() -> dict[str, str]:
    observed = {
        "step14b_head_select_for_update": _sql_hash(step14b._HEAD_SELECT_FOR_UPDATE_SQL),
        "step14b_insert_history": _sql_hash(step14b._INSERT_HISTORY_SQL),
        "step14b_insert_head": _sql_hash(step14b._INSERT_HEAD_SQL),
        "step14b_update_head": _sql_hash(step14b._UPDATE_HEAD_SQL),
        "step14c_acquire_lease": _sql_hash(step14c._ACQUIRE_LEASE_SQL),
        "step14c_renew_lease": _sql_hash(step14c._RENEW_LEASE_SQL),
        "step14c_release_lease": _sql_hash(step14c._RELEASE_LEASE_SQL),
    }
    if observed != SQL_FINGERPRINTS:
        raise WNBAStep15BLiveSmokeIntegrityError("Step 15B frozen adapter SQL drift.")
    return observed


def validate_step15b_live_evidence(evidence: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(evidence, Mapping):
        raise WNBAStep15BLiveSmokeIntegrityError("Step 15B evidence must be an object.")
    if evidence.get("data_type") != "wnba_step15b_live_adapter_transaction_smoke_evidence":
        raise WNBAStep15BLiveSmokeIntegrityError("Step 15B evidence data_type drift.")

    project = evidence.get("supabase_project")
    lineage = evidence.get("frozen_lineage")
    boundary = evidence.get("execution_boundary")
    scope = evidence.get("smoke_scope")
    checkpoint = evidence.get("checkpoint_smoke")
    lease = evidence.get("lease_smoke")
    cleanup = evidence.get("cleanup")
    if not all(isinstance(x, Mapping) for x in (
        project, lineage, boundary, scope, checkpoint, lease, cleanup
    )):
        raise WNBAStep15BLiveSmokeIntegrityError("Step 15B evidence object shape drift.")

    if (
        project.get("ref") != EXPECTED_SUPABASE_PROJECT_REF
        or project.get("status") != "ACTIVE_HEALTHY"
        or str(project.get("postgres_engine")) != "17"
    ):
        raise WNBAStep15BLiveSmokeIntegrityError("Step 15B live project identity/health drift.")
    if (
        lineage.get("step15a_certified_sha") != STEP15A_CERTIFIED_SHA
        or lineage.get("step15a_preflight_content_sha256") != STEP15A_PREFLIGHT_CONTENT_SHA256
        or lineage.get("step14d_frozen_sha") != STEP14D_FROZEN_SHA
        or lineage.get("step14_release_content_sha256") != STEP14_RELEASE_CONTENT_SHA256
    ):
        raise WNBAStep15BLiveSmokeIntegrityError("Step 15B frozen lineage evidence drift.")
    if (
        scope.get("slate_date") != EXPECTED_SMOKE_SLATE_DATE
        or scope.get("checkpoint_key") != EXPECTED_CHECKPOINT_KEY
        or scope.get("lease_key") != EXPECTED_LEASE_KEY
    ):
        raise WNBAStep15BLiveSmokeIntegrityError("Step 15B smoke scope drift.")

    required_boundary_true = (
        "live_database_used",
        "frozen_adapter_sql_semantics_executed_live",
    )
    if any(boundary.get(key) is not True for key in required_boundary_true):
        raise WNBAStep15BLiveSmokeIntegrityError("Step 15B live SQL execution evidence missing.")
    required_boundary_false = (
        "python_psycopg_adapter_connected_directly",
        "github_actions_live_database_credentials_used",
        "production_scheduler_started",
        "global_persistence_runtime_started",
        "background_worker_started",
        "public_persistence_api_exposed",
        "wagering_enabled",
    )
    if any(boundary.get(key) is not False for key in required_boundary_false):
        raise WNBAStep15BLiveSmokeIntegrityError("Step 15B execution safety boundary drift.")

    checkpoint_true = (
        "baseline_all_step14_tables_empty",
        "version_1_created",
        "load_round_trip_exact",
        "version_2_advanced",
        "stale_cas_rejected",
        "stale_transaction_rolled_back",
    )
    if any(checkpoint.get(key) is not True for key in checkpoint_true):
        raise WNBAStep15BLiveSmokeIntegrityError("Step 15B checkpoint smoke failure.")
    if checkpoint.get("idempotent_repeat_history_rows") != 1:
        raise WNBAStep15BLiveSmokeIntegrityError("Step 15B idempotency evidence drift.")
    if checkpoint.get("history_rows_after_advance") != 2:
        raise WNBAStep15BLiveSmokeIntegrityError("Step 15B append-only history evidence drift.")
    if checkpoint.get("history_rows_after_stale_attempt") != 2:
        raise WNBAStep15BLiveSmokeIntegrityError("Step 15B stale rollback history drift.")
    if checkpoint.get("stale_history_row_survived") is not False:
        raise WNBAStep15BLiveSmokeIntegrityError("Step 15B stale history row survived unexpectedly.")
    if checkpoint.get("stale_expected_version") != 1 or checkpoint.get("current_version_during_stale_attempt") != 2:
        raise WNBAStep15BLiveSmokeIntegrityError("Step 15B CAS version evidence drift.")

    if lease.get("initial_acquire_generation") != 1:
        raise WNBAStep15BLiveSmokeIntegrityError("Step 15B initial lease generation drift.")
    if lease.get("duplicate_active_acquire_rows") != 0:
        raise WNBAStep15BLiveSmokeIntegrityError("Step 15B duplicate lease was not blocked.")
    if lease.get("owner_a_renew_succeeded") is not True:
        raise WNBAStep15BLiveSmokeIntegrityError("Step 15B lease renew evidence failed.")
    if lease.get("wrong_owner_renew_rows") != 0:
        raise WNBAStep15BLiveSmokeIntegrityError("Step 15B wrong owner renewed lease.")
    if lease.get("test_only_expiry_forced") is not True or lease.get("takeover_generation") != 2:
        raise WNBAStep15BLiveSmokeIntegrityError("Step 15B lease takeover/fencing drift.")
    if lease.get("stale_owner_release_rows") != 0:
        raise WNBAStep15BLiveSmokeIntegrityError("Step 15B stale owner released active lease.")
    if lease.get("current_owner_release_succeeded") is not True:
        raise WNBAStep15BLiveSmokeIntegrityError("Step 15B current owner release failed.")

    if cleanup.get("live_step14_tables_returned_to_empty_state") is not True:
        raise WNBAStep15BLiveSmokeIntegrityError("Step 15B cleanup was not certified.")
    for key in (
        "checkpoint_heads_rows_after_cleanup",
        "checkpoint_history_rows_after_cleanup",
        "lease_rows_after_cleanup",
    ):
        if cleanup.get(key) != 0:
            raise WNBAStep15BLiveSmokeIntegrityError(f"Step 15B cleanup drift: {key}.")
    return deepcopy(dict(evidence))


def _assert_integrity(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    source = dict(os.environ if env is None else env)
    if not step15b_live_adapter_smoke_enabled(source):
        raise WNBAStep15BLiveSmokeDisabledError(
            f"Step 15B requires {STEP15B_LIVE_ADAPTER_SMOKE_ENABLED_ENV}=true."
        )
    bad = [name for name in _FORBIDDEN_TRUE_ENV_KEYS if _truthy(source.get(name))]
    if bad:
        raise WNBAStep15BLiveSmokeDisabledError(
            "Step 15B refuses production/global-persistence/write/wagering switches: "
            + ", ".join(bad)
        )
    missing = [name for name in _REQUIRED_TRUE_ENV_KEYS if not _truthy(source.get(name))]
    if missing:
        raise WNBAStep15BLiveSmokeDisabledError(
            "Step 15B requires frozen Step-15A/14/13/12 gates: " + ", ".join(missing)
        )

    parent = step15a.build_step15a_live_preflight_manifest(
        env=source,
        generated_at_utc="2026-08-28T19:20:00+00:00",
    )
    if parent.get("preflight_content_sha256") != STEP15A_PREFLIGHT_CONTENT_SHA256:
        raise WNBAStep15BLiveSmokeIntegrityError("Step 15B Step-15A preflight hash drift.")
    if step14d.RELEASE_ID != step15a.STEP14_RELEASE_ID:
        raise WNBAStep15BLiveSmokeIntegrityError("Step 15B Step-14 release identity drift.")

    own_false = (
        DEFAULT_ENABLED,
        DIRECT_PSYCOG_LIVE_CONNECTION_CERTIFIED,
        PRODUCTION_ACTIVATION_ALLOWED,
        GLOBAL_PERSISTENCE_RUNTIME_ENABLED,
        AUTOMATIC_RESTART_ACTIVATION_ALLOWED,
        BACKGROUND_DAEMON_ALLOWED,
        BACKGROUND_THREAD_ALLOWED,
        PUBLIC_PERSISTENCE_API_ALLOWED,
        SUPABASE_REST_WRITE_ALLOWED,
        WAGERING_ALLOWED,
        AUTHENTICATION_ALLOWED,
        COOKIES_ALLOWED,
        BASKETBALL_MODEL_MUTATION_ALLOWED,
        RANKING_MUTATION_ALLOWED,
        RUNTIME_MUTATION_ALLOWED,
    )
    if any(value is not False for value in own_false):
        raise WNBAStep15BLiveSmokeIntegrityError("Step 15B safety/driver-boundary constant drift.")
    own_true = (
        LIVE_DATABASE_TRANSACTION_SMOKE_CERTIFIED,
        FROZEN_ADAPTER_SQL_SEMANTICS_CERTIFIED,
        CHECKPOINT_CREATE_LOAD_IDEMPOTENCY_CERTIFIED,
        CHECKPOINT_ADVANCE_CAS_CERTIFIED,
        STALE_CHECKPOINT_TRANSACTION_ROLLBACK_CERTIFIED,
        LEASE_CONTENTION_CERTIFIED,
        LEASE_RENEW_CERTIFIED,
        LEASE_EXPIRY_TAKEOVER_CERTIFIED,
        LEASE_FENCING_CERTIFIED,
        LEASE_RELEASE_CERTIFIED,
        LIVE_SMOKE_CLEANUP_CERTIFIED,
    )
    if any(value is not True for value in own_true):
        raise WNBAStep15BLiveSmokeIntegrityError("Step 15B certification constant drift.")

    validate_frozen_sql_fingerprints()
    return validate_step15b_live_evidence(load_step15b_live_evidence())


def build_step15b_live_smoke_manifest(
    *, env: Mapping[str, str] | None = None, generated_at_utc: str | None = None
) -> dict[str, Any]:
    evidence = _assert_integrity(env)
    generated = generated_at_utc or datetime.now(timezone.utc).isoformat()
    result = {
        "data_type": "wnba_step15b_live_adapter_transaction_smoke",
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        "integration_version": INTEGRATION_VERSION,
        "generated_at_utc": generated,
        "season": SEASON,
        "season_type": SEASON_TYPE,
        "branch": BRANCH,
        "lineage": {
            "step15a_certified_sha": STEP15A_CERTIFIED_SHA,
            "step15a_preflight_content_sha256": STEP15A_PREFLIGHT_CONTENT_SHA256,
            "step14d_frozen_sha": STEP14D_FROZEN_SHA,
            "step14_release_content_sha256": STEP14_RELEASE_CONTENT_SHA256,
            "live_evidence_content_sha256": LIVE_EVIDENCE_CONTENT_SHA256,
        },
        "sql_contract": {
            "frozen_adapter_sql_semantics_certified": True,
            "sql_fingerprints": deepcopy(SQL_FINGERPRINTS),
            "direct_psycopg_live_connection_certified": False,
            "direct_psycopg_live_connection_reason": evidence["execution_boundary"]["reason_direct_adapter_not_connected"],
        },
        "checkpoint_contract": {
            "create_v1": True,
            "exact_load_round_trip": True,
            "idempotent_repeat": True,
            "append_only_advance_v2": True,
            "head_compare_and_swap": True,
            "stale_writer_rejected": True,
            "failed_stale_transaction_rolled_back": True,
        },
        "lease_contract": {
            "initial_generation": 1,
            "duplicate_active_owner_blocked": True,
            "valid_owner_renewed": True,
            "wrong_owner_renew_blocked": True,
            "expired_lease_takeover": True,
            "takeover_generation": 2,
            "stale_owner_release_blocked": True,
            "current_owner_release_succeeded": True,
        },
        "cleanup_contract": deepcopy(evidence["cleanup"]),
        "activation_contract": {
            "live_database_transaction_smoke_completed": True,
            "live_scheduler_started": False,
            "global_persistence_runtime_enabled": False,
            "automatic_restart_activation": False,
            "background_worker_started": False,
            "public_persistence_api_exposed": False,
            "supabase_rest_write_path_enabled": False,
            "production_runtime_enabled": False,
        },
        "safety_contract": deepcopy(SAFETY_CONTRACT),
        "phase_boundary": {
            "step15b_complete": True,
            "live_sql_transaction_semantics_complete": True,
            "live_tables_clean_after_smoke": True,
            "direct_psycopg_secret_in_ci_not_required": True,
            "production_runtime_activation_not_started": True,
            "global_persistence_autostart_not_started": True,
            "final_step15_freeze_not_started": True,
        },
    }
    surface = deepcopy(result)
    surface.pop("generated_at_utc", None)
    result["smoke_content_sha256"] = _canonical_hash(surface)
    _assert_integrity(env)
    return result


__all__ = [
    "BRANCH",
    "DEFAULT_ENABLED",
    "DIRECT_PSYCOG_LIVE_CONNECTION_CERTIFIED",
    "EXPECTED_CHECKPOINT_KEY",
    "EXPECTED_LEASE_KEY",
    "EXPECTED_SMOKE_SLATE_DATE",
    "FROZEN_ADAPTER_SQL_SEMANTICS_CERTIFIED",
    "INTEGRATION_VERSION",
    "LIVE_EVIDENCE_CONTENT_SHA256",
    "LIVE_EVIDENCE_PATH",
    "SAFETY_CONTRACT",
    "SCHEMA_VERSION",
    "SOURCE",
    "SQL_FINGERPRINTS",
    "STEP15A_CERTIFIED_SHA",
    "STEP15A_PREFLIGHT_CONTENT_SHA256",
    "STEP15B_LIVE_ADAPTER_SMOKE_ENABLED_ENV",
    "WNBAStep15BLiveSmokeDisabledError",
    "WNBAStep15BLiveSmokeIntegrityError",
    "build_step15b_live_smoke_manifest",
    "load_step15b_live_evidence",
    "step15b_live_adapter_smoke_enabled",
    "validate_frozen_sql_fingerprints",
    "validate_step15b_live_evidence",
]
