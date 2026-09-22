"""MLB Step 14C — durable restart context plus PostgreSQL cross-process lease.

Step 14B added isolated checkpoint load/save with append-only history and CAS.
Step 14C adds the durable ownership layer that a future always-on process may use
to safely recover the exact scheduler/recovery checkpoint after a crash/redeploy.

This module is explicit, foreground-only, default-OFF, and non-production. It
does not execute Step 12/13 runtime cycles, provider calls, sportsbook calls,
retries, restarts, background workers, or production scheduling. Its only
side effects are isolated PostgreSQL lease operations plus Step 14B checkpoint
reads/writes when the corresponding explicit gates are enabled.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any
from uuid import UUID, uuid4

from sports_api import mlb_step14a_persistence_contract_v1 as step14a
from sports_api import mlb_step14b_database_checkpoint_adapter_v1 as step14b
from sports_api.mlb_step9_final_freeze_v1 import PROTECTED_INVARIANTS

DATA_TYPE = "mlb_step14c_durable_restart_lease_v1"
RESTART_CONTEXT_DATA_TYPE = "mlb_step14c_restart_context_v1"
PERSIST_RESULT_DATA_TYPE = "mlb_step14c_persist_result_v1"
SCHEMA_CHECK_DATA_TYPE = "mlb_step14c_lease_schema_check_v1"
SCHEMA_VERSION = 1
STEP14C_BASE_MAIN_SHA = "195df0c15de1998754204080f9db4a76bca74e4b"
STEP14B_MERGE_SHA = STEP14C_BASE_MAIN_SHA
STEP14B_SOURCE_BLOB_SHA = "ee7ffe3117edc33b1377f883c25613d63760095b"
RUNTIME_VERSION = "mlb_step14c_foreground_durable_restart_lease_2026_v1"
RUNTIME_STATUS = "STEP14C_DURABLE_RESTART_LEASE_READY"
RUNTIME_MODE = "SHADOW_ONLY"
FINAL_CERTIFICATION_MARKER = "MLB_STEP14C_DURABLE_RESTART_LEASE_GREEN"

DATABASE_SCHEMA_NAME = step14b.DATABASE_SCHEMA_NAME
DATABASE_URL_ENV = step14b.DATABASE_URL_ENV
LEASE_TABLE_NAME = "mlb_runtime_leases"
LEASE_SQL_SCHEMA_PATH = "sports_api/sql/mlb_step14c_runtime_lease_schema.sql"
LEASE_SQL_SCHEMA_SHA256 = "9c113b0a6ae4c9f73c10e2d664b96c9130861b6a9cc3cbda1d2b9932c10c9190"

STEP14C_DURABLE_RESTART_LEASE_ENABLED_ENV = (
    "MLB_STEP14C_DURABLE_RESTART_LEASE_ENABLED"
)

DEFAULT_ENABLED = False
FOREGROUND_DURABLE_RESTART_CONTEXT_ALLOWED = True
DURABLE_RESTART_RECOVERY_ALLOWED = True
DURABLE_DISTRIBUTED_LEASE_ALLOWED = True
CROSS_PROCESS_DUPLICATE_RUN_GUARD_ALLOWED = True
FENCING_GENERATION_REQUIRED = True
LEASE_EXPIRY_REQUIRED = True
LEASE_REVALIDATION_BEFORE_SAVE_REQUIRED = True
CHECKPOINT_CAS_REQUIRED = True
CHECKPOINT_PERSIST_UNDER_LEASE_ALLOWED = True
SCHEMA_AUTO_APPLY_ALLOWED = False
PERSISTENCE_RUNTIME_ENABLED = False
AUTOMATIC_RESTART_EXECUTION_ALLOWED = False
AUTOMATIC_PRODUCTION_RESTART_ACTIVATION_ALLOWED = False
PRODUCTION_ACTIVATION_ALLOWED = False
PUBLIC_API_ACTIVATION_ALLOWED = False
ACTIONABLE_OUTPUT_ALLOWED = False
BACKGROUND_WORKER_ALLOWED = False
BACKGROUND_THREAD_ALLOWED = False
SUPABASE_REST_WRITE_ALLOWED = False

DEFAULT_LEASE_TTL_SECONDS = 300
MIN_LEASE_TTL_SECONDS = 60
MAX_LEASE_TTL_SECONDS = 3600

_FORBIDDEN_TRUE_ENV_KEYS = (
    "MLB_PRODUCTION_RUNTIME_ENABLED",
    "MLB_PRODUCTION_SCHEDULER_ENABLED",
    "MLB_ACTIONABLE_OUTPUT_ENABLED",
    "MLB_WAGERING_ENABLED",
    "MLB_SUPABASE_REST_WRITE_ENABLED",
)
_REQUIRED_TRUE_ENV_KEYS = (
    step14b.STEP14B_DATABASE_CHECKPOINT_ADAPTER_ENABLED_ENV,
    step14b.STEP14B_DATABASE_READ_ENABLED_ENV,
    step14b.STEP14B_DATABASE_WRITE_ENABLED_ENV,
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

_SCHEMA_EXISTENCE_SQL = "SELECT to_regclass(%s) IS NOT NULL"
_ACQUIRE_LEASE_SQL = f"""
INSERT INTO {DATABASE_SCHEMA_NAME}.{LEASE_TABLE_NAME} AS l (
    lease_key,
    owner_id,
    lease_token,
    fencing_generation,
    acquired_at,
    renewed_at,
    expires_at,
    updated_at
) VALUES (
    %s, %s, %s, 1,
    now(), now(), now() + (%s * interval '1 second'), now()
)
ON CONFLICT (lease_key) DO UPDATE
SET owner_id = EXCLUDED.owner_id,
    lease_token = EXCLUDED.lease_token,
    fencing_generation = l.fencing_generation + 1,
    acquired_at = now(),
    renewed_at = now(),
    expires_at = now() + (%s * interval '1 second'),
    updated_at = now()
WHERE l.expires_at <= now()
RETURNING lease_key, owner_id, lease_token::text, fencing_generation,
          acquired_at::text, renewed_at::text, expires_at::text
""".strip()

_RENEW_LEASE_SQL = f"""
UPDATE {DATABASE_SCHEMA_NAME}.{LEASE_TABLE_NAME}
SET renewed_at = now(),
    expires_at = now() + (%s * interval '1 second'),
    updated_at = now()
WHERE lease_key = %s
  AND owner_id = %s
  AND lease_token = %s
  AND fencing_generation = %s
  AND expires_at > now()
RETURNING lease_key, owner_id, lease_token::text, fencing_generation,
          acquired_at::text, renewed_at::text, expires_at::text
""".strip()

_RELEASE_LEASE_SQL = f"""
DELETE FROM {DATABASE_SCHEMA_NAME}.{LEASE_TABLE_NAME}
WHERE lease_key = %s
  AND owner_id = %s
  AND lease_token = %s
  AND fencing_generation = %s
RETURNING lease_key
""".strip()

_RESTART_CONTEXT_KEYS = {
    "data_type", "schema_version", "runtime_version", "runtime_status",
    "runtime_mode", "status", "slate_date", "checkpoint_key", "found",
    "loaded_checkpoint_version", "expected_head_version", "checkpoint_id",
    "envelope_content_sha256", "scheduler_state_sha256",
    "recovery_state_sha256", "recovery_handoff_sha256",
    "checkpoint_envelope", "scheduler_state_for_restart",
    "recovery_state_for_restart", "recovery_handoff_for_restart", "lease",
    "lineage", "guardrails", "generated_at_utc", "restart_context_sha256",
}

_PERSIST_RESULT_KEYS = {
    "data_type", "schema_version", "runtime_version", "runtime_status",
    "runtime_mode", "status", "slate_date", "checkpoint_key",
    "previous_checkpoint_version", "saved_checkpoint_version",
    "saved_checkpoint_status", "saved_checkpoint_id",
    "saved_envelope_content_sha256", "scheduler_state_sha256",
    "recovery_state_sha256", "recovery_handoff_sha256", "lease",
    "lineage", "guardrails", "generated_at_utc", "persist_result_sha256",
}


class MLBStep14CDurableRuntimeDisabledError(RuntimeError):
    """Raised when explicit Step 14C/14B persistence gates are not enabled."""


class MLBStep14CDurableRuntimeInputError(ValueError):
    """Raised for malformed Step 14C caller input."""


class MLBStep14CDurableRuntimeIntegrityError(RuntimeError):
    """Raised when frozen lineage, context, lease, or checkpoint integrity drifts."""


class MLBStep14CLeaseSchemaError(RuntimeError):
    """Raised when the additive Step 14C lease table is absent."""


class MLBStep14CLeaseUnavailableError(RuntimeError):
    """Raised when another process owns an unexpired slate lease."""


class MLBStep14CLeaseLostError(RuntimeError):
    """Raised when a stale/expired owner attempts renew/release/persist."""


class MLBStep14CDatabaseError(RuntimeError):
    """Raised for isolated PostgreSQL transport/transaction failures."""


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled",
    }


def step14c_durable_restart_lease_enabled(
    env: Mapping[str, str] | None = None,
) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(STEP14C_DURABLE_RESTART_LEASE_ENABLED_ENV))


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
    text = str(value or "").strip()
    if _SHA256_RE.fullmatch(text) is None:
        raise MLBStep14CDurableRuntimeIntegrityError(
            f"{field} must be lowercase 64-character SHA-256 hex"
        )
    return text


def _strict_positive_int(
    value: Any,
    field: str,
    minimum: int,
    maximum: int,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise MLBStep14CDurableRuntimeInputError(f"{field} must be an integer")
    if not minimum <= value <= maximum:
        raise MLBStep14CDurableRuntimeInputError(
            f"{field} must be between {minimum} and {maximum}"
        )
    return value


def _owner_id(value: Any) -> str:
    text = str(value or "").strip()
    if not 1 <= len(text) <= 255:
        raise MLBStep14CDurableRuntimeInputError(
            "owner_id must contain 1 through 255 characters"
        )
    return text


def _utc_z(value: Any, field: str) -> tuple[str, datetime]:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        text = value.strip()
        try:
            parsed = datetime.fromisoformat(
                text[:-1] + "+00:00" if text.endswith("Z") else text
            )
        except ValueError as exc:
            raise MLBStep14CDurableRuntimeIntegrityError(
                f"{field} must be ISO-8601"
            ) from exc
    else:
        raise MLBStep14CDurableRuntimeIntegrityError(
            f"{field} must be ISO-8601"
        )
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise MLBStep14CDurableRuntimeIntegrityError(
            f"{field} must be timezone-aware"
        )
    parsed = parsed.astimezone(timezone.utc)
    return parsed.isoformat().replace("+00:00", "Z"), parsed


def _step14b_env(env: Mapping[str, str] | None) -> dict[str, str]:
    source = dict(os.environ if env is None else env)
    source["MLB_STEP14C_DURABLE_RESTART_ENABLED"] = "false"
    source["MLB_STEP14C_DISTRIBUTED_LEASE_ENABLED"] = "false"
    source["MLB_PRODUCTION_RUNTIME_ENABLED"] = "false"
    source["MLB_PRODUCTION_SCHEDULER_ENABLED"] = "false"
    source["MLB_ACTIONABLE_OUTPUT_ENABLED"] = "false"
    source["MLB_WAGERING_ENABLED"] = "false"
    source["MLB_SUPABASE_REST_WRITE_ENABLED"] = "false"
    return source


def _assert_integrity(env: Mapping[str, str] | None = None) -> None:
    source = os.environ if env is None else env
    if not step14c_durable_restart_lease_enabled(source):
        raise MLBStep14CDurableRuntimeDisabledError(
            f"Step 14C requires {STEP14C_DURABLE_RESTART_LEASE_ENABLED_ENV}=true"
        )
    forbidden = [key for key in _FORBIDDEN_TRUE_ENV_KEYS if _truthy(source.get(key))]
    if forbidden:
        raise MLBStep14CDurableRuntimeDisabledError(
            "Step 14C refuses production/actionable switches: "
            + ", ".join(forbidden)
        )
    missing = [key for key in _REQUIRED_TRUE_ENV_KEYS if not _truthy(source.get(key))]
    if missing:
        raise MLBStep14CDurableRuntimeDisabledError(
            "Step 14C requires the frozen Step 14B adapter/read/write gates: "
            + ", ".join(missing)
        )

    manifest = step14b.database_checkpoint_adapter_manifest()
    validation = step14b.validate_database_checkpoint_adapter_manifest(manifest)
    if validation.get("manifest_valid") is not True:
        raise MLBStep14CDurableRuntimeIntegrityError(
            f"Step 14B manifest validation failed: {validation.get('failures')}"
        )

    exact = {
        "step14b_base_sha": step14b.STEP14B_BASE_MAIN_SHA
        == "3dae5181571dbfea45f6f0db87e916d25e971170",
        "step14b_marker": step14b.FINAL_CERTIFICATION_MARKER
        == "MLB_STEP14B_DATABASE_CHECKPOINT_ADAPTER_GREEN",
        "step14b_runtime_mode": step14b.RUNTIME_MODE == RUNTIME_MODE,
        "step14b_read_allowed": step14b.POSTGRESQL_DATABASE_READ_ALLOWED is True,
        "step14b_write_allowed": step14b.POSTGRESQL_DATABASE_WRITE_ALLOWED is True,
        "step14b_restart_off": step14b.DURABLE_RESTART_RECOVERY_ALLOWED is False,
        "step14b_lease_off": step14b.DURABLE_DISTRIBUTED_LEASE_ALLOWED is False,
        "step14b_cross_process_off":
        step14b.CROSS_PROCESS_DUPLICATE_RUN_GUARD_ALLOWED is False,
        "step14b_future_14c":
        manifest.get("future_step14c_durable_restart_lease_required") is True,
        "step14a_restart_off": step14a.DURABLE_RESTART_RECOVERY_ALLOWED is False,
        "step14a_lease_off": step14a.DURABLE_DISTRIBUTED_LEASE_ALLOWED is False,
    }
    failed = [name for name, ok in exact.items() if not ok]
    if failed:
        raise MLBStep14CDurableRuntimeIntegrityError(
            "Step 14C detected frozen parent drift: " + ", ".join(failed)
        )

    try:
        observed_sql_hash = hashlib.sha256(
            Path(LEASE_SQL_SCHEMA_PATH).read_bytes()
        ).hexdigest()
    except OSError as exc:
        raise MLBStep14CDurableRuntimeIntegrityError(
            "Step 14C cannot read the additive lease SQL schema"
        ) from exc
    if observed_sql_hash != LEASE_SQL_SCHEMA_SHA256:
        raise MLBStep14CDurableRuntimeIntegrityError(
            "Step 14C lease SQL schema hash drift"
        )

    true_capabilities = {
        "foreground_restart_context": FOREGROUND_DURABLE_RESTART_CONTEXT_ALLOWED,
        "durable_restart": DURABLE_RESTART_RECOVERY_ALLOWED,
        "durable_lease": DURABLE_DISTRIBUTED_LEASE_ALLOWED,
        "cross_process_guard": CROSS_PROCESS_DUPLICATE_RUN_GUARD_ALLOWED,
        "fencing": FENCING_GENERATION_REQUIRED,
        "expiry": LEASE_EXPIRY_REQUIRED,
        "revalidate_before_save": LEASE_REVALIDATION_BEFORE_SAVE_REQUIRED,
        "checkpoint_cas": CHECKPOINT_CAS_REQUIRED,
        "checkpoint_persist_under_lease": CHECKPOINT_PERSIST_UNDER_LEASE_ALLOWED,
    }
    if any(value is not True for value in true_capabilities.values()):
        raise MLBStep14CDurableRuntimeIntegrityError(
            "Step 14C required capability drift"
        )
    false_capabilities = {
        "default_enabled": DEFAULT_ENABLED,
        "schema_auto_apply": SCHEMA_AUTO_APPLY_ALLOWED,
        "persistence_runtime": PERSISTENCE_RUNTIME_ENABLED,
        "automatic_restart_execution": AUTOMATIC_RESTART_EXECUTION_ALLOWED,
        "automatic_production_restart":
        AUTOMATIC_PRODUCTION_RESTART_ACTIVATION_ALLOWED,
        "production_activation": PRODUCTION_ACTIVATION_ALLOWED,
        "public_api": PUBLIC_API_ACTIVATION_ALLOWED,
        "actionable_output": ACTIONABLE_OUTPUT_ALLOWED,
        "background_worker": BACKGROUND_WORKER_ALLOWED,
        "background_thread": BACKGROUND_THREAD_ALLOWED,
        "supabase_rest_write": SUPABASE_REST_WRITE_ALLOWED,
    }
    if any(value is not False for value in false_capabilities.values()):
        raise MLBStep14CDurableRuntimeIntegrityError(
            "Step 14C forbidden capability drift"
        )

    for key, value in PROTECTED_INVARIANTS.items():
        if value is not False:
            raise MLBStep14CDurableRuntimeIntegrityError(
                f"Step 14C protected invariant drift: {key}"
            )


def durable_restart_lease_manifest() -> dict[str, Any]:
    manifest: dict[str, Any] = {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "step14c_base_main_sha": STEP14C_BASE_MAIN_SHA,
        "step14b_merge_sha": STEP14B_MERGE_SHA,
        "step14b_source_blob_sha": STEP14B_SOURCE_BLOB_SHA,
        "runtime_version": RUNTIME_VERSION,
        "runtime_status": RUNTIME_STATUS,
        "runtime_mode": RUNTIME_MODE,
        "final_certification_marker": FINAL_CERTIFICATION_MARKER,
        "step14b_final_certification_marker_required":
        step14b.FINAL_CERTIFICATION_MARKER,
        "step14a_final_certification_marker_required":
        step14a.FINAL_CERTIFICATION_MARKER,
        "database_schema": DATABASE_SCHEMA_NAME,
        "lease_table": LEASE_TABLE_NAME,
        "lease_sql_schema_path": LEASE_SQL_SCHEMA_PATH,
        "lease_sql_schema_sha256": LEASE_SQL_SCHEMA_SHA256,
        "explicit_step14c_gate_required": True,
        "step14b_adapter_read_write_gates_required": True,
        "foreground_durable_restart_context_allowed": True,
        "durable_restart_recovery_allowed": True,
        "durable_distributed_lease_allowed": True,
        "cross_process_duplicate_run_guard_allowed": True,
        "lease_uuid_token_required": True,
        "monotonic_fencing_generation_required": True,
        "lease_expiry_required": True,
        "lease_revalidation_before_checkpoint_save_required": True,
        "checkpoint_compare_and_swap_required": True,
        "append_only_checkpoint_history_required": True,
        "checkpoint_persist_under_lease_allowed": True,
        "schema_presence_probe_required": True,
        "schema_auto_apply_allowed": False,
        "persistence_runtime_enabled": False,
        "automatic_restart_execution_allowed": False,
        "automatic_production_restart_activation_allowed": False,
        "production_activation_allowed": False,
        "public_api_activation_allowed": False,
        "actionable_output_allowed": False,
        "background_worker_allowed": False,
        "background_thread_allowed": False,
        "supabase_rest_write_allowed": False,
        "runtime_cycle_execution_added_by_step14c": False,
        "retry_execution_added_by_step14c": False,
        "restart_execution_added_by_step14c": False,
        "provider_network_calls_added_by_step14c": False,
        "sportsbook_network_calls_added_by_step14c": False,
        "future_step14d_final_persistence_freeze_required": True,
        **PROTECTED_INVARIANTS,
    }
    manifest["runtime_manifest_sha256"] = _hash(manifest)
    return manifest


def validate_durable_restart_lease_manifest(
    manifest: Mapping[str, Any] | None,
) -> dict[str, Any]:
    failures: list[str] = []
    if not isinstance(manifest, Mapping):
        failures.append("STEP14C_MANIFEST_NOT_MAPPING")
    else:
        expected = durable_restart_lease_manifest()
        if dict(manifest) != expected:
            failures.append("STEP14C_MANIFEST_EXACT_CONTRACT_MISMATCH")
    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "manifest_valid": not failures,
        "failures": failures,
    }


def _open_connection(
    env: Mapping[str, str] | None,
    connection_factory: Callable[[], Any] | None,
) -> Any:
    if connection_factory is not None:
        try:
            connection = connection_factory()
        except Exception as exc:
            raise MLBStep14CDatabaseError(
                "injected lease database connection factory failed"
            ) from exc
        if connection is None:
            raise MLBStep14CDatabaseError(
                "lease database connection factory returned no connection"
            )
        return connection

    source = os.environ if env is None else env
    dsn = str(source.get(DATABASE_URL_ENV) or "").strip()
    if not dsn:
        raise MLBStep14CDurableRuntimeDisabledError(
            f"live PostgreSQL access requires {DATABASE_URL_ENV}; "
            "credentials are never embedded in code"
        )
    try:
        import psycopg  # type: ignore
    except ImportError as exc:
        raise MLBStep14CDatabaseError(
            "live PostgreSQL access requires psycopg 3"
        ) from exc
    try:
        return psycopg.connect(
            dsn,
            connect_timeout=10,
            application_name="kyre-sports-ai-mlb-step14c",
        )
    except Exception as exc:
        raise MLBStep14CDatabaseError(
            "could not open isolated Step 14C PostgreSQL connection"
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


def _verify_lease_schema_with_cursor(cursor: Any) -> None:
    cursor.execute(
        _SCHEMA_EXISTENCE_SQL,
        (f"{DATABASE_SCHEMA_NAME}.{LEASE_TABLE_NAME}",),
    )
    row = cursor.fetchone()
    if not isinstance(row, (tuple, list)) or len(row) != 1:
        raise MLBStep14CLeaseSchemaError(
            "lease schema probe returned an invalid shape"
        )
    if row[0] is not True:
        raise MLBStep14CLeaseSchemaError(
            "Step 14C requires its additive durable lease table"
        )


def verify_step14c_lease_schema(
    *,
    env: Mapping[str, str] | None = None,
    connection_factory: Callable[[], Any] | None = None,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    _assert_integrity(env)
    connection = _open_connection(env, connection_factory)
    cursor = None
    try:
        cursor = connection.cursor()
        _verify_lease_schema_with_cursor(cursor)
        _safe_rollback(connection)
    except (
        MLBStep14CDurableRuntimeDisabledError,
        MLBStep14CDurableRuntimeIntegrityError,
        MLBStep14CLeaseSchemaError,
    ):
        _safe_rollback(connection)
        raise
    except Exception as exc:
        _safe_rollback(connection)
        raise MLBStep14CDatabaseError(
            "Step 14C lease schema verification failed"
        ) from exc
    finally:
        _safe_close(cursor)
        _safe_close(connection)

    generated = (
        _utc_z(generated_at_utc, "generated_at_utc")[0]
        if generated_at_utc is not None
        else datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )
    result = {
        "data_type": SCHEMA_CHECK_DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "runtime_version": RUNTIME_VERSION,
        "runtime_status": RUNTIME_STATUS,
        "runtime_mode": RUNTIME_MODE,
        "database_schema": DATABASE_SCHEMA_NAME,
        "lease_table": LEASE_TABLE_NAME,
        "lease_sql_schema_sha256": LEASE_SQL_SCHEMA_SHA256,
        "table_present": True,
        "database_write_performed": False,
        "schema_auto_apply_performed": False,
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


def lease_key_for_slate(slate_date: str | date) -> str:
    return step14a.checkpoint_key_for_slate(slate_date) + ":scheduler-recovery-lease"


def _normalize_lease_row(
    row: Any,
    *,
    expected_key: str,
    expected_owner: str | None = None,
    expected_token: str | None = None,
    expected_generation: int | None = None,
) -> dict[str, Any]:
    if not isinstance(row, (tuple, list)) or len(row) != 7:
        raise MLBStep14CDurableRuntimeIntegrityError(
            "lease query returned an invalid row shape"
        )
    key, owner, token, generation, acquired_at, renewed_at, expires_at = row
    key = str(key or "")
    owner = str(owner or "")
    try:
        token = str(UUID(str(token)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise MLBStep14CDurableRuntimeIntegrityError(
            "lease token is not a valid UUID"
        ) from exc
    if isinstance(generation, bool) or not isinstance(generation, int) or generation < 1:
        raise MLBStep14CDurableRuntimeIntegrityError(
            "fencing generation is invalid"
        )
    acquired_text, acquired = _utc_z(acquired_at, "lease acquired_at")
    renewed_text, renewed = _utc_z(renewed_at, "lease renewed_at")
    expires_text, expires = _utc_z(expires_at, "lease expires_at")
    if not (acquired <= renewed < expires):
        raise MLBStep14CDurableRuntimeIntegrityError(
            "lease timestamps are inconsistent"
        )
    checks = [key == expected_key, 1 <= len(owner) <= 255]
    if expected_owner is not None:
        checks.append(owner == expected_owner)
    if expected_token is not None:
        try:
            checks.append(token == str(UUID(str(expected_token))))
        except (ValueError, TypeError, AttributeError) as exc:
            raise MLBStep14CDurableRuntimeIntegrityError(
                "expected lease token is invalid"
            ) from exc
    if expected_generation is not None:
        checks.append(generation == expected_generation)
    if not all(checks):
        raise MLBStep14CDurableRuntimeIntegrityError(
            "lease ownership/fencing row mismatch"
        )
    return {
        "lease_key": key,
        "owner_id": owner,
        "lease_token": token,
        "fencing_generation": generation,
        "acquired_at_utc": acquired_text,
        "renewed_at_utc": renewed_text,
        "expires_at_utc": expires_text,
    }


def acquire_step14c_lease(
    *,
    slate_date: str | date,
    owner_id: str,
    lease_ttl_seconds: int = DEFAULT_LEASE_TTL_SECONDS,
    env: Mapping[str, str] | None = None,
    connection_factory: Callable[[], Any] | None = None,
    token_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    _assert_integrity(env)
    owner = _owner_id(owner_id)
    ttl = _strict_positive_int(
        lease_ttl_seconds, "lease_ttl_seconds",
        MIN_LEASE_TTL_SECONDS, MAX_LEASE_TTL_SECONDS,
    )
    lease_key = lease_key_for_slate(slate_date)
    raw_token = (token_factory or uuid4)()
    try:
        token = str(UUID(str(raw_token)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise MLBStep14CDurableRuntimeInputError(
            "token_factory must return a UUID value"
        ) from exc

    connection = _open_connection(env, connection_factory)
    cursor = None
    try:
        cursor = connection.cursor()
        _verify_lease_schema_with_cursor(cursor)
        cursor.execute(_ACQUIRE_LEASE_SQL, (lease_key, owner, token, ttl, ttl))
        row = cursor.fetchone()
        if row is None:
            _safe_rollback(connection)
            raise MLBStep14CLeaseUnavailableError(
                "Step 14C refuses a duplicate cross-process slate run "
                "while an unexpired lease exists"
            )
        handle = _normalize_lease_row(
            row, expected_key=lease_key,
            expected_owner=owner, expected_token=token,
        )
        connection.commit()
        return handle
    except (
        MLBStep14CDurableRuntimeDisabledError,
        MLBStep14CDurableRuntimeInputError,
        MLBStep14CDurableRuntimeIntegrityError,
        MLBStep14CLeaseSchemaError,
        MLBStep14CLeaseUnavailableError,
    ):
        _safe_rollback(connection)
        raise
    except Exception as exc:
        _safe_rollback(connection)
        raise MLBStep14CDatabaseError("durable lease acquisition failed") from exc
    finally:
        _safe_close(cursor)
        _safe_close(connection)


def _validated_handle(handle: Mapping[str, Any]) -> tuple[str, str, str, int]:
    if not isinstance(handle, Mapping):
        raise MLBStep14CDurableRuntimeInputError("lease handle must be a mapping")
    key = str(handle.get("lease_key") or "").strip()
    owner = _owner_id(handle.get("owner_id"))
    if not key or len(key) > 255:
        raise MLBStep14CDurableRuntimeInputError(
            "lease handle key must contain 1 through 255 characters"
        )
    try:
        token = str(UUID(str(handle.get("lease_token"))))
    except (ValueError, TypeError, AttributeError) as exc:
        raise MLBStep14CDurableRuntimeInputError(
            "lease handle token is invalid"
        ) from exc
    generation = _strict_positive_int(
        handle.get("fencing_generation"), "fencing_generation",
        1, 9_223_372_036_854_775_807,
    )
    return key, owner, token, generation


def renew_step14c_lease(
    *,
    handle: Mapping[str, Any],
    lease_ttl_seconds: int = DEFAULT_LEASE_TTL_SECONDS,
    env: Mapping[str, str] | None = None,
    connection_factory: Callable[[], Any] | None = None,
) -> dict[str, Any]:
    _assert_integrity(env)
    key, owner, token, generation = _validated_handle(handle)
    ttl = _strict_positive_int(
        lease_ttl_seconds, "lease_ttl_seconds",
        MIN_LEASE_TTL_SECONDS, MAX_LEASE_TTL_SECONDS,
    )
    connection = _open_connection(env, connection_factory)
    cursor = None
    try:
        cursor = connection.cursor()
        _verify_lease_schema_with_cursor(cursor)
        cursor.execute(_RENEW_LEASE_SQL, (ttl, key, owner, token, generation))
        row = cursor.fetchone()
        if row is None:
            _safe_rollback(connection)
            raise MLBStep14CLeaseLostError(
                "lease ownership was lost or expired; stale process is fenced"
            )
        renewed = _normalize_lease_row(
            row, expected_key=key, expected_owner=owner,
            expected_token=token, expected_generation=generation,
        )
        connection.commit()
        return renewed
    except (
        MLBStep14CDurableRuntimeDisabledError,
        MLBStep14CDurableRuntimeInputError,
        MLBStep14CDurableRuntimeIntegrityError,
        MLBStep14CLeaseSchemaError,
        MLBStep14CLeaseLostError,
    ):
        _safe_rollback(connection)
        raise
    except Exception as exc:
        _safe_rollback(connection)
        raise MLBStep14CDatabaseError("durable lease renewal failed") from exc
    finally:
        _safe_close(cursor)
        _safe_close(connection)


def release_step14c_lease(
    *,
    handle: Mapping[str, Any],
    env: Mapping[str, str] | None = None,
    connection_factory: Callable[[], Any] | None = None,
) -> bool:
    _assert_integrity(env)
    key, owner, token, generation = _validated_handle(handle)
    connection = _open_connection(env, connection_factory)
    cursor = None
    try:
        cursor = connection.cursor()
        _verify_lease_schema_with_cursor(cursor)
        cursor.execute(_RELEASE_LEASE_SQL, (key, owner, token, generation))
        row = cursor.fetchone()
        if not isinstance(row, (tuple, list)) or len(row) != 1 or str(row[0]) != key:
            _safe_rollback(connection)
            raise MLBStep14CLeaseLostError(
                "stale lease owner cannot release a newer/expired lease"
            )
        connection.commit()
        return True
    except (
        MLBStep14CDurableRuntimeDisabledError,
        MLBStep14CDurableRuntimeInputError,
        MLBStep14CDurableRuntimeIntegrityError,
        MLBStep14CLeaseSchemaError,
        MLBStep14CLeaseLostError,
    ):
        _safe_rollback(connection)
        raise
    except Exception as exc:
        _safe_rollback(connection)
        raise MLBStep14CDatabaseError("durable lease release failed") from exc
    finally:
        _safe_close(cursor)
        _safe_close(connection)


def _restart_context_hash_surface(context: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: deepcopy(value) for key, value in context.items()
        if key not in {"generated_at_utc", "restart_context_sha256"}
    }


def _persist_result_hash_surface(result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: deepcopy(value) for key, value in result.items()
        if key not in {"generated_at_utc", "persist_result_sha256"}
    }


def _lineage() -> dict[str, Any]:
    return {
        "step14c_base_main_sha": STEP14C_BASE_MAIN_SHA,
        "step14b_merge_sha": STEP14B_MERGE_SHA,
        "step14b_source_blob_sha": STEP14B_SOURCE_BLOB_SHA,
        "step14b_final_certification_marker": step14b.FINAL_CERTIFICATION_MARKER,
        "step14a_final_certification_marker": step14a.FINAL_CERTIFICATION_MARKER,
        "lease_sql_schema_sha256": LEASE_SQL_SCHEMA_SHA256,
    }


def _guardrails() -> dict[str, Any]:
    return {
        "explicit_foreground_restart_context": True,
        "durable_restart_recovery": True,
        "durable_distributed_lease": True,
        "cross_process_duplicate_run_guard": True,
        "fencing_generation_enforced": True,
        "lease_expiry_enforced": True,
        "lease_revalidated_before_checkpoint_save": True,
        "checkpoint_cas_enforced": True,
        "append_only_checkpoint_history": True,
        "schema_auto_apply": False,
        "persistence_runtime_enabled": False,
        "automatic_restart_execution": False,
        "automatic_production_restart_activation": False,
        "production_activation": False,
        "public_api_activation": False,
        "actionable_output": False,
        "background_worker": False,
        "background_thread": False,
        "supabase_rest_write": False,
        "runtime_cycle_executed": False,
        "retry_executed": False,
        "restart_executed": False,
        "provider_network_calls": 0,
        "sportsbook_network_calls": 0,
    }


def _validated_step14b_result(result: Mapping[str, Any]) -> dict[str, Any]:
    validation = step14b.validate_step14b_adapter_result(result)
    if validation.get("result_valid") is not True:
        raise MLBStep14CDurableRuntimeIntegrityError(
            "Step 14B adapter result failed validation: "
            + repr(validation.get("failures"))
        )
    return deepcopy(dict(result))


def load_step14c_restart_context(
    *,
    slate_date: str | date,
    owner_id: str,
    lease_ttl_seconds: int = DEFAULT_LEASE_TTL_SECONDS,
    env: Mapping[str, str] | None = None,
    lease_connection_factory: Callable[[], Any] | None = None,
    checkpoint_connection_factory: Callable[[], Any] | None = None,
    token_factory: Callable[[], Any] | None = None,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    """Acquire the slate lease, then load the exact durable restart checkpoint."""
    _assert_integrity(env)
    lease = acquire_step14c_lease(
        slate_date=slate_date,
        owner_id=owner_id,
        lease_ttl_seconds=lease_ttl_seconds,
        env=env,
        connection_factory=lease_connection_factory,
        token_factory=token_factory,
    )
    try:
        loaded = step14b.load_step14b_checkpoint(
            slate_date=slate_date,
            env=_step14b_env(env),
            connection_factory=checkpoint_connection_factory,
            generated_at_utc=generated_at_utc,
        )
        loaded = _validated_step14b_result(loaded)
    except Exception:
        try:
            release_step14c_lease(
                handle=lease, env=env,
                connection_factory=lease_connection_factory,
            )
        except Exception:
            pass
        raise

    generated = (
        _utc_z(generated_at_utc, "generated_at_utc")[0]
        if generated_at_utc is not None
        else datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )
    context: dict[str, Any] = {
        "data_type": RESTART_CONTEXT_DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "runtime_version": RUNTIME_VERSION,
        "runtime_status": RUNTIME_STATUS,
        "runtime_mode": RUNTIME_MODE,
        "status": "recovered" if loaded["found"] else "fresh_start",
        "slate_date": loaded["slate_date"],
        "checkpoint_key": loaded["checkpoint_key"],
        "found": bool(loaded["found"]),
        "loaded_checkpoint_version": loaded["checkpoint_version"],
        "expected_head_version": int(loaded["checkpoint_version"] or 0),
        "checkpoint_id": loaded["checkpoint_id"],
        "envelope_content_sha256": loaded["envelope_content_sha256"],
        "scheduler_state_sha256": loaded["scheduler_state_sha256"],
        "recovery_state_sha256": loaded["recovery_state_sha256"],
        "recovery_handoff_sha256": loaded["recovery_handoff_sha256"],
        "checkpoint_envelope": deepcopy(loaded["checkpoint_envelope"]),
        "scheduler_state_for_restart": deepcopy(loaded["scheduler_state_for_restart"]),
        "recovery_state_for_restart": deepcopy(loaded["recovery_state_for_restart"]),
        "recovery_handoff_for_restart": deepcopy(loaded["recovery_handoff_for_restart"]),
        "lease": deepcopy(lease),
        "lineage": _lineage(),
        "guardrails": _guardrails(),
        "generated_at_utc": generated,
    }
    context["restart_context_sha256"] = _hash(_restart_context_hash_surface(context))
    validation = validate_step14c_restart_context(context)
    if validation.get("context_valid") is not True:
        try:
            release_step14c_lease(
                handle=lease, env=env,
                connection_factory=lease_connection_factory,
            )
        except Exception:
            pass
        raise MLBStep14CDurableRuntimeIntegrityError(
            "built restart context failed self-validation: "
            + repr(validation.get("failures"))
        )
    return context


def validate_step14c_restart_context(
    context: Mapping[str, Any] | None,
) -> dict[str, Any]:
    failures: list[str] = []
    if not isinstance(context, Mapping):
        return {
            "data_type": RESTART_CONTEXT_DATA_TYPE,
            "schema_version": SCHEMA_VERSION,
            "context_valid": False,
            "failures": ["STEP14C_CONTEXT_NOT_MAPPING"],
        }
    value = dict(context)
    missing = sorted(_RESTART_CONTEXT_KEYS - set(value))
    unknown = sorted(set(value) - _RESTART_CONTEXT_KEYS)
    if missing:
        failures.append("STEP14C_CONTEXT_MISSING_KEYS:" + ",".join(missing))
    if unknown:
        failures.append("STEP14C_CONTEXT_UNKNOWN_KEYS:" + ",".join(unknown))
    if failures:
        return {
            "data_type": RESTART_CONTEXT_DATA_TYPE,
            "schema_version": SCHEMA_VERSION,
            "context_valid": False,
            "failures": failures,
        }

    try:
        exact = {
            "data_type": value["data_type"] == RESTART_CONTEXT_DATA_TYPE,
            "schema_version": value["schema_version"] == SCHEMA_VERSION,
            "runtime_version": value["runtime_version"] == RUNTIME_VERSION,
            "runtime_status": value["runtime_status"] == RUNTIME_STATUS,
            "runtime_mode": value["runtime_mode"] == RUNTIME_MODE,
            "checkpoint_key": value["checkpoint_key"]
            == step14a.checkpoint_key_for_slate(value["slate_date"]),
            "lineage": value["lineage"] == _lineage(),
            "guardrails": value["guardrails"] == _guardrails(),
        }
        bad = [name for name, ok in exact.items() if not ok]
        if bad:
            raise MLBStep14CDurableRuntimeIntegrityError(
                "restart context contract drift: " + ", ".join(bad)
            )
        _utc_z(value["generated_at_utc"], "generated_at_utc")
        digest = _valid_sha256(value["restart_context_sha256"], "restart_context_sha256")
        if digest != _hash(_restart_context_hash_surface(value)):
            raise MLBStep14CDurableRuntimeIntegrityError(
                "restart context content hash mismatch"
            )

        lease = value.get("lease")
        key, _owner, _token, _generation = _validated_handle(lease)
        if key != lease_key_for_slate(value["slate_date"]):
            raise MLBStep14CDurableRuntimeIntegrityError(
                "restart context lease key/slate mismatch"
            )

        version = value["expected_head_version"]
        if isinstance(version, bool) or not isinstance(version, int) or version < 0:
            raise MLBStep14CDurableRuntimeIntegrityError(
                "expected_head_version is invalid"
            )

        if value["found"] is True:
            if value["status"] != "recovered":
                raise MLBStep14CDurableRuntimeIntegrityError(
                    "found context must have recovered status"
                )
            if value["loaded_checkpoint_version"] != version or version < 1:
                raise MLBStep14CDurableRuntimeIntegrityError(
                    "loaded checkpoint version mismatch"
                )
            envelope = value["checkpoint_envelope"]
            validation = step14a.validate_step14a_checkpoint_envelope(
                envelope, expected_slate_date=value["slate_date"],
            )
            if validation.get("envelope_valid") is not True:
                raise MLBStep14CDurableRuntimeIntegrityError(
                    "restart checkpoint envelope failed Step 14A validation"
                )
            checks = {
                "checkpoint_id": value["checkpoint_id"]
                == step14b.checkpoint_id_for_envelope(envelope),
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
            mismatch = [name for name, ok in checks.items() if not ok]
            if mismatch:
                raise MLBStep14CDurableRuntimeIntegrityError(
                    "restart context/envelope mismatch: " + ", ".join(mismatch)
                )
        else:
            if value["status"] != "fresh_start":
                raise MLBStep14CDurableRuntimeIntegrityError(
                    "not-found context must have fresh_start status"
                )
            if version != 0 or value["loaded_checkpoint_version"] is not None:
                raise MLBStep14CDurableRuntimeIntegrityError(
                    "fresh-start context must begin at version zero"
                )
            nullable = (
                "checkpoint_id", "envelope_content_sha256",
                "scheduler_state_sha256", "recovery_state_sha256",
                "recovery_handoff_sha256", "checkpoint_envelope",
                "scheduler_state_for_restart", "recovery_state_for_restart",
                "recovery_handoff_for_restart",
            )
            if any(value[key] is not None for key in nullable):
                raise MLBStep14CDurableRuntimeIntegrityError(
                    "fresh-start context carries durable checkpoint state"
                )
    except Exception as exc:
        failures.append(
            f"STEP14C_CONTEXT_INVALID:{type(exc).__name__}:{exc}"
        )

    return {
        "data_type": RESTART_CONTEXT_DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "context_valid": not failures,
        "failures": failures,
    }


def restart_inputs_from_context(context: Mapping[str, Any]) -> dict[str, Any]:
    validation = validate_step14c_restart_context(context)
    if validation.get("context_valid") is not True:
        raise MLBStep14CDurableRuntimeIntegrityError(
            "cannot extract restart inputs from invalid context: "
            + repr(validation.get("failures"))
        )
    return {
        "scheduler_state": deepcopy(context["scheduler_state_for_restart"]),
        "recovery_state": deepcopy(context["recovery_state_for_restart"]),
        "recovery_handoff": deepcopy(context["recovery_handoff_for_restart"]),
        "expected_head_version": context["expected_head_version"],
        "checkpoint_key": context["checkpoint_key"],
        "lease": deepcopy(context["lease"]),
    }


def persist_step14c_checkpoint_under_lease(
    *,
    restart_context: Mapping[str, Any],
    checkpoint_envelope: Mapping[str, Any],
    lease_ttl_seconds: int = DEFAULT_LEASE_TTL_SECONDS,
    env: Mapping[str, str] | None = None,
    lease_connection_factory: Callable[[], Any] | None = None,
    checkpoint_connection_factory: Callable[[], Any] | None = None,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    """Revalidate ownership, then append/save one Step 14A checkpoint via Step 14B."""
    _assert_integrity(env)
    validation = validate_step14c_restart_context(restart_context)
    if validation.get("context_valid") is not True:
        raise MLBStep14CDurableRuntimeIntegrityError(
            "invalid restart context: " + repr(validation.get("failures"))
        )
    context = dict(restart_context)

    envelope_validation = step14a.validate_step14a_checkpoint_envelope(
        checkpoint_envelope, expected_slate_date=context["slate_date"],
    )
    if envelope_validation.get("envelope_valid") is not True:
        raise MLBStep14CDurableRuntimeIntegrityError(
            "checkpoint envelope failed frozen Step 14A validation: "
            + repr(envelope_validation.get("failures"))
        )
    envelope = deepcopy(dict(checkpoint_envelope))
    if envelope["checkpoint_key"] != context["checkpoint_key"]:
        raise MLBStep14CDurableRuntimeIntegrityError(
            "checkpoint envelope belongs to a different restart context"
        )

    renewed = renew_step14c_lease(
        handle=context["lease"],
        lease_ttl_seconds=lease_ttl_seconds,
        env=env,
        connection_factory=lease_connection_factory,
    )
    saved = step14b.save_step14b_checkpoint(
        checkpoint_envelope=envelope,
        expected_head_version=context["expected_head_version"],
        env=_step14b_env(env),
        connection_factory=checkpoint_connection_factory,
        generated_at_utc=generated_at_utc,
    )
    saved = _validated_step14b_result(saved)

    generated = (
        _utc_z(generated_at_utc, "generated_at_utc")[0]
        if generated_at_utc is not None
        else datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )
    result: dict[str, Any] = {
        "data_type": PERSIST_RESULT_DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "runtime_version": RUNTIME_VERSION,
        "runtime_status": RUNTIME_STATUS,
        "runtime_mode": RUNTIME_MODE,
        "status": "persisted",
        "slate_date": context["slate_date"],
        "checkpoint_key": context["checkpoint_key"],
        "previous_checkpoint_version": context["expected_head_version"],
        "saved_checkpoint_version": saved["checkpoint_version"],
        "saved_checkpoint_status": saved["status"],
        "saved_checkpoint_id": saved["checkpoint_id"],
        "saved_envelope_content_sha256": saved["envelope_content_sha256"],
        "scheduler_state_sha256": saved["scheduler_state_sha256"],
        "recovery_state_sha256": saved["recovery_state_sha256"],
        "recovery_handoff_sha256": saved["recovery_handoff_sha256"],
        "lease": deepcopy(renewed),
        "lineage": _lineage(),
        "guardrails": _guardrails(),
        "generated_at_utc": generated,
    }
    result["persist_result_sha256"] = _hash(_persist_result_hash_surface(result))
    validation = validate_step14c_persist_result(result)
    if validation.get("result_valid") is not True:
        raise MLBStep14CDurableRuntimeIntegrityError(
            "built persist result failed self-validation: "
            + repr(validation.get("failures"))
        )
    return result


def validate_step14c_persist_result(
    result: Mapping[str, Any] | None,
) -> dict[str, Any]:
    failures: list[str] = []
    if not isinstance(result, Mapping):
        return {
            "data_type": PERSIST_RESULT_DATA_TYPE,
            "schema_version": SCHEMA_VERSION,
            "result_valid": False,
            "failures": ["STEP14C_PERSIST_RESULT_NOT_MAPPING"],
        }
    value = dict(result)
    missing = sorted(_PERSIST_RESULT_KEYS - set(value))
    unknown = sorted(set(value) - _PERSIST_RESULT_KEYS)
    if missing:
        failures.append("STEP14C_PERSIST_RESULT_MISSING_KEYS:" + ",".join(missing))
    if unknown:
        failures.append("STEP14C_PERSIST_RESULT_UNKNOWN_KEYS:" + ",".join(unknown))
    if failures:
        return {
            "data_type": PERSIST_RESULT_DATA_TYPE,
            "schema_version": SCHEMA_VERSION,
            "result_valid": False,
            "failures": failures,
        }

    try:
        exact = {
            "data_type": value["data_type"] == PERSIST_RESULT_DATA_TYPE,
            "schema_version": value["schema_version"] == SCHEMA_VERSION,
            "runtime_version": value["runtime_version"] == RUNTIME_VERSION,
            "runtime_status": value["runtime_status"] == RUNTIME_STATUS,
            "runtime_mode": value["runtime_mode"] == RUNTIME_MODE,
            "status": value["status"] == "persisted",
            "checkpoint_key": value["checkpoint_key"]
            == step14a.checkpoint_key_for_slate(value["slate_date"]),
            "lineage": value["lineage"] == _lineage(),
            "guardrails": value["guardrails"] == _guardrails(),
        }
        bad = [name for name, ok in exact.items() if not ok]
        if bad:
            raise MLBStep14CDurableRuntimeIntegrityError(
                "persist result contract drift: " + ", ".join(bad)
            )
        _utc_z(value["generated_at_utc"], "generated_at_utc")
        digest = _valid_sha256(value["persist_result_sha256"], "persist_result_sha256")
        if digest != _hash(_persist_result_hash_surface(value)):
            raise MLBStep14CDurableRuntimeIntegrityError(
                "persist result content hash mismatch"
            )
        key, _owner, _token, _generation = _validated_handle(value["lease"])
        if key != lease_key_for_slate(value["slate_date"]):
            raise MLBStep14CDurableRuntimeIntegrityError(
                "persist result lease key/slate mismatch"
            )

        previous = value["previous_checkpoint_version"]
        saved_version = value["saved_checkpoint_version"]
        if (
            isinstance(previous, bool) or not isinstance(previous, int) or previous < 0
            or isinstance(saved_version, bool) or not isinstance(saved_version, int)
            or saved_version < 1
        ):
            raise MLBStep14CDurableRuntimeIntegrityError(
                "persist result checkpoint version invalid"
            )
        if value["saved_checkpoint_status"] == "idempotent":
            if saved_version < previous:
                raise MLBStep14CDurableRuntimeIntegrityError(
                    "idempotent persist version moved backwards"
                )
        elif value["saved_checkpoint_status"] in {"created", "advanced"}:
            if saved_version != previous + 1:
                raise MLBStep14CDurableRuntimeIntegrityError(
                    "persisted checkpoint version did not advance exactly one"
                )
        else:
            raise MLBStep14CDurableRuntimeIntegrityError(
                "unexpected Step 14B save status"
            )
        for field in (
            "saved_envelope_content_sha256", "scheduler_state_sha256",
            "recovery_state_sha256", "recovery_handoff_sha256",
        ):
            _valid_sha256(value[field], field)
        try:
            UUID(str(value["saved_checkpoint_id"]))
        except (ValueError, TypeError, AttributeError) as exc:
            raise MLBStep14CDurableRuntimeIntegrityError(
                "saved checkpoint id is not a UUID"
            ) from exc
    except Exception as exc:
        failures.append(
            f"STEP14C_PERSIST_RESULT_INVALID:{type(exc).__name__}:{exc}"
        )

    return {
        "data_type": PERSIST_RESULT_DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "result_valid": not failures,
        "failures": failures,
    }


__all__ = [
    "ACTIONABLE_OUTPUT_ALLOWED",
    "AUTOMATIC_PRODUCTION_RESTART_ACTIVATION_ALLOWED",
    "AUTOMATIC_RESTART_EXECUTION_ALLOWED",
    "BACKGROUND_THREAD_ALLOWED",
    "BACKGROUND_WORKER_ALLOWED",
    "CHECKPOINT_CAS_REQUIRED",
    "CHECKPOINT_PERSIST_UNDER_LEASE_ALLOWED",
    "CROSS_PROCESS_DUPLICATE_RUN_GUARD_ALLOWED",
    "DATA_TYPE",
    "DEFAULT_ENABLED",
    "DEFAULT_LEASE_TTL_SECONDS",
    "DURABLE_DISTRIBUTED_LEASE_ALLOWED",
    "DURABLE_RESTART_RECOVERY_ALLOWED",
    "FINAL_CERTIFICATION_MARKER",
    "FENCING_GENERATION_REQUIRED",
    "FOREGROUND_DURABLE_RESTART_CONTEXT_ALLOWED",
    "LEASE_EXPIRY_REQUIRED",
    "LEASE_REVALIDATION_BEFORE_SAVE_REQUIRED",
    "LEASE_SQL_SCHEMA_PATH",
    "LEASE_SQL_SCHEMA_SHA256",
    "LEASE_TABLE_NAME",
    "MAX_LEASE_TTL_SECONDS",
    "MIN_LEASE_TTL_SECONDS",
    "MLBStep14CDatabaseError",
    "MLBStep14CDurableRuntimeDisabledError",
    "MLBStep14CDurableRuntimeInputError",
    "MLBStep14CDurableRuntimeIntegrityError",
    "MLBStep14CLeaseLostError",
    "MLBStep14CLeaseSchemaError",
    "MLBStep14CLeaseUnavailableError",
    "PERSISTENCE_RUNTIME_ENABLED",
    "PERSIST_RESULT_DATA_TYPE",
    "PRODUCTION_ACTIVATION_ALLOWED",
    "PUBLIC_API_ACTIVATION_ALLOWED",
    "RESTART_CONTEXT_DATA_TYPE",
    "RUNTIME_MODE",
    "RUNTIME_STATUS",
    "RUNTIME_VERSION",
    "SCHEMA_AUTO_APPLY_ALLOWED",
    "SCHEMA_VERSION",
    "STEP14B_MERGE_SHA",
    "STEP14B_SOURCE_BLOB_SHA",
    "STEP14C_BASE_MAIN_SHA",
    "STEP14C_DURABLE_RESTART_LEASE_ENABLED_ENV",
    "SUPABASE_REST_WRITE_ALLOWED",
    "acquire_step14c_lease",
    "durable_restart_lease_manifest",
    "lease_key_for_slate",
    "load_step14c_restart_context",
    "persist_step14c_checkpoint_under_lease",
    "release_step14c_lease",
    "renew_step14c_lease",
    "restart_inputs_from_context",
    "step14c_durable_restart_lease_enabled",
    "validate_durable_restart_lease_manifest",
    "validate_step14c_persist_result",
    "validate_step14c_restart_context",
    "verify_step14c_lease_schema",
]
