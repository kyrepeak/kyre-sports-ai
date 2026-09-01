"""MLB Step 15A — live PostgreSQL preflight.

Step 14 froze the durable checkpoint/restart/lease stack without opening a live
database connection. Step 15A is the first release layer allowed to inspect the
real PostgreSQL environment. It is deliberately read-only: it proves
connectivity, required schema shape, privileges, emptiness before smoke testing,
and frozen Step 14 lineage without persisting a checkpoint, touching a lease,
running a scheduler cycle, or activating production.

Schema installation is an explicit operational action outside this module.
This module never auto-applies DDL.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
import hashlib
import json
import os
from typing import Any

from sports_api import mlb_step14_final_persistence_freeze_v1 as step14d
from sports_api import mlb_step14b_database_checkpoint_adapter_v1 as step14b
from sports_api import mlb_step14c_durable_restart_lease_v1 as step14c
from sports_api.mlb_step9_final_freeze_v1 import PROTECTED_INVARIANTS

DATA_TYPE = "mlb_step15a_live_postgresql_preflight_v1"
RESULT_DATA_TYPE = "mlb_step15a_live_postgresql_preflight_result_v1"
SCHEMA_VERSION = 1
STEP15A_BASE_MAIN_SHA = "ac90d1261b31f15225a9e0cbb42c986c055bdf09"
STEP14D_SOURCE_BLOB_SHA = "8d346c2fb3abf71742c048d5489ac88124b990b6"
PREFLIGHT_VERSION = "mlb_step15a_live_postgresql_preflight_2026_v1"
PREFLIGHT_STATUS = "STEP15A_LIVE_POSTGRESQL_PREFLIGHT_READY"
FINAL_CERTIFICATION_MARKER = "MLB_STEP15A_LIVE_POSTGRESQL_PREFLIGHT_GREEN"
RUNTIME_MODE = "SHADOW_ONLY"

DATABASE_URL_ENV = step14b.DATABASE_URL_ENV
PREFLIGHT_ENABLED_ENV = "MLB_STEP15A_LIVE_POSTGRESQL_PREFLIGHT_ENABLED"

DATABASE_SCHEMA_NAME = step14b.DATABASE_SCHEMA_NAME
CHECKPOINT_TABLE_NAME = step14b.CHECKPOINT_TABLE_NAME
CHECKPOINT_HEAD_TABLE_NAME = step14b.CHECKPOINT_HEAD_TABLE_NAME
LEASE_TABLE_NAME = step14c.LEASE_TABLE_NAME

REQUIRED_TABLES = (
    CHECKPOINT_TABLE_NAME,
    CHECKPOINT_HEAD_TABLE_NAME,
    LEASE_TABLE_NAME,
)

EXPECTED_COLUMNS: dict[str, tuple[tuple[str, str, bool], ...]] = {
    CHECKPOINT_TABLE_NAME: (
        ("checkpoint_id", "uuid", True),
        ("checkpoint_key", "text", True),
        ("checkpoint_version", "bigint", True),
        ("season", "integer", True),
        ("season_type", "text", True),
        ("slate_date", "date", True),
        ("step13d_merge_sha", "character(40)", True),
        ("step13d_source_blob_sha", "character(40)", True),
        ("step13d_freeze_manifest_sha256", "character(64)", True),
        ("source_reliability_sha256", "character(64)", True),
        ("source_supervision_sha256", "character(64)", True),
        ("cycle_id", "character(64)", False),
        ("cycle_slot_utc", "timestamp with time zone", False),
        ("scheduler_state_sha256", "character(64)", True),
        ("recovery_state_sha256", "character(64)", True),
        ("recovery_handoff_sha256", "character(64)", True),
        ("envelope_content_sha256", "character(64)", True),
        ("envelope_json", "jsonb", True),
        ("created_at", "timestamp with time zone", True),
    ),
    CHECKPOINT_HEAD_TABLE_NAME: (
        ("checkpoint_key", "text", True),
        ("checkpoint_version", "bigint", True),
        ("checkpoint_id", "uuid", True),
        ("envelope_content_sha256", "character(64)", True),
        ("updated_at", "timestamp with time zone", True),
    ),
    LEASE_TABLE_NAME: (
        ("lease_key", "text", True),
        ("owner_id", "text", True),
        ("lease_token", "uuid", True),
        ("fencing_generation", "bigint", True),
        ("acquired_at", "timestamp with time zone", True),
        ("renewed_at", "timestamp with time zone", True),
        ("expires_at", "timestamp with time zone", True),
        ("updated_at", "timestamp with time zone", True),
    ),
}

REQUIRED_CONSTRAINTS: dict[str, frozenset[str]] = {
    CHECKPOINT_TABLE_NAME: frozenset(
        {
            "mlb_runtime_checkpoints_pkey",
            "mlb_runtime_checkpoints_key_version_unique",
            "mlb_runtime_checkpoints_key_envelope_unique",
            "mlb_runtime_checkpoints_envelope_object",
            "mlb_runtime_checkpoints_cycle_identity_pair",
            "mlb_runtime_checkpoints_step13d_merge_sha_len",
            "mlb_runtime_checkpoints_step13d_blob_sha_len",
            "mlb_runtime_checkpoints_step13d_manifest_hash_len",
            "mlb_runtime_checkpoints_source_reliability_hash_len",
            "mlb_runtime_checkpoints_source_supervision_hash_len",
            "mlb_runtime_checkpoints_scheduler_state_hash_len",
            "mlb_runtime_checkpoints_recovery_state_hash_len",
            "mlb_runtime_checkpoints_recovery_handoff_hash_len",
            "mlb_runtime_checkpoints_envelope_hash_len",
        }
    ),
    CHECKPOINT_HEAD_TABLE_NAME: frozenset(
        {
            "mlb_runtime_checkpoint_heads_pkey",
            "mlb_runtime_checkpoint_heads_checkpoint_fk",
            "mlb_runtime_checkpoint_heads_envelope_hash_len",
        }
    ),
    LEASE_TABLE_NAME: frozenset(
        {
            "mlb_runtime_leases_pkey",
            "mlb_runtime_leases_fencing_generation_check",
            "mlb_runtime_leases_lease_key_check",
            "mlb_runtime_leases_owner_id_check",
        }
    ),
}

REQUIRED_INDEXES: dict[str, frozenset[str]] = {
    CHECKPOINT_TABLE_NAME: frozenset(
        {
            "mlb_runtime_checkpoints_pkey",
            "mlb_runtime_checkpoints_key_version_unique",
            "mlb_runtime_checkpoints_key_envelope_unique",
            "mlb_runtime_checkpoints_slate_created_idx",
            "mlb_runtime_checkpoints_key_version_desc_idx",
            "mlb_runtime_checkpoints_cycle_idx",
        }
    ),
    CHECKPOINT_HEAD_TABLE_NAME: frozenset({"mlb_runtime_checkpoint_heads_pkey"}),
    LEASE_TABLE_NAME: frozenset(
        {"mlb_runtime_leases_pkey", "mlb_runtime_leases_expires_idx"}
    ),
}

_FORBIDDEN_TRUE_ENV_KEYS = (
    "MLB_PRODUCTION_RUNTIME_ENABLED",
    "MLB_PRODUCTION_SCHEDULER_ENABLED",
    "MLB_ACTIONABLE_OUTPUT_ENABLED",
    "MLB_WAGERING_ENABLED",
    "MLB_SUPABASE_REST_WRITE_ENABLED",
)

_METADATA_SQL = """
SELECT
    current_database()::text,
    current_user::text,
    current_setting('server_version_num')::integer,
    pg_is_in_recovery(),
    to_regnamespace(%s) IS NOT NULL,
    has_database_privilege(current_user, current_database(), 'CONNECT'),
    has_schema_privilege(current_user, %s, 'USAGE')
""".strip()

_COLUMNS_SQL = """
SELECT
    c.relname::text,
    a.attname::text,
    pg_catalog.format_type(a.atttypid, a.atttypmod)::text,
    a.attnotnull
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
JOIN pg_attribute a ON a.attrelid = c.oid
WHERE n.nspname = %s
  AND c.relname = ANY(%s)
  AND a.attnum > 0
  AND NOT a.attisdropped
ORDER BY c.relname, a.attnum
""".strip()

_CONSTRAINTS_SQL = """
SELECT c.relname::text, con.conname::text
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
JOIN pg_constraint con ON con.conrelid = c.oid
WHERE n.nspname = %s
  AND c.relname = ANY(%s)
ORDER BY c.relname, con.conname
""".strip()

_INDEXES_SQL = """
SELECT tablename::text, indexname::text
FROM pg_indexes
WHERE schemaname = %s
  AND tablename = ANY(%s)
ORDER BY tablename, indexname
""".strip()

_PRIVILEGES_SQL = """
SELECT
    has_table_privilege(current_user, %s, 'SELECT,INSERT'),
    has_table_privilege(current_user, %s, 'SELECT,INSERT,UPDATE'),
    has_table_privilege(current_user, %s, 'SELECT,INSERT,UPDATE,DELETE')
""".strip()

_COUNTS_SQL = f"""
SELECT
    (SELECT count(*) FROM {DATABASE_SCHEMA_NAME}.{CHECKPOINT_TABLE_NAME}),
    (SELECT count(*) FROM {DATABASE_SCHEMA_NAME}.{CHECKPOINT_HEAD_TABLE_NAME}),
    (SELECT count(*) FROM {DATABASE_SCHEMA_NAME}.{LEASE_TABLE_NAME})
""".strip()


class MLBStep15ALivePostgreSQLPreflightDisabledError(RuntimeError):
    """Raised when live preflight is not explicitly enabled."""


class MLBStep15ALivePostgreSQLPreflightError(RuntimeError):
    """Raised when live PostgreSQL preflight cannot be completed."""


class MLBStep15ALivePostgreSQLPreflightNotReadyError(RuntimeError):
    """Raised when the real PostgreSQL environment is not Step-15B ready."""


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() not in {
        "",
        "0",
        "false",
        "no",
        "off",
        "disabled",
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


def live_postgresql_preflight_manifest() -> dict[str, Any]:
    parent = step14d.final_persistence_freeze_manifest()
    validation = step14d.validate_final_persistence_freeze_manifest(parent)
    if validation.get("freeze_manifest_valid") is not True:
        raise MLBStep15ALivePostgreSQLPreflightError(
            f"Step 14D parent validation failed: {validation.get('failures')}"
        )

    manifest: dict[str, Any] = {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "step15a_base_main_sha": STEP15A_BASE_MAIN_SHA,
        "step14d_source_blob_sha": STEP14D_SOURCE_BLOB_SHA,
        "step14d_final_certification_marker_required": step14d.FINAL_CERTIFICATION_MARKER,
        "step14d_freeze_manifest_sha256": parent["freeze_manifest_sha256"],
        "preflight_version": PREFLIGHT_VERSION,
        "preflight_status": PREFLIGHT_STATUS,
        "final_certification_marker": FINAL_CERTIFICATION_MARKER,
        "runtime_mode": RUNTIME_MODE,
        "database_schema_name": DATABASE_SCHEMA_NAME,
        "checkpoint_table_name": CHECKPOINT_TABLE_NAME,
        "checkpoint_head_table_name": CHECKPOINT_HEAD_TABLE_NAME,
        "lease_table_name": LEASE_TABLE_NAME,
        "required_tables": list(REQUIRED_TABLES),
        "database_url_env": DATABASE_URL_ENV,
        "preflight_enable_env": PREFLIGHT_ENABLED_ENV,
        "live_database_connection_allowed": True,
        "live_database_metadata_reads_allowed": True,
        "live_database_schema_reads_allowed": True,
        "live_database_privilege_reads_allowed": True,
        "live_database_row_count_reads_allowed": True,
        "live_database_writes_allowed": False,
        "schema_auto_apply_allowed": False,
        "checkpoint_smoke_write_allowed": False,
        "lease_smoke_write_allowed": False,
        "runtime_cycle_execution_allowed": False,
        "retry_execution_allowed": False,
        "restart_execution_allowed": False,
        "production_runtime_activation_allowed": False,
        "production_scheduler_activation_allowed": False,
        "public_api_activation_allowed": False,
        "actionable_output_allowed": False,
        "background_worker_allowed": False,
        "provider_network_calls_allowed": False,
        "sportsbook_network_calls_allowed": False,
        "future_step15b_live_persistence_smoke_required": True,
        **PROTECTED_INVARIANTS,
    }
    manifest["preflight_manifest_sha256"] = _hash(manifest)
    return manifest


def _assert_preflight_gate(env: Mapping[str, str]) -> None:
    if not _truthy(env.get(PREFLIGHT_ENABLED_ENV)):
        raise MLBStep15ALivePostgreSQLPreflightDisabledError(
            f"Step 15A requires {PREFLIGHT_ENABLED_ENV}=true"
        )
    forbidden = [key for key in _FORBIDDEN_TRUE_ENV_KEYS if _truthy(env.get(key))]
    if forbidden:
        raise MLBStep15ALivePostgreSQLPreflightDisabledError(
            "Step 15A refuses production/actionable switches: " + ", ".join(forbidden)
        )
    if not str(env.get(DATABASE_URL_ENV) or "").strip():
        raise MLBStep15ALivePostgreSQLPreflightDisabledError(
            f"Step 15A requires {DATABASE_URL_ENV}; credentials are never embedded in code"
        )


def _default_connection_factory(dsn: str) -> Any:
    try:
        import psycopg  # type: ignore
    except ImportError as exc:
        raise MLBStep15ALivePostgreSQLPreflightError(
            "live PostgreSQL preflight requires psycopg 3"
        ) from exc
    try:
        return psycopg.connect(
            dsn,
            connect_timeout=10,
            application_name="kyre-sports-ai-mlb-step15a",
        )
    except Exception as exc:
        raise MLBStep15ALivePostgreSQLPreflightError(
            "could not open Step 15A PostgreSQL connection"
        ) from exc


def _rows_by_table(rows: list[tuple[Any, ...]]) -> dict[str, list[tuple[Any, ...]]]:
    grouped: dict[str, list[tuple[Any, ...]]] = {name: [] for name in REQUIRED_TABLES}
    for row in rows:
        if not row:
            continue
        name = str(row[0])
        if name in grouped:
            grouped[name].append(tuple(row[1:]))
    return grouped


def evaluate_live_postgresql_preflight(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    """Fail closed unless the live database matches the frozen Step 14 shape."""
    failures: list[str] = []

    if snapshot.get("in_recovery") is not False:
        failures.append("DATABASE_NOT_WRITABLE_PRIMARY")
    if snapshot.get("schema_exists") is not True:
        failures.append("KYRE_RUNTIME_SCHEMA_MISSING")
    if snapshot.get("can_connect") is not True:
        failures.append("DATABASE_CONNECT_PRIVILEGE_MISSING")
    if snapshot.get("can_use_schema") is not True:
        failures.append("KYRE_RUNTIME_USAGE_PRIVILEGE_MISSING")

    version_num = snapshot.get("server_version_num")
    if isinstance(version_num, bool) or not isinstance(version_num, int) or version_num < 150000:
        failures.append("POSTGRESQL_15_OR_NEWER_REQUIRED")

    tables = snapshot.get("tables")
    if not isinstance(tables, Mapping):
        failures.append("TABLE_SNAPSHOT_MISSING")
        tables = {}

    for table_name in REQUIRED_TABLES:
        table = tables.get(table_name) if isinstance(tables, Mapping) else None
        if not isinstance(table, Mapping):
            failures.append(f"{table_name.upper()}_MISSING")
            continue

        columns = tuple(tuple(value) for value in table.get("columns", ()))
        if columns != EXPECTED_COLUMNS[table_name]:
            failures.append(f"{table_name.upper()}_COLUMN_CONTRACT_MISMATCH")

        constraints = frozenset(str(v) for v in table.get("constraints", ()))
        missing_constraints = REQUIRED_CONSTRAINTS[table_name] - constraints
        if missing_constraints:
            failures.append(
                f"{table_name.upper()}_MISSING_CONSTRAINTS:"
                + ",".join(sorted(missing_constraints))
            )

        indexes = frozenset(str(v) for v in table.get("indexes", ()))
        missing_indexes = REQUIRED_INDEXES[table_name] - indexes
        if missing_indexes:
            failures.append(
                f"{table_name.upper()}_MISSING_INDEXES:"
                + ",".join(sorted(missing_indexes))
            )

        if table.get("privileges_ok") is not True:
            failures.append(f"{table_name.upper()}_PRIVILEGES_MISSING")

        row_count = table.get("row_count")
        if isinstance(row_count, bool) or not isinstance(row_count, int) or row_count < 0:
            failures.append(f"{table_name.upper()}_ROW_COUNT_INVALID")
        elif row_count != 0:
            failures.append(f"{table_name.upper()}_NOT_EMPTY_BEFORE_SMOKE")

    ready = not failures
    result = {
        "data_type": RESULT_DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "preflight_version": PREFLIGHT_VERSION,
        "preflight_status": "READY_FOR_STEP15B" if ready else "NOT_READY",
        "runtime_mode": RUNTIME_MODE,
        "database_name": snapshot.get("database_name"),
        "database_user": snapshot.get("database_user"),
        "server_version_num": version_num,
        "schema_exists": snapshot.get("schema_exists") is True,
        "required_tables": list(REQUIRED_TABLES),
        "live_database_connection_executed": True,
        "live_database_write_executed": False,
        "checkpoint_write_executed": False,
        "lease_operation_executed": False,
        "runtime_cycle_executed": False,
        "retry_executed": False,
        "restart_executed": False,
        "provider_calls": 0,
        "sportsbook_calls": 0,
        "production_activation": 0,
        "ready_for_step15b": ready,
        "failures": failures,
    }
    result["result_sha256"] = _hash(result)
    return result


def run_live_postgresql_preflight(
    *,
    env: Mapping[str, str] | None = None,
    connection_factory: Callable[[str], Any] | None = None,
) -> dict[str, Any]:
    """Connect read-only to the real database and certify Step-15B readiness."""
    source = os.environ if env is None else env
    _assert_preflight_gate(source)
    live_postgresql_preflight_manifest()

    dsn = str(source[DATABASE_URL_ENV]).strip()
    factory = _default_connection_factory if connection_factory is None else connection_factory
    connection = factory(dsn)

    try:
        with connection.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")

            cursor.execute(_METADATA_SQL, (DATABASE_SCHEMA_NAME, DATABASE_SCHEMA_NAME))
            metadata = cursor.fetchone()
            if not metadata or len(metadata) != 7:
                raise MLBStep15ALivePostgreSQLPreflightError(
                    "database metadata probe returned an unexpected shape"
                )

            cursor.execute(_COLUMNS_SQL, (DATABASE_SCHEMA_NAME, list(REQUIRED_TABLES)))
            columns = _rows_by_table(list(cursor.fetchall()))

            cursor.execute(_CONSTRAINTS_SQL, (DATABASE_SCHEMA_NAME, list(REQUIRED_TABLES)))
            constraints = _rows_by_table(list(cursor.fetchall()))

            cursor.execute(_INDEXES_SQL, (DATABASE_SCHEMA_NAME, list(REQUIRED_TABLES)))
            indexes = _rows_by_table(list(cursor.fetchall()))

            qualified = [
                f"{DATABASE_SCHEMA_NAME}.{CHECKPOINT_TABLE_NAME}",
                f"{DATABASE_SCHEMA_NAME}.{CHECKPOINT_HEAD_TABLE_NAME}",
                f"{DATABASE_SCHEMA_NAME}.{LEASE_TABLE_NAME}",
            ]
            cursor.execute(_PRIVILEGES_SQL, tuple(qualified))
            privileges = cursor.fetchone()
            if not privileges or len(privileges) != 3:
                raise MLBStep15ALivePostgreSQLPreflightError(
                    "database privilege probe returned an unexpected shape"
                )

            cursor.execute(_COUNTS_SQL)
            counts = cursor.fetchone()
            if not counts or len(counts) != 3:
                raise MLBStep15ALivePostgreSQLPreflightError(
                    "database row-count probe returned an unexpected shape"
                )

        connection.rollback()
    except Exception:
        try:
            connection.rollback()
        except Exception:
            pass
        raise
    finally:
        try:
            connection.close()
        except Exception:
            pass

    table_snapshot: dict[str, dict[str, Any]] = {}
    privilege_by_table = dict(zip(REQUIRED_TABLES, privileges, strict=True))
    count_by_table = dict(zip(REQUIRED_TABLES, counts, strict=True))
    for table_name in REQUIRED_TABLES:
        table_snapshot[table_name] = {
            "columns": [
                (str(name), str(data_type), bool(not_null))
                for name, data_type, not_null in columns.get(table_name, [])
            ],
            "constraints": [str(name) for (name,) in constraints.get(table_name, [])],
            "indexes": [str(name) for (name,) in indexes.get(table_name, [])],
            "privileges_ok": bool(privilege_by_table[table_name]),
            "row_count": int(count_by_table[table_name]),
        }

    snapshot = {
        "database_name": str(metadata[0]),
        "database_user": str(metadata[1]),
        "server_version_num": int(metadata[2]),
        "in_recovery": bool(metadata[3]),
        "schema_exists": bool(metadata[4]),
        "can_connect": bool(metadata[5]),
        "can_use_schema": bool(metadata[6]),
        "tables": table_snapshot,
    }
    result = evaluate_live_postgresql_preflight(snapshot)
    if result["ready_for_step15b"] is not True:
        raise MLBStep15ALivePostgreSQLPreflightNotReadyError(
            "live PostgreSQL preflight is not ready: " + ", ".join(result["failures"])
        )
    return result
