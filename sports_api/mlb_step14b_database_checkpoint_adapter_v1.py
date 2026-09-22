"""MLB Step 14B — isolated PostgreSQL scheduler/recovery checkpoint adapter.

Step 14A froze the only valid scheduler/recovery checkpoint envelope and its
append-only relational schema. Step 14B is the first MLB layer allowed to
perform isolated PostgreSQL reads and writes against that exact contract.

The adapter is explicitly gated, transaction-scoped, append-only, and uses a
versioned compare-and-swap (CAS) head. It does not wire persistence into the
runtime, restore a process after restart, create a distributed lease, run a
background worker, call a sportsbook/provider, or activate production.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from datetime import date, datetime, timezone
import hashlib
import json
import os
import re
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

from sports_api import mlb_step14a_persistence_contract_v1 as step14a
from sports_api.mlb_step9_final_freeze_v1 import PROTECTED_INVARIANTS

DATA_TYPE = "mlb_step14b_database_checkpoint_adapter_v1"
RESULT_DATA_TYPE = "mlb_step14b_database_checkpoint_result_v1"
SCHEMA_CHECK_DATA_TYPE = "mlb_step14b_database_schema_check_v1"
SCHEMA_VERSION = 1
STEP14B_BASE_MAIN_SHA = "3dae5181571dbfea45f6f0db87e916d25e971170"
STEP14A_MERGE_SHA = STEP14B_BASE_MAIN_SHA
STEP14A_SOURCE_BLOB_SHA = "373996a35959e5ad2252325062b250ddffd4286c"
STEP14A_SQL_SOURCE_BLOB_SHA = "969c88c529486c8cde54f7928919e2a393a0f588"
ADAPTER_VERSION = "mlb_step14b_postgresql_checkpoint_adapter_2026_v1"
ADAPTER_STATUS = "STEP14B_DATABASE_CHECKPOINT_ADAPTER_READY"
RUNTIME_MODE = "SHADOW_ONLY"
FINAL_CERTIFICATION_MARKER = "MLB_STEP14B_DATABASE_CHECKPOINT_ADAPTER_GREEN"

DATABASE_SCHEMA_NAME = step14a.DATABASE_SCHEMA_NAME
CHECKPOINT_TABLE_NAME = step14a.CHECKPOINT_TABLE_NAME
CHECKPOINT_HEAD_TABLE_NAME = step14a.CHECKPOINT_HEAD_TABLE_NAME
DATABASE_URL_ENV = "KYRE_DATABASE_URL"

STEP14B_DATABASE_CHECKPOINT_ADAPTER_ENABLED_ENV = (
    "MLB_STEP14B_DATABASE_CHECKPOINT_ADAPTER_ENABLED"
)
STEP14B_DATABASE_READ_ENABLED_ENV = "MLB_STEP14B_DATABASE_READ_ENABLED"
STEP14B_DATABASE_WRITE_ENABLED_ENV = "MLB_STEP14B_DATABASE_WRITE_ENABLED"

DEFAULT_ENABLED = False
POSTGRESQL_DATABASE_READ_ALLOWED = True
POSTGRESQL_DATABASE_WRITE_ALLOWED = True
CHECKPOINT_LOAD_ALLOWED = True
CHECKPOINT_SAVE_ALLOWED = True
ATOMIC_HEAD_COMPARE_AND_SWAP_ALLOWED = True
APPEND_ONLY_HISTORY_REQUIRED = True
DETERMINISTIC_CHECKPOINT_ID_REQUIRED = True
SCHEMA_AUTO_APPLY_ALLOWED = False
PERSISTENCE_RUNTIME_ENABLED = False
DURABLE_RESTART_RECOVERY_ALLOWED = False
DURABLE_DISTRIBUTED_LEASE_ALLOWED = False
CROSS_PROCESS_DUPLICATE_RUN_GUARD_ALLOWED = False
PRODUCTION_ACTIVATION_ALLOWED = False
PUBLIC_API_ACTIVATION_ALLOWED = False
ACTIONABLE_OUTPUT_ALLOWED = False
BACKGROUND_WORKER_ALLOWED = False
SUPABASE_REST_WRITE_ALLOWED = False

_FORBIDDEN_TRUE_ENV_KEYS = (
    "MLB_PRODUCTION_RUNTIME_ENABLED",
    "MLB_PRODUCTION_SCHEDULER_ENABLED",
    "MLB_STEP14C_DURABLE_RESTART_ENABLED",
    "MLB_STEP14C_DISTRIBUTED_LEASE_ENABLED",
    "MLB_ACTIONABLE_OUTPUT_ENABLED",
    "MLB_WAGERING_ENABLED",
    "MLB_SUPABASE_REST_WRITE_ENABLED",
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")

_SCHEMA_EXISTENCE_SQL = "SELECT to_regclass(%s) IS NOT NULL, to_regclass(%s) IS NOT NULL"

_HEAD_SELECT_SQL = f"""
SELECT
    h.checkpoint_version,
    h.checkpoint_id::text,
    h.envelope_content_sha256::text,
    c.checkpoint_version,
    c.checkpoint_id::text,
    c.checkpoint_key,
    c.slate_date::text,
    c.step13d_merge_sha,
    c.step13d_source_blob_sha,
    c.step13d_freeze_manifest_sha256,
    c.source_reliability_sha256,
    c.source_supervision_sha256,
    c.cycle_id,
    c.cycle_slot_utc,
    c.scheduler_state_sha256,
    c.recovery_state_sha256,
    c.recovery_handoff_sha256,
    c.envelope_content_sha256,
    c.envelope_json
FROM {DATABASE_SCHEMA_NAME}.{CHECKPOINT_HEAD_TABLE_NAME} AS h
JOIN {DATABASE_SCHEMA_NAME}.{CHECKPOINT_TABLE_NAME} AS c
  ON c.checkpoint_id = h.checkpoint_id
WHERE h.checkpoint_key = %s
""".strip()

_HEAD_SELECT_FOR_UPDATE_SQL = _HEAD_SELECT_SQL + "\nFOR UPDATE OF h"

_INSERT_HISTORY_SQL = f"""
INSERT INTO {DATABASE_SCHEMA_NAME}.{CHECKPOINT_TABLE_NAME} (
    checkpoint_id,
    checkpoint_key,
    checkpoint_version,
    season,
    season_type,
    slate_date,
    step13d_merge_sha,
    step13d_source_blob_sha,
    step13d_freeze_manifest_sha256,
    source_reliability_sha256,
    source_supervision_sha256,
    cycle_id,
    cycle_slot_utc,
    scheduler_state_sha256,
    recovery_state_sha256,
    recovery_handoff_sha256,
    envelope_content_sha256,
    envelope_json,
    created_at
) VALUES (
    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s
)
""".strip()

_INSERT_HEAD_SQL = f"""
INSERT INTO {DATABASE_SCHEMA_NAME}.{CHECKPOINT_HEAD_TABLE_NAME} (
    checkpoint_key,
    checkpoint_version,
    checkpoint_id,
    envelope_content_sha256,
    updated_at
) VALUES (%s, %s, %s, %s, %s)
""".strip()

_UPDATE_HEAD_SQL = f"""
UPDATE {DATABASE_SCHEMA_NAME}.{CHECKPOINT_HEAD_TABLE_NAME}
SET checkpoint_version = %s,
    checkpoint_id = %s,
    envelope_content_sha256 = %s,
    updated_at = %s
WHERE checkpoint_key = %s
  AND checkpoint_version = %s
""".strip()

_RESULT_KEYS = {
    "data_type",
    "schema_version",
    "adapter_version",
    "adapter_status",
    "runtime_mode",
    "operation",
    "status",
    "found",
    "slate_date",
    "checkpoint_key",
    "checkpoint_version",
    "checkpoint_id",
    "envelope_content_sha256",
    "scheduler_state_sha256",
    "recovery_state_sha256",
    "recovery_handoff_sha256",
    "checkpoint_envelope",
    "scheduler_state_for_restart",
    "recovery_state_for_restart",
    "recovery_handoff_for_restart",
    "lineage",
    "guardrails",
    "generated_at_utc",
    "adapter_content_sha256",
}


class MLBStep14BDatabaseAdapterDisabledError(RuntimeError):
    """Raised when an explicit Step 14B adapter/read/write gate is not enabled."""


class MLBStep14BDatabaseAdapterInputError(ValueError):
    """Raised when a caller supplies malformed adapter input."""


class MLBStep14BDatabaseAdapterIntegrityError(RuntimeError):
    """Raised when frozen lineage, checkpoint content, or row integrity drifts."""


class MLBStep14BDatabaseSchemaError(RuntimeError):
    """Raised when the frozen Step 14A checkpoint schema is not present."""


class MLBStep14BDatabaseConflictError(RuntimeError):
    """Raised when optimistic checkpoint-head compare-and-swap fails."""


class MLBStep14BDatabaseError(RuntimeError):
    """Raised for isolated database transport/transaction failures."""


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() not in {
        "",
        "0",
        "false",
        "no",
        "off",
        "disabled",
    }


def step14b_database_checkpoint_adapter_enabled(
    env: Mapping[str, str] | None = None,
) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(STEP14B_DATABASE_CHECKPOINT_ADAPTER_ENABLED_ENV))


def step14b_database_read_enabled(
    env: Mapping[str, str] | None = None,
) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(STEP14B_DATABASE_READ_ENABLED_ENV))


def step14b_database_write_enabled(
    env: Mapping[str, str] | None = None,
) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(STEP14B_DATABASE_WRITE_ENABLED_ENV))


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


def _valid_sha256(value: Any, field: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise MLBStep14BDatabaseAdapterIntegrityError(
            f"{field} must be lowercase 64-character SHA-256 hex"
        )
    return value


def _utc_z(value: Any, field: str) -> tuple[str, datetime]:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        text = value.strip()
        try:
            parsed = datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith("Z") else text)
        except ValueError as exc:
            raise MLBStep14BDatabaseAdapterInputError(f"{field} is invalid") from exc
    else:
        raise MLBStep14BDatabaseAdapterInputError(
            f"{field} must be an ISO-8601 timestamp"
        )
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise MLBStep14BDatabaseAdapterInputError(f"{field} must be timezone-aware")
    parsed = parsed.astimezone(timezone.utc)
    canonical = parsed.isoformat().replace("+00:00", "Z")
    return canonical, parsed


def _slate_text(value: str | date) -> str:
    checkpoint_key = step14a.checkpoint_key_for_slate(value)
    return checkpoint_key.rsplit(":", 1)[-1]


def _normalize_expected_version(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise MLBStep14BDatabaseAdapterInputError(
            "expected_head_version must be an integer >= 0"
        )
    return value


def _assert_adapter_integrity(env: Mapping[str, str] | None = None) -> None:
    source = os.environ if env is None else env
    if not step14b_database_checkpoint_adapter_enabled(source):
        raise MLBStep14BDatabaseAdapterDisabledError(
            f"Step 14B requires {STEP14B_DATABASE_CHECKPOINT_ADAPTER_ENABLED_ENV}=true"
        )
    forbidden = [key for key in _FORBIDDEN_TRUE_ENV_KEYS if _truthy(source.get(key))]
    if forbidden:
        raise MLBStep14BDatabaseAdapterDisabledError(
            "Step 14B refuses production/restart/actionable switches: "
            + ", ".join(forbidden)
        )

    contract = step14a.persistence_contract_manifest()
    contract_validation = step14a.validate_persistence_contract_manifest(contract)
    if contract_validation.get("manifest_valid") is not True:
        raise MLBStep14BDatabaseAdapterIntegrityError(
            f"Step 14A persistence contract validation failed: "
            f"{contract_validation.get('failures')}"
        )
    schema_manifest = step14a.build_step14a_schema_manifest()

    exact = {
        "step14a_contract_id": step14a.CONTRACT_ID
        == "mlb_step14a_scheduler_recovery_checkpoint_contract_2026_v1",
        "step14a_marker": step14a.FINAL_CERTIFICATION_MARKER
        == "MLB_STEP14A_PERSISTENCE_CONTRACT_GREEN",
        "step14a_runtime": step14a.RUNTIME_MODE == RUNTIME_MODE,
        "step14a_database_read_off": step14a.DATABASE_READ_ALLOWED is False,
        "step14a_database_write_off": step14a.DATABASE_WRITE_ALLOWED is False,
        "step14a_runtime_persistence_off": step14a.PERSISTENCE_RUNTIME_ENABLED is False,
        "step14a_restart_off": step14a.DURABLE_RESTART_RECOVERY_ALLOWED is False,
        "step14a_lease_off": step14a.DURABLE_DISTRIBUTED_LEASE_ALLOWED is False,
        "step14a_future_14b": contract.get("future_step14b_database_adapter_required")
        is True,
        "step14a_schema_name": schema_manifest.get("database_schema")
        == DATABASE_SCHEMA_NAME,
        "step14a_checkpoint_table": (
            schema_manifest.get("tables", {}).get("checkpoints", {}).get("name")
            == CHECKPOINT_TABLE_NAME
        ),
        "step14a_head_table": (
            schema_manifest.get("tables", {}).get("heads", {}).get("name")
            == CHECKPOINT_HEAD_TABLE_NAME
        ),
        "step14a_lease_absent": schema_manifest.get("lease_table_defined") is False,
    }
    failed = [name for name, ok in exact.items() if not ok]
    if failed:
        raise MLBStep14BDatabaseAdapterIntegrityError(
            "Step 14B detected frozen Step 14A drift: " + ", ".join(failed)
        )

    false_capabilities = {
        "schema_auto_apply": SCHEMA_AUTO_APPLY_ALLOWED,
        "persistence_runtime": PERSISTENCE_RUNTIME_ENABLED,
        "durable_restart": DURABLE_RESTART_RECOVERY_ALLOWED,
        "durable_lease": DURABLE_DISTRIBUTED_LEASE_ALLOWED,
        "cross_process_guard": CROSS_PROCESS_DUPLICATE_RUN_GUARD_ALLOWED,
        "production_activation": PRODUCTION_ACTIVATION_ALLOWED,
        "public_api": PUBLIC_API_ACTIVATION_ALLOWED,
        "actionable_output": ACTIONABLE_OUTPUT_ALLOWED,
        "background_worker": BACKGROUND_WORKER_ALLOWED,
        "supabase_rest_write": SUPABASE_REST_WRITE_ALLOWED,
    }
    if any(value is not False for value in false_capabilities.values()):
        raise MLBStep14BDatabaseAdapterIntegrityError(
            "Step 14B forbidden capability drift"
        )
    true_capabilities = {
        "postgres_read": POSTGRESQL_DATABASE_READ_ALLOWED,
        "postgres_write": POSTGRESQL_DATABASE_WRITE_ALLOWED,
        "checkpoint_load": CHECKPOINT_LOAD_ALLOWED,
        "checkpoint_save": CHECKPOINT_SAVE_ALLOWED,
        "cas": ATOMIC_HEAD_COMPARE_AND_SWAP_ALLOWED,
        "append_only": APPEND_ONLY_HISTORY_REQUIRED,
        "deterministic_id": DETERMINISTIC_CHECKPOINT_ID_REQUIRED,
    }
    if any(value is not True for value in true_capabilities.values()):
        raise MLBStep14BDatabaseAdapterIntegrityError(
            "Step 14B required adapter capability drift"
        )

    for key, value in PROTECTED_INVARIANTS.items():
        if value is not False:
            raise MLBStep14BDatabaseAdapterIntegrityError(
                f"Step 14B protected invariant drift: {key}"
            )


def _require_read(env: Mapping[str, str] | None) -> None:
    if not step14b_database_read_enabled(env):
        raise MLBStep14BDatabaseAdapterDisabledError(
            f"Step 14B reads require {STEP14B_DATABASE_READ_ENABLED_ENV}=true"
        )


def _require_write(env: Mapping[str, str] | None) -> None:
    if not step14b_database_write_enabled(env):
        raise MLBStep14BDatabaseAdapterDisabledError(
            f"Step 14B writes require {STEP14B_DATABASE_WRITE_ENABLED_ENV}=true"
        )


def database_checkpoint_adapter_manifest() -> dict[str, Any]:
    """Return the immutable Step 14B isolated-adapter capability boundary."""
    manifest: dict[str, Any] = {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "step14b_base_main_sha": STEP14B_BASE_MAIN_SHA,
        "step14a_merge_sha": STEP14A_MERGE_SHA,
        "step14a_source_blob_sha": STEP14A_SOURCE_BLOB_SHA,
        "step14a_sql_source_blob_sha": STEP14A_SQL_SOURCE_BLOB_SHA,
        "adapter_version": ADAPTER_VERSION,
        "adapter_status": ADAPTER_STATUS,
        "runtime_mode": RUNTIME_MODE,
        "final_certification_marker": FINAL_CERTIFICATION_MARKER,
        "step14a_final_certification_marker_required": step14a.FINAL_CERTIFICATION_MARKER,
        "step14a_contract_id_required": step14a.CONTRACT_ID,
        "database_schema": DATABASE_SCHEMA_NAME,
        "checkpoint_table": CHECKPOINT_TABLE_NAME,
        "checkpoint_head_table": CHECKPOINT_HEAD_TABLE_NAME,
        "explicit_adapter_gate_required": True,
        "explicit_read_gate_required": True,
        "explicit_write_gate_required": True,
        "postgresql_database_read_allowed": True,
        "postgresql_database_write_allowed": True,
        "checkpoint_load_allowed": True,
        "checkpoint_save_allowed": True,
        "append_only_checkpoint_history_required": True,
        "atomic_head_compare_and_swap_required": True,
        "select_for_update_head_serialization_required": True,
        "deterministic_uuid5_checkpoint_id_required": True,
        "idempotent_same_envelope_save_required": True,
        "schema_presence_probe_required": True,
        "schema_auto_apply_allowed": False,
        "persistence_runtime_enabled": False,
        "durable_restart_recovery_allowed": False,
        "durable_distributed_lease_allowed": False,
        "cross_process_duplicate_run_guard_allowed": False,
        "production_activation_allowed": False,
        "public_api_activation_allowed": False,
        "actionable_output_allowed": False,
        "background_worker_allowed": False,
        "supabase_rest_write_allowed": False,
        "runtime_cycle_execution_added_by_step14b": False,
        "retry_execution_added_by_step14b": False,
        "restart_execution_added_by_step14b": False,
        "provider_network_calls_added_by_step14b": False,
        "sportsbook_network_calls_added_by_step14b": False,
        "scheduler_state_mutation_added_by_step14b": False,
        "recovery_state_mutation_added_by_step14b": False,
        "future_step14c_durable_restart_lease_required": True,
        "future_step14d_final_persistence_freeze_required": True,
        **PROTECTED_INVARIANTS,
    }
    manifest["adapter_manifest_sha256"] = _hash(manifest)
    return manifest


def validate_database_checkpoint_adapter_manifest(
    manifest: Mapping[str, Any] | None,
) -> dict[str, Any]:
    failures: list[str] = []
    if not isinstance(manifest, Mapping):
        failures.append("STEP14B_MANIFEST_NOT_MAPPING")
    else:
        expected = database_checkpoint_adapter_manifest()
        if dict(manifest) != expected:
            failures.append("STEP14B_MANIFEST_EXACT_CONTRACT_MISMATCH")
    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "manifest_valid": not failures,
        "failures": failures,
    }


def checkpoint_id_for_envelope(envelope: Mapping[str, Any]) -> str:
    """Return a deterministic UUIDv5 for one exact Step 14A envelope."""
    if not isinstance(envelope, Mapping):
        raise MLBStep14BDatabaseAdapterInputError("checkpoint_envelope must be a mapping")
    key = str(envelope.get("checkpoint_key") or "").strip()
    digest = str(envelope.get("envelope_content_sha256") or "").strip().lower()
    if not key or _SHA256_RE.fullmatch(digest) is None:
        raise MLBStep14BDatabaseAdapterInputError(
            "checkpoint identity requires checkpoint_key and valid envelope hash"
        )
    return str(uuid5(NAMESPACE_URL, f"kyre-sports-ai:mlb:{key}:{digest}"))


def _validated_envelope(
    envelope: Mapping[str, Any],
    *,
    expected_slate_date: str | date | None = None,
) -> dict[str, Any]:
    if not isinstance(envelope, Mapping):
        raise MLBStep14BDatabaseAdapterInputError("checkpoint_envelope must be a mapping")
    validation = step14a.validate_step14a_checkpoint_envelope(
        envelope,
        expected_slate_date=expected_slate_date,
    )
    if validation.get("envelope_valid") is not True:
        raise MLBStep14BDatabaseAdapterIntegrityError(
            "Step 14B checkpoint failed frozen Step 14A validation: "
            + repr(validation.get("failures"))
        )
    return deepcopy(dict(envelope))


def _open_connection(
    env: Mapping[str, str] | None,
    connection_factory: Callable[[], Any] | None,
) -> Any:
    if connection_factory is not None:
        try:
            connection = connection_factory()
        except Exception as exc:
            raise MLBStep14BDatabaseError(
                "injected database connection factory failed"
            ) from exc
        if connection is None:
            raise MLBStep14BDatabaseError(
                "database connection factory returned no connection"
            )
        return connection

    source = os.environ if env is None else env
    dsn = str(source.get(DATABASE_URL_ENV) or "").strip()
    if not dsn:
        raise MLBStep14BDatabaseAdapterDisabledError(
            f"live PostgreSQL access requires {DATABASE_URL_ENV}; "
            "credentials are never embedded in code"
        )
    try:
        import psycopg  # type: ignore
    except ImportError as exc:
        raise MLBStep14BDatabaseError(
            "live PostgreSQL access requires psycopg 3"
        ) from exc
    try:
        return psycopg.connect(
            dsn,
            connect_timeout=10,
            application_name="kyre-sports-ai-mlb-step14b",
        )
    except Exception as exc:
        raise MLBStep14BDatabaseError(
            "could not open isolated Step 14B PostgreSQL connection"
        ) from exc


def _safe_close(value: Any) -> None:
    try:
        close = getattr(value, "close", None)
        if callable(close):
            close()
    except Exception:
        pass


def _safe_rollback(connection: Any) -> None:
    try:
        rollback = getattr(connection, "rollback", None)
        if callable(rollback):
            rollback()
    except Exception:
        pass


def _is_unique_violation(exc: BaseException) -> bool:
    code = str(
        getattr(exc, "sqlstate", None)
        or getattr(exc, "pgcode", None)
        or ""
    )
    return code == "23505"


def _verify_schema_with_cursor(cursor: Any) -> None:
    cursor.execute(
        _SCHEMA_EXISTENCE_SQL,
        (
            f"{DATABASE_SCHEMA_NAME}.{CHECKPOINT_TABLE_NAME}",
            f"{DATABASE_SCHEMA_NAME}.{CHECKPOINT_HEAD_TABLE_NAME}",
        ),
    )
    row = cursor.fetchone()
    if not isinstance(row, (tuple, list)) or len(row) != 2:
        raise MLBStep14BDatabaseSchemaError(
            "schema probe returned an invalid shape"
        )
    if row[0] is not True or row[1] is not True:
        raise MLBStep14BDatabaseSchemaError(
            "both frozen Step 14A checkpoint tables are required"
        )


def _decode_envelope(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        decoded = dict(value)
    elif isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError as exc:
            raise MLBStep14BDatabaseAdapterIntegrityError(
                "database envelope JSON is malformed"
            ) from exc
    else:
        raise MLBStep14BDatabaseAdapterIntegrityError(
            "database envelope must be JSON object content"
        )
    if not isinstance(decoded, dict):
        raise MLBStep14BDatabaseAdapterIntegrityError(
            "database envelope did not decode to an object"
        )
    return decoded


def _canonical_db_timestamp(value: Any, field: str) -> str | None:
    if value is None:
        return None
    canonical, _ = _utc_z(value, field)
    return canonical


def _normalize_head_row(
    row: Any,
    *,
    expected_slate_date: str | date,
) -> dict[str, Any] | None:
    if row is None:
        return None
    if not isinstance(row, (tuple, list)) or len(row) != 19:
        raise MLBStep14BDatabaseAdapterIntegrityError(
            "checkpoint-head query returned an invalid row shape"
        )

    (
        head_version,
        head_id,
        head_hash,
        history_version,
        history_id,
        history_key,
        history_slate,
        history_step13d_merge_sha,
        history_step13d_source_blob_sha,
        history_step13d_freeze_hash,
        history_source_reliability_hash,
        history_source_supervision_hash,
        history_cycle_id,
        history_cycle_slot,
        history_scheduler_hash,
        history_recovery_state_hash,
        history_recovery_handoff_hash,
        history_envelope_hash,
        envelope_json,
    ) = row

    if (
        isinstance(head_version, bool)
        or not isinstance(head_version, int)
        or head_version < 1
    ):
        raise MLBStep14BDatabaseAdapterIntegrityError(
            "persisted checkpoint head version is invalid"
        )
    if history_version != head_version:
        raise MLBStep14BDatabaseAdapterIntegrityError(
            "head/history checkpoint version mismatch"
        )
    try:
        head_uuid = str(UUID(str(head_id)))
        history_uuid = str(UUID(str(history_id)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise MLBStep14BDatabaseAdapterIntegrityError(
            "persisted checkpoint UUID is invalid"
        ) from exc
    if head_uuid != history_uuid:
        raise MLBStep14BDatabaseAdapterIntegrityError(
            "head/history checkpoint UUID mismatch"
        )

    head_digest = _valid_sha256(
        str(head_hash or "").strip().lower(),
        "head.envelope_content_sha256",
    )
    history_digest = _valid_sha256(
        str(history_envelope_hash or "").strip().lower(),
        "history.envelope_content_sha256",
    )
    if head_digest != history_digest:
        raise MLBStep14BDatabaseAdapterIntegrityError(
            "head/history envelope hash mismatch"
        )

    envelope = _decode_envelope(envelope_json)
    validated = _validated_envelope(
        envelope,
        expected_slate_date=expected_slate_date,
    )
    expected_key = step14a.checkpoint_key_for_slate(expected_slate_date)

    row_cycle_slot = _canonical_db_timestamp(
        history_cycle_slot,
        "history.cycle_slot_utc",
    )
    expected_cycle_slot = validated.get("cycle_slot_utc")
    checks = {
        "checkpoint_key": str(history_key) == expected_key == validated["checkpoint_key"],
        "slate_date": str(history_slate) == validated["slate_date"],
        "step13d_merge_sha": history_step13d_merge_sha
        == validated["step13d_merge_sha"],
        "step13d_source_blob_sha": history_step13d_source_blob_sha
        == validated["step13d_source_blob_sha"],
        "step13d_freeze_manifest_sha256": str(history_step13d_freeze_hash).lower()
        == validated["step13d_freeze_manifest_sha256"],
        "source_reliability_sha256": str(history_source_reliability_hash).lower()
        == validated["source_reliability_sha256"],
        "source_supervision_sha256": str(history_source_supervision_hash).lower()
        == validated["source_supervision_sha256"],
        "cycle_id": history_cycle_id == validated.get("cycle_id"),
        "cycle_slot_utc": row_cycle_slot == expected_cycle_slot,
        "scheduler_state_sha256": str(history_scheduler_hash).lower()
        == validated["scheduler_state_sha256"],
        "recovery_state_sha256": str(history_recovery_state_hash).lower()
        == validated["recovery_state_sha256"],
        "recovery_handoff_sha256": str(history_recovery_handoff_hash).lower()
        == validated["recovery_handoff_sha256"],
        "envelope_content_sha256": history_digest
        == validated["envelope_content_sha256"],
        "checkpoint_id": head_uuid == checkpoint_id_for_envelope(validated),
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise MLBStep14BDatabaseAdapterIntegrityError(
            "persisted checkpoint row/envelope mismatch: " + ", ".join(failed)
        )

    return {
        "checkpoint_version": head_version,
        "checkpoint_id": head_uuid,
        "envelope_content_sha256": validated["envelope_content_sha256"],
        "scheduler_state_sha256": validated["scheduler_state_sha256"],
        "recovery_state_sha256": validated["recovery_state_sha256"],
        "recovery_handoff_sha256": validated["recovery_handoff_sha256"],
        "checkpoint_envelope": validated,
        "scheduler_state_for_restart": deepcopy(validated["scheduler_state"]),
        "recovery_state_for_restart": deepcopy(validated["recovery_state"]),
        "recovery_handoff_for_restart": deepcopy(validated["recovery_handoff"]),
    }


def _result_hash_surface(result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: deepcopy(value)
        for key, value in result.items()
        if key not in {"generated_at_utc", "adapter_content_sha256"}
    }


def _build_result(
    *,
    operation: str,
    status: str,
    slate_date: str,
    checkpoint_key: str,
    found: bool,
    checkpoint_version: int | None,
    checkpoint_id: str | None,
    envelope_content_sha256: str | None,
    scheduler_state_sha256: str | None,
    recovery_state_sha256: str | None,
    recovery_handoff_sha256: str | None,
    checkpoint_envelope: Mapping[str, Any] | None,
    scheduler_state_for_restart: Mapping[str, Any] | None,
    recovery_state_for_restart: Mapping[str, Any] | None,
    recovery_handoff_for_restart: Mapping[str, Any] | None,
    generated_at_utc: str | None,
) -> dict[str, Any]:
    generated = (
        _utc_z(generated_at_utc, "generated_at_utc")[0]
        if generated_at_utc is not None
        else datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )
    result: dict[str, Any] = {
        "data_type": RESULT_DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "adapter_version": ADAPTER_VERSION,
        "adapter_status": ADAPTER_STATUS,
        "runtime_mode": RUNTIME_MODE,
        "operation": operation,
        "status": status,
        "found": found,
        "slate_date": slate_date,
        "checkpoint_key": checkpoint_key,
        "checkpoint_version": checkpoint_version,
        "checkpoint_id": checkpoint_id,
        "envelope_content_sha256": envelope_content_sha256,
        "scheduler_state_sha256": scheduler_state_sha256,
        "recovery_state_sha256": recovery_state_sha256,
        "recovery_handoff_sha256": recovery_handoff_sha256,
        "checkpoint_envelope": (
            deepcopy(dict(checkpoint_envelope))
            if checkpoint_envelope is not None
            else None
        ),
        "scheduler_state_for_restart": (
            deepcopy(dict(scheduler_state_for_restart))
            if scheduler_state_for_restart is not None
            else None
        ),
        "recovery_state_for_restart": (
            deepcopy(dict(recovery_state_for_restart))
            if recovery_state_for_restart is not None
            else None
        ),
        "recovery_handoff_for_restart": (
            deepcopy(dict(recovery_handoff_for_restart))
            if recovery_handoff_for_restart is not None
            else None
        ),
        "lineage": {
            "step14b_base_main_sha": STEP14B_BASE_MAIN_SHA,
            "step14a_merge_sha": STEP14A_MERGE_SHA,
            "step14a_source_blob_sha": STEP14A_SOURCE_BLOB_SHA,
            "step14a_sql_source_blob_sha": STEP14A_SQL_SOURCE_BLOB_SHA,
            "step14a_contract_id": step14a.CONTRACT_ID,
            "step14a_final_certification_marker": step14a.FINAL_CERTIFICATION_MARKER,
        },
        "guardrails": {
            "isolated_database_adapter": True,
            "postgresql_database_read_allowed": True,
            "postgresql_database_write_allowed": True,
            "append_only_checkpoint_history": True,
            "head_compare_and_swap": True,
            "select_for_update_head_serialization": True,
            "deterministic_checkpoint_id": True,
            "schema_auto_apply": False,
            "persistence_runtime_enabled": False,
            "durable_restart_recovery": False,
            "durable_distributed_lease": False,
            "cross_process_duplicate_run_guard": False,
            "production_activation": False,
            "public_api_activation": False,
            "actionable_output": False,
            "background_worker": False,
            "supabase_rest_write": False,
            "runtime_cycle_executed": False,
            "retry_executed": False,
            "restart_executed": False,
            "provider_network_calls": 0,
            "sportsbook_network_calls": 0,
        },
        "generated_at_utc": generated,
    }
    result["adapter_content_sha256"] = _hash(_result_hash_surface(result))
    return result


def validate_step14b_adapter_result(
    result: Mapping[str, Any] | None,
) -> dict[str, Any]:
    failures: list[str] = []
    if not isinstance(result, Mapping):
        return {
            "data_type": RESULT_DATA_TYPE,
            "schema_version": SCHEMA_VERSION,
            "result_valid": False,
            "failures": ["STEP14B_RESULT_NOT_MAPPING"],
        }
    value = dict(result)
    missing = sorted(_RESULT_KEYS - set(value))
    unknown = sorted(set(value) - _RESULT_KEYS)
    if missing:
        failures.append("STEP14B_RESULT_MISSING_KEYS:" + ",".join(missing))
    if unknown:
        failures.append("STEP14B_RESULT_UNKNOWN_KEYS:" + ",".join(unknown))
    if failures:
        return {
            "data_type": RESULT_DATA_TYPE,
            "schema_version": SCHEMA_VERSION,
            "result_valid": False,
            "failures": failures,
        }

    try:
        exact = {
            "data_type": value["data_type"] == RESULT_DATA_TYPE,
            "schema_version": value["schema_version"] == SCHEMA_VERSION,
            "adapter_version": value["adapter_version"] == ADAPTER_VERSION,
            "adapter_status": value["adapter_status"] == ADAPTER_STATUS,
            "runtime_mode": value["runtime_mode"] == RUNTIME_MODE,
            "checkpoint_key": value["checkpoint_key"]
            == step14a.checkpoint_key_for_slate(value["slate_date"]),
        }
        bad = [name for name, ok in exact.items() if not ok]
        if bad:
            raise MLBStep14BDatabaseAdapterIntegrityError(
                "adapter result contract drift: " + ", ".join(bad)
            )
        _utc_z(value["generated_at_utc"], "generated_at_utc")
        digest = _valid_sha256(
            value["adapter_content_sha256"],
            "adapter_content_sha256",
        )
        if digest != _hash(_result_hash_surface(value)):
            raise MLBStep14BDatabaseAdapterIntegrityError(
                "adapter result content hash mismatch"
            )

        lineage = value.get("lineage")
        if not isinstance(lineage, Mapping):
            raise MLBStep14BDatabaseAdapterIntegrityError(
                "adapter result lineage missing"
            )
        expected_lineage = {
            "step14b_base_main_sha": STEP14B_BASE_MAIN_SHA,
            "step14a_merge_sha": STEP14A_MERGE_SHA,
            "step14a_source_blob_sha": STEP14A_SOURCE_BLOB_SHA,
            "step14a_sql_source_blob_sha": STEP14A_SQL_SOURCE_BLOB_SHA,
            "step14a_contract_id": step14a.CONTRACT_ID,
            "step14a_final_certification_marker": step14a.FINAL_CERTIFICATION_MARKER,
        }
        if dict(lineage) != expected_lineage:
            raise MLBStep14BDatabaseAdapterIntegrityError(
                "adapter result lineage mismatch"
            )

        guardrails = value.get("guardrails")
        if not isinstance(guardrails, Mapping):
            raise MLBStep14BDatabaseAdapterIntegrityError(
                "adapter result guardrails missing"
            )
        forbidden_true = (
            "schema_auto_apply",
            "persistence_runtime_enabled",
            "durable_restart_recovery",
            "durable_distributed_lease",
            "cross_process_duplicate_run_guard",
            "production_activation",
            "public_api_activation",
            "actionable_output",
            "background_worker",
            "supabase_rest_write",
            "runtime_cycle_executed",
            "retry_executed",
            "restart_executed",
        )
        if any(guardrails.get(key) is not False for key in forbidden_true):
            raise MLBStep14BDatabaseAdapterIntegrityError(
                "adapter result forbidden guardrail drift"
            )
        if guardrails.get("provider_network_calls") != 0:
            raise MLBStep14BDatabaseAdapterIntegrityError(
                "adapter result provider call drift"
            )
        if guardrails.get("sportsbook_network_calls") != 0:
            raise MLBStep14BDatabaseAdapterIntegrityError(
                "adapter result sportsbook call drift"
            )

        if value["found"] is True:
            envelope = _validated_envelope(
                value["checkpoint_envelope"],
                expected_slate_date=value["slate_date"],
            )
            found_checks = {
                "checkpoint_version": isinstance(value["checkpoint_version"], int)
                and not isinstance(value["checkpoint_version"], bool)
                and value["checkpoint_version"] >= 1,
                "checkpoint_id": value["checkpoint_id"]
                == checkpoint_id_for_envelope(envelope),
                "envelope_hash": value["envelope_content_sha256"]
                == envelope["envelope_content_sha256"],
                "scheduler_hash": value["scheduler_state_sha256"]
                == envelope["scheduler_state_sha256"],
                "recovery_state_hash": value["recovery_state_sha256"]
                == envelope["recovery_state_sha256"],
                "recovery_handoff_hash": value["recovery_handoff_sha256"]
                == envelope["recovery_handoff_sha256"],
                "scheduler_state": value["scheduler_state_for_restart"]
                == envelope["scheduler_state"],
                "recovery_state": value["recovery_state_for_restart"]
                == envelope["recovery_state"],
                "recovery_handoff": value["recovery_handoff_for_restart"]
                == envelope["recovery_handoff"],
            }
            bad_found = [name for name, ok in found_checks.items() if not ok]
            if bad_found:
                raise MLBStep14BDatabaseAdapterIntegrityError(
                    "adapter result/envelope mismatch: " + ", ".join(bad_found)
                )
        else:
            nullable = (
                "checkpoint_version",
                "checkpoint_id",
                "envelope_content_sha256",
                "scheduler_state_sha256",
                "recovery_state_sha256",
                "recovery_handoff_sha256",
                "checkpoint_envelope",
                "scheduler_state_for_restart",
                "recovery_state_for_restart",
                "recovery_handoff_for_restart",
            )
            if any(value.get(key) is not None for key in nullable):
                raise MLBStep14BDatabaseAdapterIntegrityError(
                    "not-found adapter result carries checkpoint data"
                )
    except Exception as exc:
        failures.append(
            f"STEP14B_RESULT_INVALID:{type(exc).__name__}:{exc}"
        )

    return {
        "data_type": RESULT_DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "result_valid": not failures,
        "failures": failures,
    }


def verify_step14b_database_schema(
    *,
    env: Mapping[str, str] | None = None,
    connection_factory: Callable[[], Any] | None = None,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    """Verify required Step 14A tables using a read-only transaction."""
    _assert_adapter_integrity(env)
    _require_read(env)
    connection = _open_connection(env, connection_factory)
    cursor = None
    try:
        cursor = connection.cursor()
        _verify_schema_with_cursor(cursor)
        _safe_rollback(connection)
    except (
        MLBStep14BDatabaseAdapterDisabledError,
        MLBStep14BDatabaseAdapterIntegrityError,
        MLBStep14BDatabaseSchemaError,
    ):
        _safe_rollback(connection)
        raise
    except Exception as exc:
        _safe_rollback(connection)
        raise MLBStep14BDatabaseError(
            "database schema verification failed"
        ) from exc
    finally:
        _safe_close(cursor)
        _safe_close(connection)

    generated = (
        _utc_z(generated_at_utc, "generated_at_utc")[0]
        if generated_at_utc is not None
        else datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )
    result: dict[str, Any] = {
        "data_type": SCHEMA_CHECK_DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "adapter_version": ADAPTER_VERSION,
        "adapter_status": ADAPTER_STATUS,
        "runtime_mode": RUNTIME_MODE,
        "database_schema": DATABASE_SCHEMA_NAME,
        "checkpoint_table": CHECKPOINT_TABLE_NAME,
        "checkpoint_head_table": CHECKPOINT_HEAD_TABLE_NAME,
        "tables_present": True,
        "database_write_performed": False,
        "schema_auto_apply_performed": False,
        "step14a_merge_sha": STEP14A_MERGE_SHA,
        "step14a_source_blob_sha": STEP14A_SOURCE_BLOB_SHA,
        "step14a_sql_source_blob_sha": STEP14A_SQL_SOURCE_BLOB_SHA,
        "generated_at_utc": generated,
    }
    result["schema_check_content_sha256"] = _hash(
        {
            key: deepcopy(value)
            for key, value in result.items()
            if key not in {"generated_at_utc", "schema_check_content_sha256"}
        }
    )
    return result


def load_step14b_checkpoint(
    *,
    slate_date: str | date,
    env: Mapping[str, str] | None = None,
    connection_factory: Callable[[], Any] | None = None,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    """Load and fully validate the current durable checkpoint head."""
    _assert_adapter_integrity(env)
    _require_read(env)
    checkpoint_key = step14a.checkpoint_key_for_slate(slate_date)
    slate = _slate_text(slate_date)

    connection = _open_connection(env, connection_factory)
    cursor = None
    try:
        cursor = connection.cursor()
        _verify_schema_with_cursor(cursor)
        cursor.execute(_HEAD_SELECT_SQL, (checkpoint_key,))
        normalized = _normalize_head_row(
            cursor.fetchone(),
            expected_slate_date=slate,
        )
        _safe_rollback(connection)
    except (
        MLBStep14BDatabaseAdapterDisabledError,
        MLBStep14BDatabaseAdapterInputError,
        MLBStep14BDatabaseAdapterIntegrityError,
        MLBStep14BDatabaseSchemaError,
    ):
        _safe_rollback(connection)
        raise
    except Exception as exc:
        _safe_rollback(connection)
        raise MLBStep14BDatabaseError("checkpoint load failed") from exc
    finally:
        _safe_close(cursor)
        _safe_close(connection)

    if normalized is None:
        return _build_result(
            operation="load",
            status="not_found",
            slate_date=slate,
            checkpoint_key=checkpoint_key,
            found=False,
            checkpoint_version=None,
            checkpoint_id=None,
            envelope_content_sha256=None,
            scheduler_state_sha256=None,
            recovery_state_sha256=None,
            recovery_handoff_sha256=None,
            checkpoint_envelope=None,
            scheduler_state_for_restart=None,
            recovery_state_for_restart=None,
            recovery_handoff_for_restart=None,
            generated_at_utc=generated_at_utc,
        )

    return _build_result(
        operation="load",
        status="loaded",
        slate_date=slate,
        checkpoint_key=checkpoint_key,
        found=True,
        checkpoint_version=normalized["checkpoint_version"],
        checkpoint_id=normalized["checkpoint_id"],
        envelope_content_sha256=normalized["envelope_content_sha256"],
        scheduler_state_sha256=normalized["scheduler_state_sha256"],
        recovery_state_sha256=normalized["recovery_state_sha256"],
        recovery_handoff_sha256=normalized["recovery_handoff_sha256"],
        checkpoint_envelope=normalized["checkpoint_envelope"],
        scheduler_state_for_restart=normalized["scheduler_state_for_restart"],
        recovery_state_for_restart=normalized["recovery_state_for_restart"],
        recovery_handoff_for_restart=normalized["recovery_handoff_for_restart"],
        generated_at_utc=generated_at_utc,
    )


def save_step14b_checkpoint(
    *,
    checkpoint_envelope: Mapping[str, Any],
    expected_head_version: int,
    env: Mapping[str, str] | None = None,
    connection_factory: Callable[[], Any] | None = None,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    """Append one checkpoint and atomically advance its slate head."""
    _assert_adapter_integrity(env)
    _require_read(env)
    _require_write(env)
    expected_version = _normalize_expected_version(expected_head_version)
    validated = _validated_envelope(checkpoint_envelope)

    checkpoint_key = validated["checkpoint_key"]
    slate = validated["slate_date"]
    envelope_hash = validated["envelope_content_sha256"]
    checkpoint_id = checkpoint_id_for_envelope(validated)
    created_at = _utc_z(
        validated["created_at_utc"],
        "checkpoint.created_at_utc",
    )[1]
    write_time = (
        _utc_z(generated_at_utc, "generated_at_utc")[1]
        if generated_at_utc is not None
        else datetime.now(timezone.utc)
    )
    cycle_slot = (
        _utc_z(validated["cycle_slot_utc"], "checkpoint.cycle_slot_utc")[1]
        if validated.get("cycle_slot_utc") is not None
        else None
    )

    connection = _open_connection(env, connection_factory)
    cursor = None
    status: str
    new_version: int
    try:
        cursor = connection.cursor()
        _verify_schema_with_cursor(cursor)
        cursor.execute(_HEAD_SELECT_FOR_UPDATE_SQL, (checkpoint_key,))
        current = _normalize_head_row(
            cursor.fetchone(),
            expected_slate_date=slate,
        )
        current_version = 0 if current is None else current["checkpoint_version"]

        if (
            current is not None
            and current["envelope_content_sha256"] == envelope_hash
        ):
            _safe_rollback(connection)
            return _build_result(
                operation="save",
                status="idempotent",
                slate_date=slate,
                checkpoint_key=checkpoint_key,
                found=True,
                checkpoint_version=current["checkpoint_version"],
                checkpoint_id=current["checkpoint_id"],
                envelope_content_sha256=current["envelope_content_sha256"],
                scheduler_state_sha256=current["scheduler_state_sha256"],
                recovery_state_sha256=current["recovery_state_sha256"],
                recovery_handoff_sha256=current["recovery_handoff_sha256"],
                checkpoint_envelope=current["checkpoint_envelope"],
                scheduler_state_for_restart=current["scheduler_state_for_restart"],
                recovery_state_for_restart=current["recovery_state_for_restart"],
                recovery_handoff_for_restart=current["recovery_handoff_for_restart"],
                generated_at_utc=generated_at_utc,
            )

        if current_version != expected_version:
            raise MLBStep14BDatabaseConflictError(
                "checkpoint head CAS conflict: "
                f"expected version {expected_version}, "
                f"current version {current_version}"
            )

        new_version = current_version + 1
        cursor.execute(
            _INSERT_HISTORY_SQL,
            (
                checkpoint_id,
                checkpoint_key,
                new_version,
                step14a.SEASON,
                step14a.SEASON_TYPE,
                date.fromisoformat(slate),
                validated["step13d_merge_sha"],
                validated["step13d_source_blob_sha"],
                validated["step13d_freeze_manifest_sha256"],
                validated["source_reliability_sha256"],
                validated["source_supervision_sha256"],
                validated.get("cycle_id"),
                cycle_slot,
                validated["scheduler_state_sha256"],
                validated["recovery_state_sha256"],
                validated["recovery_handoff_sha256"],
                envelope_hash,
                json.dumps(
                    validated,
                    sort_keys=True,
                    separators=(",", ":"),
                    ensure_ascii=False,
                    allow_nan=False,
                ),
                created_at,
            ),
        )
        if getattr(cursor, "rowcount", 1) not in (1, -1):
            raise MLBStep14BDatabaseError(
                "checkpoint history insert did not affect exactly one row"
            )

        if current is None:
            cursor.execute(
                _INSERT_HEAD_SQL,
                (
                    checkpoint_key,
                    new_version,
                    checkpoint_id,
                    envelope_hash,
                    write_time,
                ),
            )
            status = "created"
        else:
            cursor.execute(
                _UPDATE_HEAD_SQL,
                (
                    new_version,
                    checkpoint_id,
                    envelope_hash,
                    write_time,
                    checkpoint_key,
                    current_version,
                ),
            )
            status = "advanced"

        if getattr(cursor, "rowcount", 1) != 1:
            raise MLBStep14BDatabaseConflictError(
                "checkpoint head compare-and-swap did not affect exactly one row"
            )
        connection.commit()
    except (
        MLBStep14BDatabaseAdapterDisabledError,
        MLBStep14BDatabaseAdapterInputError,
        MLBStep14BDatabaseAdapterIntegrityError,
        MLBStep14BDatabaseSchemaError,
        MLBStep14BDatabaseConflictError,
        MLBStep14BDatabaseError,
    ):
        _safe_rollback(connection)
        raise
    except Exception as exc:
        _safe_rollback(connection)
        if _is_unique_violation(exc):
            raise MLBStep14BDatabaseConflictError(
                "database uniqueness conflict; reload the head before retrying"
            ) from exc
        raise MLBStep14BDatabaseError("checkpoint save failed") from exc
    finally:
        _safe_close(cursor)
        _safe_close(connection)

    return _build_result(
        operation="save",
        status=status,
        slate_date=slate,
        checkpoint_key=checkpoint_key,
        found=True,
        checkpoint_version=new_version,
        checkpoint_id=checkpoint_id,
        envelope_content_sha256=envelope_hash,
        scheduler_state_sha256=validated["scheduler_state_sha256"],
        recovery_state_sha256=validated["recovery_state_sha256"],
        recovery_handoff_sha256=validated["recovery_handoff_sha256"],
        checkpoint_envelope=validated,
        scheduler_state_for_restart=validated["scheduler_state"],
        recovery_state_for_restart=validated["recovery_state"],
        recovery_handoff_for_restart=validated["recovery_handoff"],
        generated_at_utc=generated_at_utc,
    )


__all__ = [
    "DATA_TYPE",
    "RESULT_DATA_TYPE",
    "SCHEMA_CHECK_DATA_TYPE",
    "SCHEMA_VERSION",
    "STEP14B_BASE_MAIN_SHA",
    "STEP14A_MERGE_SHA",
    "STEP14A_SOURCE_BLOB_SHA",
    "STEP14A_SQL_SOURCE_BLOB_SHA",
    "ADAPTER_VERSION",
    "ADAPTER_STATUS",
    "RUNTIME_MODE",
    "FINAL_CERTIFICATION_MARKER",
    "DATABASE_SCHEMA_NAME",
    "CHECKPOINT_TABLE_NAME",
    "CHECKPOINT_HEAD_TABLE_NAME",
    "DATABASE_URL_ENV",
    "STEP14B_DATABASE_CHECKPOINT_ADAPTER_ENABLED_ENV",
    "STEP14B_DATABASE_READ_ENABLED_ENV",
    "STEP14B_DATABASE_WRITE_ENABLED_ENV",
    "DEFAULT_ENABLED",
    "POSTGRESQL_DATABASE_READ_ALLOWED",
    "POSTGRESQL_DATABASE_WRITE_ALLOWED",
    "CHECKPOINT_LOAD_ALLOWED",
    "CHECKPOINT_SAVE_ALLOWED",
    "ATOMIC_HEAD_COMPARE_AND_SWAP_ALLOWED",
    "APPEND_ONLY_HISTORY_REQUIRED",
    "DETERMINISTIC_CHECKPOINT_ID_REQUIRED",
    "SCHEMA_AUTO_APPLY_ALLOWED",
    "PERSISTENCE_RUNTIME_ENABLED",
    "DURABLE_RESTART_RECOVERY_ALLOWED",
    "DURABLE_DISTRIBUTED_LEASE_ALLOWED",
    "CROSS_PROCESS_DUPLICATE_RUN_GUARD_ALLOWED",
    "PRODUCTION_ACTIVATION_ALLOWED",
    "PUBLIC_API_ACTIVATION_ALLOWED",
    "ACTIONABLE_OUTPUT_ALLOWED",
    "BACKGROUND_WORKER_ALLOWED",
    "SUPABASE_REST_WRITE_ALLOWED",
    "MLBStep14BDatabaseAdapterDisabledError",
    "MLBStep14BDatabaseAdapterInputError",
    "MLBStep14BDatabaseAdapterIntegrityError",
    "MLBStep14BDatabaseSchemaError",
    "MLBStep14BDatabaseConflictError",
    "MLBStep14BDatabaseError",
    "step14b_database_checkpoint_adapter_enabled",
    "step14b_database_read_enabled",
    "step14b_database_write_enabled",
    "database_checkpoint_adapter_manifest",
    "validate_database_checkpoint_adapter_manifest",
    "checkpoint_id_for_envelope",
    "verify_step14b_database_schema",
    "load_step14b_checkpoint",
    "save_step14b_checkpoint",
    "validate_step14b_adapter_result",
]
