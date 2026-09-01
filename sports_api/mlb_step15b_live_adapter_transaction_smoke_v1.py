"""MLB Step 15B — certified live PostgreSQL adapter transaction smoke.

Step 15A proved that the real PostgreSQL environment matches the frozen Step-14
schema. Step 15B advances one controlled boundary: the frozen Step 14B checkpoint
SQL and Step 14C lease SQL semantics were executed against the real Supabase
PostgreSQL database inside one explicit transaction and then rolled back.

The smoke covers checkpoint create/load/idempotency, append-only V2 advance,
head compare-and-swap failure with stale-history rollback, lease acquisition,
contention, renewal, expiry takeover, fencing, and release. The outer rollback
returns all three MLB persistence tables to their pre-smoke empty state.

This module does not start the scheduler, execute a runtime cycle, persist a
production checkpoint, enable automatic restart, expose a public persistence
API, call a provider/sportsbook, or activate production.
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

from sports_api import mlb_step14b_database_checkpoint_adapter_v1 as step14b
from sports_api import mlb_step14c_durable_restart_lease_v1 as step14c
from sports_api import mlb_step14_final_persistence_freeze_v1 as step14d
from sports_api import mlb_step15a_live_postgresql_preflight_v1 as step15a
from sports_api.mlb_step9_final_freeze_v1 import PROTECTED_INVARIANTS

DATA_TYPE = "mlb_step15b_live_adapter_transaction_smoke_v1"
SCHEMA_VERSION = 1
SMOKE_VERSION = "mlb_step15b_live_postgresql_transaction_smoke_2026_v1"
SMOKE_STATUS = "STEP15B_LIVE_ADAPTER_TRANSACTION_SMOKE_READY"
FINAL_CERTIFICATION_MARKER = "MLB_STEP15B_LIVE_ADAPTER_TRANSACTION_SMOKE_GREEN"
RUNTIME_MODE = "SHADOW_ONLY"

STEP15B_BASE_MAIN_SHA = "4242f2c2a3b3465b38f0e80b041d0ee4d8f6ab20"
STEP15A_SOURCE_BLOB_SHA = "9000c54df1a9d1bac4aeb143e354fc554129725c"
STEP14D_SOURCE_BLOB_SHA = "8d346c2fb3abf71742c048d5489ac88124b990b6"

LIVE_EVIDENCE_PATH = (
    "sports_api/certification/mlb_step15b_live_adapter_transaction_smoke_evidence.json"
)
LIVE_EVIDENCE_CONTENT_SHA256 = (
    "e167582075d845b807505a3988fad35fb1a29a7aa3e18de5eb843971aba30af7"
)
EXPECTED_SUPABASE_PROJECT_REF = "jqajcdckalsfizbvngiu"
EXPECTED_SMOKE_SLATE_DATE = "2026-01-15"
EXPECTED_CHECKPOINT_KEY = "mlb:runtime:2026:regular-season:2026-01-15"
EXPECTED_LEASE_KEY = EXPECTED_CHECKPOINT_KEY + ":scheduler-lease"

STEP15B_LIVE_ADAPTER_SMOKE_ENABLED_ENV = "MLB_STEP15B_LIVE_ADAPTER_SMOKE_ENABLED"

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
OUTER_TRANSACTION_ROLLBACK_CLEANUP_CERTIFIED = True
DIRECT_PSYCOG_LIVE_CONNECTION_CERTIFIED = False

PRODUCTION_ACTIVATION_ALLOWED = False
PRODUCTION_SCHEDULER_ALLOWED = False
GLOBAL_PERSISTENCE_RUNTIME_ENABLED = False
AUTOMATIC_RESTART_EXECUTION_ALLOWED = False
BACKGROUND_WORKER_ALLOWED = False
PUBLIC_PERSISTENCE_API_ALLOWED = False
ACTIONABLE_OUTPUT_ALLOWED = False
PROVIDER_NETWORK_CALLS_ALLOWED = False
SPORTSBOOK_NETWORK_CALLS_ALLOWED = False
SCHEMA_AUTO_APPLY_ALLOWED = False

SQL_FINGERPRINTS = {
    "step14b_head_select_for_update": "ac5088c3227812b3ee38ef4547ce0f3262d074deeaa82f72cf206e6edf4b041e",
    "step14b_insert_history": "c7233dfb58db976c75e8e072948a4f28d31de44eb1122ffb15cbd9190f9f78da",
    "step14b_insert_head": "e61ba008c57a622f50f57232be1349274de2a456ce5fd7a68f5799e3757e84ef",
    "step14b_update_head": "50d7b781874d09dfb571b725cc576e8c1ac44d883eb00d0835a224685772d79a",
    "step14c_acquire_lease": "0acfe3a6182cb229712d56afa957ef7e7f45362868800cf2802aef7cc858edf9",
    "step14c_renew_lease": "ef5ddbf28498ea3a0a42bcda0f8b40cf8f4841633caca3be1a19d67b82197f2a",
    "step14c_release_lease": "e7930ceac348f9d69be4b841aa96db0d668b69e0e00f8d2715f599f4f5708173",
}

_FORBIDDEN_TRUE_ENV_KEYS = (
    "MLB_PRODUCTION_RUNTIME_ENABLED",
    "MLB_PRODUCTION_SCHEDULER_ENABLED",
    "MLB_ACTIONABLE_OUTPUT_ENABLED",
    "MLB_WAGERING_ENABLED",
    "MLB_SUPABASE_REST_WRITE_ENABLED",
)


class MLBStep15BLiveSmokeDisabledError(RuntimeError):
    """Raised unless the isolated Step15B certification gate is explicit."""


class MLBStep15BLiveSmokeIntegrityError(RuntimeError):
    """Raised when live evidence, frozen SQL, or parent lineage drifts."""


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled"
    }


def _hash(value: Any) -> str:
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


def step15b_live_adapter_smoke_enabled(
    env: Mapping[str, str] | None = None,
) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(STEP15B_LIVE_ADAPTER_SMOKE_ENABLED_ENV))


def _evidence_hash_surface(evidence: Mapping[str, Any]) -> dict[str, Any]:
    result = deepcopy(dict(evidence))
    result.pop("observed_at_utc", None)
    result.pop("evidence_content_sha256", None)
    return result


def load_live_smoke_evidence(path: str = LIVE_EVIDENCE_PATH) -> dict[str, Any]:
    try:
        evidence = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MLBStep15BLiveSmokeIntegrityError(
            "Step 15B could not load live transaction smoke evidence"
        ) from exc
    if not isinstance(evidence, dict):
        raise MLBStep15BLiveSmokeIntegrityError("Step 15B evidence must be an object")
    observed = str(evidence.get("evidence_content_sha256") or "").lower()
    expected = _hash(_evidence_hash_surface(evidence))
    if observed != expected or expected != LIVE_EVIDENCE_CONTENT_SHA256:
        raise MLBStep15BLiveSmokeIntegrityError("Step 15B live evidence hash drift")
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
        raise MLBStep15BLiveSmokeIntegrityError("Step 15B frozen adapter SQL drift")
    return observed


def validate_live_smoke_evidence(evidence: Mapping[str, Any]) -> dict[str, Any]:
    if evidence.get("data_type") != "mlb_step15b_live_adapter_transaction_smoke_evidence":
        raise MLBStep15BLiveSmokeIntegrityError("Step 15B evidence data_type drift")

    project = evidence.get("supabase_project")
    lineage = evidence.get("frozen_lineage")
    boundary = evidence.get("execution_boundary")
    scope = evidence.get("smoke_scope")
    checkpoint = evidence.get("checkpoint_smoke")
    lease = evidence.get("lease_smoke")
    cleanup = evidence.get("cleanup")
    values = (project, lineage, boundary, scope, checkpoint, lease, cleanup)
    if not all(isinstance(value, Mapping) for value in values):
        raise MLBStep15BLiveSmokeIntegrityError("Step 15B evidence shape drift")

    if (
        project.get("ref") != EXPECTED_SUPABASE_PROJECT_REF
        or project.get("database_name") != "postgres"
        or project.get("postgres_version") != "17.6"
        or project.get("primary") is not True
    ):
        raise MLBStep15BLiveSmokeIntegrityError("Step 15B live database identity drift")

    if (
        lineage.get("step15a_merge_sha") != STEP15B_BASE_MAIN_SHA
        or lineage.get("step15a_source_blob_sha") != STEP15A_SOURCE_BLOB_SHA
        or lineage.get("step15a_final_marker") != step15a.FINAL_CERTIFICATION_MARKER
        or lineage.get("step14d_source_blob_sha") != STEP14D_SOURCE_BLOB_SHA
    ):
        raise MLBStep15BLiveSmokeIntegrityError("Step 15B frozen lineage drift")

    if (
        scope.get("slate_date") != EXPECTED_SMOKE_SLATE_DATE
        or scope.get("checkpoint_key") != EXPECTED_CHECKPOINT_KEY
        or scope.get("lease_key") != EXPECTED_LEASE_KEY
    ):
        raise MLBStep15BLiveSmokeIntegrityError("Step 15B smoke scope drift")

    required_true = (
        "live_database_used",
        "frozen_adapter_sql_semantics_executed_live",
        "connected_supabase_sql_surface_used",
        "single_explicit_transaction_used",
        "transaction_rolled_back",
    )
    if any(boundary.get(key) is not True for key in required_true):
        raise MLBStep15BLiveSmokeIntegrityError("Step 15B live execution evidence missing")
    required_false = (
        "python_psycopg_adapter_connected_directly",
        "production_scheduler_started",
        "global_persistence_runtime_started",
        "background_worker_started",
        "public_persistence_api_exposed",
    )
    if any(boundary.get(key) is not False for key in required_false):
        raise MLBStep15BLiveSmokeIntegrityError("Step 15B execution boundary drift")
    if any(boundary.get(key) != 0 for key in (
        "provider_calls", "sportsbook_calls", "production_activation"
    )):
        raise MLBStep15BLiveSmokeIntegrityError("Step 15B forbidden execution occurred")

    checkpoint_true = (
        "baseline_all_step14_tables_empty",
        "version_1_created",
        "load_round_trip_exact",
        "version_2_advanced",
        "stale_cas_rejected",
        "stale_transaction_rolled_back",
    )
    if any(checkpoint.get(key) is not True for key in checkpoint_true):
        raise MLBStep15BLiveSmokeIntegrityError("Step 15B checkpoint smoke failure")
    expected_checkpoint = {
        "idempotent_repeat_history_rows": 1,
        "history_rows_after_advance": 2,
        "history_rows_after_stale_attempt": 2,
        "stale_history_row_survived": False,
        "stale_expected_version": 1,
        "current_version_during_stale_attempt": 2,
    }
    if any(checkpoint.get(key) != value for key, value in expected_checkpoint.items()):
        raise MLBStep15BLiveSmokeIntegrityError("Step 15B checkpoint evidence drift")

    expected_lease = {
        "initial_acquire_generation": 1,
        "duplicate_active_acquire_rows": 0,
        "owner_a_renew_succeeded": True,
        "wrong_owner_renew_rows": 0,
        "test_only_expiry_forced": True,
        "takeover_generation": 2,
        "stale_owner_release_rows": 0,
        "current_owner_release_succeeded": True,
    }
    if any(lease.get(key) != value for key, value in expected_lease.items()):
        raise MLBStep15BLiveSmokeIntegrityError("Step 15B lease evidence drift")

    if cleanup.get("cleanup_method") != "outer_transaction_rollback":
        raise MLBStep15BLiveSmokeIntegrityError("Step 15B cleanup method drift")
    if cleanup.get("live_step14_tables_returned_to_empty_state") is not True:
        raise MLBStep15BLiveSmokeIntegrityError("Step 15B cleanup not certified")
    for key in (
        "checkpoint_history_rows_after_cleanup",
        "checkpoint_heads_rows_after_cleanup",
        "lease_rows_after_cleanup",
    ):
        if cleanup.get(key) != 0:
            raise MLBStep15BLiveSmokeIntegrityError(f"Step 15B cleanup drift: {key}")
    if cleanup.get("marker") != "MLB_STEP15B_LIVE_TRANSACTION_SMOKE_EXECUTED":
        raise MLBStep15BLiveSmokeIntegrityError("Step 15B live marker drift")
    return deepcopy(dict(evidence))


def _assert_integrity(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    source = os.environ if env is None else env
    if not step15b_live_adapter_smoke_enabled(source):
        raise MLBStep15BLiveSmokeDisabledError(
            f"Step 15B requires {STEP15B_LIVE_ADAPTER_SMOKE_ENABLED_ENV}=true"
        )
    forbidden = [key for key in _FORBIDDEN_TRUE_ENV_KEYS if _truthy(source.get(key))]
    if forbidden:
        raise MLBStep15BLiveSmokeDisabledError(
            "Step 15B refuses production/actionable switches: " + ", ".join(forbidden)
        )

    if step15a.FINAL_CERTIFICATION_MARKER != "MLB_STEP15A_LIVE_POSTGRESQL_PREFLIGHT_GREEN":
        raise MLBStep15BLiveSmokeIntegrityError("Step 15A marker drift")
    if step14d.FINAL_CERTIFICATION_MARKER != "MLB_STEP14D_FINAL_PERSISTENCE_FREEZE_GREEN":
        raise MLBStep15BLiveSmokeIntegrityError("Step 14D marker drift")

    required_true = (
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
        OUTER_TRANSACTION_ROLLBACK_CLEANUP_CERTIFIED,
    )
    if any(value is not True for value in required_true):
        raise MLBStep15BLiveSmokeIntegrityError("Step 15B certification constant drift")

    forbidden_capabilities = (
        DEFAULT_ENABLED,
        DIRECT_PSYCOG_LIVE_CONNECTION_CERTIFIED,
        PRODUCTION_ACTIVATION_ALLOWED,
        PRODUCTION_SCHEDULER_ALLOWED,
        GLOBAL_PERSISTENCE_RUNTIME_ENABLED,
        AUTOMATIC_RESTART_EXECUTION_ALLOWED,
        BACKGROUND_WORKER_ALLOWED,
        PUBLIC_PERSISTENCE_API_ALLOWED,
        ACTIONABLE_OUTPUT_ALLOWED,
        PROVIDER_NETWORK_CALLS_ALLOWED,
        SPORTSBOOK_NETWORK_CALLS_ALLOWED,
        SCHEMA_AUTO_APPLY_ALLOWED,
    )
    if any(value is not False for value in forbidden_capabilities):
        raise MLBStep15BLiveSmokeIntegrityError("Step 15B safety constant drift")
    for key, value in PROTECTED_INVARIANTS.items():
        if value is not False:
            raise MLBStep15BLiveSmokeIntegrityError(
                f"Step 15B protected invariant drift: {key}"
            )

    validate_frozen_sql_fingerprints()
    return validate_live_smoke_evidence(load_live_smoke_evidence())


def live_adapter_transaction_smoke_manifest(
    *, env: Mapping[str, str] | None = None, generated_at_utc: str | None = None
) -> dict[str, Any]:
    evidence = _assert_integrity(env)
    generated = generated_at_utc or datetime.now(timezone.utc).isoformat()
    manifest: dict[str, Any] = {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "step15b_base_main_sha": STEP15B_BASE_MAIN_SHA,
        "step15a_source_blob_sha": STEP15A_SOURCE_BLOB_SHA,
        "step14d_source_blob_sha": STEP14D_SOURCE_BLOB_SHA,
        "step15a_final_certification_marker_required": step15a.FINAL_CERTIFICATION_MARKER,
        "step14d_final_certification_marker_required": step14d.FINAL_CERTIFICATION_MARKER,
        "smoke_version": SMOKE_VERSION,
        "smoke_status": SMOKE_STATUS,
        "final_certification_marker": FINAL_CERTIFICATION_MARKER,
        "runtime_mode": RUNTIME_MODE,
        "generated_at_utc": generated,
        "live_evidence_content_sha256": LIVE_EVIDENCE_CONTENT_SHA256,
        "sql_fingerprints": deepcopy(SQL_FINGERPRINTS),
        "checkpoint_contract": {
            "create_v1": True,
            "exact_load_round_trip": True,
            "idempotent_repeat": True,
            "append_only_advance_v2": True,
            "head_compare_and_swap": True,
            "stale_writer_rejected": True,
            "stale_transaction_rolled_back": True,
        },
        "lease_contract": {
            "initial_generation": 1,
            "active_contention_blocked": True,
            "valid_owner_renewed": True,
            "wrong_owner_renew_blocked": True,
            "expired_takeover": True,
            "takeover_generation": 2,
            "stale_owner_release_blocked": True,
            "current_owner_release_succeeded": True,
        },
        "cleanup_contract": deepcopy(evidence["cleanup"]),
        "execution_boundary": {
            "live_database_transaction_smoke_completed": True,
            "direct_psycopg_live_connection_certified": False,
            "connected_supabase_sql_surface_used": True,
            "all_smoke_writes_rolled_back": True,
            "production_scheduler_started": False,
            "global_persistence_runtime_started": False,
            "automatic_restart_execution": False,
            "background_worker_started": False,
            "public_persistence_api_exposed": False,
            "runtime_cycle_executed": False,
            "retry_executed": False,
            "restart_executed": False,
            "provider_calls": 0,
            "sportsbook_calls": 0,
            "production_activation": 0,
        },
        "phase_boundary": {
            "step15b_complete": True,
            "live_transaction_semantics_complete": True,
            "live_tables_clean_after_smoke": True,
            "step15c_final_live_persistence_freeze_required": True,
            "production_activation_not_started": True,
        },
        **PROTECTED_INVARIANTS,
    }
    surface = deepcopy(manifest)
    surface.pop("generated_at_utc", None)
    manifest["smoke_manifest_sha256"] = _hash(surface)
    return manifest


__all__ = [
    "DATA_TYPE",
    "FINAL_CERTIFICATION_MARKER",
    "LIVE_EVIDENCE_CONTENT_SHA256",
    "LIVE_EVIDENCE_PATH",
    "MLBStep15BLiveSmokeDisabledError",
    "MLBStep15BLiveSmokeIntegrityError",
    "SQL_FINGERPRINTS",
    "STEP15B_LIVE_ADAPTER_SMOKE_ENABLED_ENV",
    "live_adapter_transaction_smoke_manifest",
    "load_live_smoke_evidence",
    "step15b_live_adapter_smoke_enabled",
    "validate_frozen_sql_fingerprints",
    "validate_live_smoke_evidence",
]
