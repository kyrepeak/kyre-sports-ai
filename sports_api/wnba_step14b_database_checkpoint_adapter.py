"""WNBA Step 14B: PostgreSQL durable checkpoint adapter.

Step 14A froze the checkpoint envelope and relational schema. Step 14B is the
first layer allowed to perform isolated database reads/writes against that exact
contract. It adds transaction-scoped checkpoint save/load with append-only
history and optimistic compare-and-swap (CAS) movement of the slate head.

This module still does NOT activate persistence inside the Step-13 runtime,
perform durable restart recovery, create distributed leases, expose a public
route, run a background daemon, or enable production/wagering. Those remain
later Step-14/deployment boundaries.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any
from uuid import UUID, NAMESPACE_URL, uuid5

from sports_api import wnba_step14a_persistence_contract as step14a

SOURCE = "Kyre Sports API WNBA Step 14B PostgreSQL checkpoint adapter"
SCHEMA_VERSION = "wnba_step_14b_database_checkpoint_adapter_v1"
ADAPTER_VERSION = "wnba_step14b_postgresql_checkpoint_adapter_2026_regular_v1"
BRANCH = "wnba-step14b-database-checkpoint-adapter-20260828"
SEASON = 2026
SEASON_TYPE = "Regular Season"

STEP14A_FROZEN_SHA = "aa1d770cd9840dac7e31139ab177fa4aa3ac9020"
STEP14A_CONTRACT_ID = step14a.CONTRACT_ID
STEP14A_MANIFEST_CONTENT_SHA256 = "2768d83f2bccb8cf1e47318c0910d4758fdeb68916683e67db92ffb282bea2e1"
STEP14A_SQL_SCHEMA_SHA256 = "308042f8196607a477158d348ba6e03e090267910cba749491534131b490a2eb"
STEP13_RELEASE_ID = step14a.STEP13_RELEASE_ID
STEP13_RELEASE_CONTENT_SHA256 = step14a.STEP13_RELEASE_CONTENT_SHA256
STEP13D_FROZEN_SHA = step14a.STEP13D_FROZEN_SHA
STEP13C_FROZEN_SHA = step14a.STEP13C_FROZEN_SHA

DATABASE_SCHEMA_NAME = step14a.DATABASE_SCHEMA_NAME
CHECKPOINT_TABLE_NAME = step14a.CHECKPOINT_TABLE_NAME
CHECKPOINT_HEAD_TABLE_NAME = step14a.CHECKPOINT_HEAD_TABLE_NAME
DATABASE_URL_ENV = "KYRE_DATABASE_URL"

STEP14B_DATABASE_CHECKPOINT_ADAPTER_ENABLED_ENV = (
    "WNBA_STEP14B_DATABASE_CHECKPOINT_ADAPTER_ENABLED"
)
STEP14B_DATABASE_READ_ENABLED_ENV = "WNBA_STEP14B_DATABASE_READ_ENABLED"
STEP14B_DATABASE_WRITE_ENABLED_ENV = "WNBA_STEP14B_DATABASE_WRITE_ENABLED"

DEFAULT_ENABLED = False
POSTGRESQL_DATABASE_READ_ALLOWED = True
POSTGRESQL_DATABASE_WRITE_ALLOWED = True
CHECKPOINT_LOAD_ALLOWED = True
CHECKPOINT_SAVE_ALLOWED = True
ATOMIC_HEAD_COMPARE_AND_SWAP_ALLOWED = True
APPEND_ONLY_HISTORY_REQUIRED = True
SUPABASE_POSTGRES_COMPATIBLE = True
PERSISTENCE_RUNTIME_ENABLED = False
SUPABASE_REST_WRITE_ALLOWED = False
DURABLE_RESTART_RECOVERY_ALLOWED = False
DURABLE_DISTRIBUTED_LEASE_ALLOWED = False
CROSS_PROCESS_DUPLICATE_RUN_GUARD_ALLOWED = False
PRODUCTION_ACTIVATION_ALLOWED = False
PUBLIC_FASTAPI_ACTIVATION_ALLOWED = False
WAGERING_ALLOWED = False
AUTHENTICATION_ALLOWED = False
COOKIES_ALLOWED = False
BACKGROUND_DAEMON_ALLOWED = False
BACKGROUND_THREAD_ALLOWED = False
BASKETBALL_MODEL_MUTATION_ALLOWED = False
RANKING_MUTATION_ALLOWED = False

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

_SCHEMA_EXISTENCE_SQL = """
SELECT
    to_regclass(%s) IS NOT NULL,
    to_regclass(%s) IS NOT NULL
""".strip()

_HEAD_SELECT_SQL = f"""
SELECT
    h.checkpoint_version,
    h.checkpoint_id::text,
    h.envelope_content_sha256::text,
    c.checkpoint_version,
    c.checkpoint_id::text,
    c.checkpoint_key,
    c.slate_date::text,
    c.step13d_frozen_sha,
    c.step13_release_id,
    c.step13_release_content_sha256,
    c.source_step13c_frozen_sha,
    c.source_reliability_content_sha256,
    c.controller_state_sha256,
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
    step13d_frozen_sha,
    step13_release_id,
    step13_release_content_sha256,
    source_step13c_frozen_sha,
    source_reliability_content_sha256,
    controller_state_sha256,
    envelope_content_sha256,
    envelope_json,
    created_at
) VALUES (
    %s, %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s, %s, %s,
    %s::jsonb, %s
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

_RESULT_REQUIRED_FIELDS = {
    "data_type",
    "schema_version",
    "adapter_version",
    "operation",
    "status",
    "found",
    "slate_date",
    "checkpoint_key",
    "checkpoint_version",
    "checkpoint_id",
    "envelope_content_sha256",
    "controller_state_sha256",
    "checkpoint_envelope",
    "controller_state_for_restart",
    "lineage",
    "guardrails",
    "generated_at_utc",
    "adapter_content_sha256",
}


class WNBAStep14DatabaseAdapterDisabledError(RuntimeError):
    """Raised when the isolated Step-14B database gates are not enabled safely."""


class WNBAStep14DatabaseAdapterInputError(ValueError):
    """Raised when save/load input is malformed."""


class WNBAStep14DatabaseAdapterIntegrityError(RuntimeError):
    """Raised when frozen lineage, checkpoint content, or DB row integrity drifts."""


class WNBAStep14DatabaseSchemaError(RuntimeError):
    """Raised when the frozen Step-14A database tables are unavailable."""


class WNBAStep14DatabaseConflictError(RuntimeError):
    """Raised when optimistic head-version compare-and-swap detects a stale writer."""


class WNBAStep14DatabaseError(RuntimeError):
    """Raised for database connectivity/driver/transaction failures."""


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled"
    }


def step14b_database_checkpoint_adapter_enabled(
    env: Mapping[str, str] | None = None,
) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(STEP14B_DATABASE_CHECKPOINT_ADAPTER_ENABLED_ENV))


def step14b_database_read_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(STEP14B_DATABASE_READ_ENABLED_ENV))


def step14b_database_write_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(STEP14B_DATABASE_WRITE_ENABLED_ENV))


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


def _valid_sha256(value: Any) -> bool:
    text = str(value or "").strip().lower()
    return len(text) == 64 and all(ch in "0123456789abcdef" for ch in text)


def _parse_timestamp(value: Any, label: str) -> datetime:
    text = str(value or "").strip()
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise WNBAStep14DatabaseAdapterInputError(
            f"Step 14B {label} must be ISO-8601."
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise WNBAStep14DatabaseAdapterInputError(
            f"Step 14B {label} must be timezone-aware."
        )
    return parsed.astimezone(timezone.utc)


def _normalize_expected_version(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise WNBAStep14DatabaseAdapterInputError(
            "Step 14B expected_head_version must be an integer >= 0."
        )
    return value


def _assert_adapter_integrity(env: Mapping[str, str] | None = None) -> None:
    source = os.environ if env is None else env
    if not step14b_database_checkpoint_adapter_enabled(source):
        raise WNBAStep14DatabaseAdapterDisabledError(
            f"Step 14B requires {STEP14B_DATABASE_CHECKPOINT_ADAPTER_ENABLED_ENV}=true."
        )
    bad = [name for name in _FORBIDDEN_TRUE_ENV_KEYS if _truthy(source.get(name))]
    if bad:
        raise WNBAStep14DatabaseAdapterDisabledError(
            "Step 14B refuses production/global-persistence/wagering switches: "
            + ", ".join(bad)
        )
    missing = [name for name in _REQUIRED_TRUE_ENV_KEYS if not _truthy(source.get(name))]
    if missing:
        raise WNBAStep14DatabaseAdapterDisabledError(
            "Step 14B requires the frozen Step-14A/Step-13 runtime gates: "
            + ", ".join(missing)
        )

    if step14a.DATABASE_READ_ALLOWED is not False:
        raise WNBAStep14DatabaseAdapterIntegrityError(
            "Step 14B detected Step-14A database-read boundary drift."
        )
    if step14a.DATABASE_WRITE_ALLOWED is not False:
        raise WNBAStep14DatabaseAdapterIntegrityError(
            "Step 14B detected Step-14A database-write boundary drift."
        )
    if step14a.PERSISTENCE_RUNTIME_ENABLED is not False:
        raise WNBAStep14DatabaseAdapterIntegrityError(
            "Step 14B detected Step-14A persistence-runtime drift."
        )
    if step14a.STEP13_RELEASE_CONTENT_SHA256 != STEP13_RELEASE_CONTENT_SHA256:
        raise WNBAStep14DatabaseAdapterIntegrityError(
            "Step 14B frozen Step-13 release hash drift."
        )
    if step14a.CONTRACT_ID != STEP14A_CONTRACT_ID:
        raise WNBAStep14DatabaseAdapterIntegrityError(
            "Step 14B Step-14A contract identity drift."
        )

    manifest = step14a.build_step14a_schema_manifest(env=source)
    if manifest.get("manifest_content_sha256") != STEP14A_MANIFEST_CONTENT_SHA256:
        raise WNBAStep14DatabaseAdapterIntegrityError(
            "Step 14B frozen Step-14A schema-manifest hash drift."
        )
    sql_path = Path(step14a.SQL_SCHEMA_PATH)
    try:
        sql_hash = hashlib.sha256(sql_path.read_bytes()).hexdigest()
    except OSError as exc:
        raise WNBAStep14DatabaseAdapterIntegrityError(
            "Step 14B cannot read the frozen Step-14A SQL schema."
        ) from exc
    if sql_hash != STEP14A_SQL_SCHEMA_SHA256:
        raise WNBAStep14DatabaseAdapterIntegrityError(
            "Step 14B frozen Step-14A SQL schema hash drift."
        )

    false_capabilities = {
        "persistence_runtime": PERSISTENCE_RUNTIME_ENABLED,
        "supabase_rest_write": SUPABASE_REST_WRITE_ALLOWED,
        "durable_restart_recovery": DURABLE_RESTART_RECOVERY_ALLOWED,
        "durable_distributed_lease": DURABLE_DISTRIBUTED_LEASE_ALLOWED,
        "cross_process_duplicate_guard": CROSS_PROCESS_DUPLICATE_RUN_GUARD_ALLOWED,
        "production_activation": PRODUCTION_ACTIVATION_ALLOWED,
        "public_fastapi": PUBLIC_FASTAPI_ACTIVATION_ALLOWED,
        "wagering": WAGERING_ALLOWED,
        "authentication": AUTHENTICATION_ALLOWED,
        "cookies": COOKIES_ALLOWED,
        "background_daemon": BACKGROUND_DAEMON_ALLOWED,
        "background_thread": BACKGROUND_THREAD_ALLOWED,
        "basketball_model_mutation": BASKETBALL_MODEL_MUTATION_ALLOWED,
        "ranking_mutation": RANKING_MUTATION_ALLOWED,
    }
    drift = [name for name, value in false_capabilities.items() if value is not False]
    if drift:
        raise WNBAStep14DatabaseAdapterIntegrityError(
            "Step 14B forbidden capability drift: " + ", ".join(drift)
        )
    true_capabilities = {
        "postgres_read": POSTGRESQL_DATABASE_READ_ALLOWED,
        "postgres_write": POSTGRESQL_DATABASE_WRITE_ALLOWED,
        "checkpoint_load": CHECKPOINT_LOAD_ALLOWED,
        "checkpoint_save": CHECKPOINT_SAVE_ALLOWED,
        "head_cas": ATOMIC_HEAD_COMPARE_AND_SWAP_ALLOWED,
        "append_only_history": APPEND_ONLY_HISTORY_REQUIRED,
        "supabase_postgres_compatible": SUPABASE_POSTGRES_COMPATIBLE,
    }
    missing_true = [name for name, value in true_capabilities.items() if value is not True]
    if missing_true:
        raise WNBAStep14DatabaseAdapterIntegrityError(
            "Step 14B required adapter capability drift: " + ", ".join(missing_true)
        )


def _require_read(env: Mapping[str, str] | None) -> None:
    if not step14b_database_read_enabled(env):
        raise WNBAStep14DatabaseAdapterDisabledError(
            f"Step 14B reads require {STEP14B_DATABASE_READ_ENABLED_ENV}=true."
        )


def _require_write(env: Mapping[str, str] | None) -> None:
    if not step14b_database_write_enabled(env):
        raise WNBAStep14DatabaseAdapterDisabledError(
            f"Step 14B writes require {STEP14B_DATABASE_WRITE_ENABLED_ENV}=true."
        )


def checkpoint_id_for_envelope(envelope: Mapping[str, Any]) -> str:
    """Return deterministic UUIDv5 identity for one immutable checkpoint envelope."""
    if not isinstance(envelope, Mapping):
        raise WNBAStep14DatabaseAdapterInputError("Step 14B envelope must be an object.")
    key = str(envelope.get("checkpoint_key") or "").strip()
    digest = str(envelope.get("envelope_content_sha256") or "").strip().lower()
    if not key or not _valid_sha256(digest):
        raise WNBAStep14DatabaseAdapterInputError(
            "Step 14B checkpoint identity requires checkpoint_key and valid envelope hash."
        )
    return str(uuid5(NAMESPACE_URL, f"kyre-sports-ai:{key}:{digest}"))


def _open_connection(
    env: Mapping[str, str] | None,
    connection_factory: Callable[[], Any] | None,
) -> Any:
    if connection_factory is not None:
        try:
            connection = connection_factory()
        except Exception as exc:
            raise WNBAStep14DatabaseError(
                "Step 14B injected database connection factory failed."
            ) from exc
        if connection is None:
            raise WNBAStep14DatabaseError(
                "Step 14B database connection factory returned no connection."
            )
        return connection

    source = os.environ if env is None else env
    dsn = str(source.get(DATABASE_URL_ENV) or "").strip()
    if not dsn:
        raise WNBAStep14DatabaseAdapterDisabledError(
            f"Step 14B live PostgreSQL access requires {DATABASE_URL_ENV}; credentials are never embedded in code."
        )
    try:
        import psycopg  # type: ignore
    except ImportError as exc:
        raise WNBAStep14DatabaseError(
            "Step 14B live PostgreSQL access requires psycopg 3."
        ) from exc
    try:
        return psycopg.connect(
            dsn,
            connect_timeout=10,
            application_name="kyre-sports-ai-step14b",
        )
    except Exception as exc:
        raise WNBAStep14DatabaseError(
            "Step 14B could not open the PostgreSQL connection."
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
    code = getattr(exc, "sqlstate", None) or getattr(exc, "pgcode", None)
    return str(code or "") == "23505"


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
        raise WNBAStep14DatabaseSchemaError(
            "Step 14B schema probe returned an invalid shape."
        )
    if row[0] is not True or row[1] is not True:
        raise WNBAStep14DatabaseSchemaError(
            "Step 14B requires both frozen Step-14A checkpoint tables."
        )


def _decode_envelope(value: Any) -> dict[str, Any]:
    if isinstance(value, Mapping):
        raw = dict(value)
    elif isinstance(value, str):
        try:
            raw = json.loads(value)
        except json.JSONDecodeError as exc:
            raise WNBAStep14DatabaseAdapterIntegrityError(
                "Step 14B database envelope JSON is malformed."
            ) from exc
    else:
        raise WNBAStep14DatabaseAdapterIntegrityError(
            "Step 14B database envelope must be JSON object content."
        )
    if not isinstance(raw, dict):
        raise WNBAStep14DatabaseAdapterIntegrityError(
            "Step 14B database envelope did not decode to an object."
        )
    return raw


def _normalize_head_row(
    row: Any,
    *,
    env: Mapping[str, str] | None,
    expected_slate_date: str | date,
) -> dict[str, Any] | None:
    if row is None:
        return None
    if not isinstance(row, (tuple, list)) or len(row) != 15:
        raise WNBAStep14DatabaseAdapterIntegrityError(
            "Step 14B checkpoint-head query returned an invalid row shape."
        )
    (
        head_version,
        head_id,
        head_hash,
        history_version,
        history_id,
        history_key,
        history_slate,
        history_step13d_sha,
        history_release_id,
        history_release_hash,
        history_step13c_sha,
        history_source_hash,
        history_state_hash,
        history_envelope_hash,
        envelope_json,
    ) = row

    if isinstance(head_version, bool) or not isinstance(head_version, int) or head_version < 1:
        raise WNBAStep14DatabaseAdapterIntegrityError(
            "Step 14B persisted head version is invalid."
        )
    if history_version != head_version:
        raise WNBAStep14DatabaseAdapterIntegrityError(
            "Step 14B head/history version mismatch."
        )
    try:
        head_uuid = str(UUID(str(head_id)))
        history_uuid = str(UUID(str(history_id)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise WNBAStep14DatabaseAdapterIntegrityError(
            "Step 14B persisted checkpoint UUID is invalid."
        ) from exc
    if head_uuid != history_uuid:
        raise WNBAStep14DatabaseAdapterIntegrityError(
            "Step 14B head/history checkpoint UUID mismatch."
        )

    head_digest = str(head_hash or "").strip().lower()
    history_digest = str(history_envelope_hash or "").strip().lower()
    if not _valid_sha256(head_digest) or head_digest != history_digest:
        raise WNBAStep14DatabaseAdapterIntegrityError(
            "Step 14B head/history envelope-hash mismatch."
        )
    if history_step13d_sha != STEP13D_FROZEN_SHA:
        raise WNBAStep14DatabaseAdapterIntegrityError(
            "Step 14B persisted Step-13D lineage drift."
        )
    if history_release_id != STEP13_RELEASE_ID:
        raise WNBAStep14DatabaseAdapterIntegrityError(
            "Step 14B persisted Step-13 release identity drift."
        )
    if history_release_hash != STEP13_RELEASE_CONTENT_SHA256:
        raise WNBAStep14DatabaseAdapterIntegrityError(
            "Step 14B persisted Step-13 release hash drift."
        )
    if history_step13c_sha != STEP13C_FROZEN_SHA:
        raise WNBAStep14DatabaseAdapterIntegrityError(
            "Step 14B persisted Step-13C lineage drift."
        )
    if not _valid_sha256(history_source_hash) or not _valid_sha256(history_state_hash):
        raise WNBAStep14DatabaseAdapterIntegrityError(
            "Step 14B persisted source/controller hash is invalid."
        )

    envelope = _decode_envelope(envelope_json)
    validated = step14a.validate_step14a_checkpoint_envelope(
        envelope,
        env=env,
        expected_slate_date=expected_slate_date,
    )
    expected_key = step14a.checkpoint_key_for_slate(expected_slate_date)
    checks = {
        "checkpoint_key": str(history_key) == expected_key == validated["checkpoint_key"],
        "slate_date": str(history_slate) == validated["slate_date"],
        "source_hash": str(history_source_hash).lower()
        == validated["source_reliability_content_sha256"],
        "controller_hash": str(history_state_hash).lower()
        == validated["controller_state_sha256"],
        "envelope_hash": history_digest == validated["envelope_content_sha256"],
        "deterministic_checkpoint_id": head_uuid == checkpoint_id_for_envelope(validated),
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise WNBAStep14DatabaseAdapterIntegrityError(
            "Step 14B persisted row/envelope mismatch: " + ", ".join(failed)
        )
    return {
        "checkpoint_version": head_version,
        "checkpoint_id": head_uuid,
        "envelope_content_sha256": history_digest,
        "controller_state_sha256": validated["controller_state_sha256"],
        "checkpoint_envelope": validated,
        "controller_state_for_restart": deepcopy(validated["controller_state"]),
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
    controller_state_sha256: str | None,
    checkpoint_envelope: Mapping[str, Any] | None,
    controller_state_for_restart: Mapping[str, Any] | None,
    generated_at_utc: str | None,
) -> dict[str, Any]:
    generated = (
        _parse_timestamp(generated_at_utc, "generated_at_utc")
        if generated_at_utc is not None
        else datetime.now(timezone.utc)
    )
    result = {
        "data_type": "wnba_step14b_database_checkpoint_result",
        "schema_version": SCHEMA_VERSION,
        "adapter_version": ADAPTER_VERSION,
        "operation": operation,
        "status": status,
        "found": found,
        "slate_date": slate_date,
        "checkpoint_key": checkpoint_key,
        "checkpoint_version": checkpoint_version,
        "checkpoint_id": checkpoint_id,
        "envelope_content_sha256": envelope_content_sha256,
        "controller_state_sha256": controller_state_sha256,
        "checkpoint_envelope": deepcopy(dict(checkpoint_envelope))
        if checkpoint_envelope is not None
        else None,
        "controller_state_for_restart": deepcopy(dict(controller_state_for_restart))
        if controller_state_for_restart is not None
        else None,
        "lineage": {
            "step14a_frozen_sha": STEP14A_FROZEN_SHA,
            "step14a_contract_id": STEP14A_CONTRACT_ID,
            "step14a_manifest_content_sha256": STEP14A_MANIFEST_CONTENT_SHA256,
            "step14a_sql_schema_sha256": STEP14A_SQL_SCHEMA_SHA256,
            "step13d_frozen_sha": STEP13D_FROZEN_SHA,
            "step13_release_id": STEP13_RELEASE_ID,
            "step13_release_content_sha256": STEP13_RELEASE_CONTENT_SHA256,
        },
        "guardrails": {
            "isolated_database_adapter": True,
            "postgresql_database_read_allowed": True,
            "postgresql_database_write_allowed": True,
            "append_only_checkpoint_history": True,
            "head_compare_and_swap": True,
            "persistence_runtime_enabled": False,
            "durable_restart_recovery": False,
            "durable_distributed_lease": False,
            "cross_process_duplicate_run_guard": False,
            "supabase_rest_write": False,
            "production_activation": False,
            "public_fastapi_activation": False,
            "wager_action": False,
            "authentication": False,
            "cookies": False,
            "background_daemon": False,
            "background_thread": False,
            "basketball_model_mutation": False,
            "ranking_mutation": False,
        },
        "generated_at_utc": generated.isoformat(),
    }
    result["adapter_content_sha256"] = _canonical_hash(_result_hash_surface(result))
    return result


def validate_step14b_adapter_result(result: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a Step-14B adapter result before later recovery code may consume it."""
    if not isinstance(result, Mapping):
        raise WNBAStep14DatabaseAdapterInputError("Step 14B result must be an object.")
    keys = set(result)
    missing = sorted(_RESULT_REQUIRED_FIELDS - keys)
    unknown = sorted(keys - _RESULT_REQUIRED_FIELDS)
    if missing:
        raise WNBAStep14DatabaseAdapterInputError(
            "Missing Step-14B result fields: " + ", ".join(missing)
        )
    if unknown:
        raise WNBAStep14DatabaseAdapterInputError(
            "Unknown Step-14B result fields: " + ", ".join(unknown)
        )
    if result.get("data_type") != "wnba_step14b_database_checkpoint_result":
        raise WNBAStep14DatabaseAdapterIntegrityError("Step 14B result data_type drift.")
    if result.get("schema_version") != SCHEMA_VERSION:
        raise WNBAStep14DatabaseAdapterIntegrityError("Step 14B result schema drift.")
    if result.get("adapter_version") != ADAPTER_VERSION:
        raise WNBAStep14DatabaseAdapterIntegrityError("Step 14B adapter version drift.")
    lineage = result.get("lineage")
    if not isinstance(lineage, Mapping):
        raise WNBAStep14DatabaseAdapterIntegrityError("Step 14B result lineage missing.")
    if lineage.get("step14a_frozen_sha") != STEP14A_FROZEN_SHA:
        raise WNBAStep14DatabaseAdapterIntegrityError("Step 14B result parent lineage drift.")
    if lineage.get("step13_release_content_sha256") != STEP13_RELEASE_CONTENT_SHA256:
        raise WNBAStep14DatabaseAdapterIntegrityError("Step 14B result release hash drift.")
    _parse_timestamp(result.get("generated_at_utc"), "generated_at_utc")
    observed = str(result.get("adapter_content_sha256") or "").strip().lower()
    expected = _canonical_hash(_result_hash_surface(result))
    if not _valid_sha256(observed) or observed != expected:
        raise WNBAStep14DatabaseAdapterIntegrityError(
            "Step 14B adapter result content-hash mismatch."
        )
    if result.get("found") is True:
        envelope = result.get("checkpoint_envelope")
        if not isinstance(envelope, Mapping):
            raise WNBAStep14DatabaseAdapterIntegrityError(
                "Step 14B found result must carry its checkpoint envelope."
            )
        validated = step14a.validate_step14a_checkpoint_envelope(
            envelope,
            env=_result_validation_env(),
            expected_slate_date=result.get("slate_date"),
        )
        if result.get("checkpoint_key") != validated["checkpoint_key"]:
            raise WNBAStep14DatabaseAdapterIntegrityError(
                "Step 14B result checkpoint key/envelope mismatch."
            )
        if result.get("envelope_content_sha256") != validated["envelope_content_sha256"]:
            raise WNBAStep14DatabaseAdapterIntegrityError(
                "Step 14B result envelope hash mismatch."
            )
        if result.get("controller_state_sha256") != validated["controller_state_sha256"]:
            raise WNBAStep14DatabaseAdapterIntegrityError(
                "Step 14B result controller hash mismatch."
            )
        if result.get("controller_state_for_restart") != validated["controller_state"]:
            raise WNBAStep14DatabaseAdapterIntegrityError(
                "Step 14B result restart-state mismatch."
            )
    return deepcopy(dict(result))


def _result_validation_env() -> dict[str, str]:
    """Internal frozen-parent env for pure result validation; never enables DB I/O."""
    return {
        "WNBA_STEP14A_PERSISTENCE_CONTRACT_ENABLED": "true",
        "WNBA_STEP13D_FINAL_SCHEDULER_FREEZE_ENABLED": "true",
        "WNBA_STEP13C_RELIABILITY_RECOVERY_ENABLED": "true",
        "WNBA_STEP13B_RUNTIME_SUPERVISOR_ENABLED": "true",
        "WNBA_STEP13A_BOUNDED_SCHEDULER_ENABLED": "true",
        "WNBA_STEP12D_FINAL_RUNTIME_FREEZE_ENABLED": "true",
        "WNBA_STEP12C_LIVE_BOARD_RUNTIME_ENABLED": "true",
        "WNBA_STEP12B_LIVE_RUNTIME_ASSEMBLY_ENABLED": "true",
        "WNBA_STEP12A_SHADOW_RUNNER_ENABLED": "true",
        "WNBA_STEP11E_CONTROLLED_AUTOMATION_ENABLED": "true",
        "WNBA_PRODUCTION_RUNTIME_ENABLED": "false",
        "WNBA_BOARD_SCHEDULER_ENABLED": "false",
        "WNBA_PERSISTENCE_ENABLED": "false",
        "WNBA_SUPABASE_WRITE_ENABLED": "false",
        "WNBA_WAGERING_ENABLED": "false",
        "WNBA_PUBLIC_STEP11E_FASTAPI_ENABLED": "false",
        "WNBA_STEP12_SCHEDULER_ENABLED": "false",
    }


def verify_step14b_database_schema(
    *,
    env: Mapping[str, str] | None = None,
    connection_factory: Callable[[], Any] | None = None,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    """Verify that the two frozen Step-14A tables exist; performs no mutation."""
    _assert_adapter_integrity(env)
    _require_read(env)
    connection = _open_connection(env, connection_factory)
    cursor = None
    try:
        cursor = connection.cursor()
        _verify_schema_with_cursor(cursor)
        _safe_rollback(connection)
    except (WNBAStep14DatabaseAdapterDisabledError, WNBAStep14DatabaseAdapterIntegrityError, WNBAStep14DatabaseSchemaError):
        _safe_rollback(connection)
        raise
    except Exception as exc:
        _safe_rollback(connection)
        raise WNBAStep14DatabaseError("Step 14B database schema verification failed.") from exc
    finally:
        _safe_close(cursor)
        _safe_close(connection)

    generated = (
        _parse_timestamp(generated_at_utc, "generated_at_utc")
        if generated_at_utc is not None
        else datetime.now(timezone.utc)
    )
    result = {
        "data_type": "wnba_step14b_database_schema_check",
        "schema_version": SCHEMA_VERSION,
        "adapter_version": ADAPTER_VERSION,
        "database_schema": DATABASE_SCHEMA_NAME,
        "checkpoint_table": CHECKPOINT_TABLE_NAME,
        "checkpoint_head_table": CHECKPOINT_HEAD_TABLE_NAME,
        "tables_present": True,
        "step14a_frozen_sha": STEP14A_FROZEN_SHA,
        "step14a_sql_schema_sha256": STEP14A_SQL_SCHEMA_SHA256,
        "generated_at_utc": generated.isoformat(),
    }
    hash_surface = {k: deepcopy(v) for k, v in result.items() if k != "generated_at_utc"}
    result["schema_check_content_sha256"] = _canonical_hash(hash_surface)
    return result


def load_step14b_checkpoint(
    *,
    slate_date: str | date,
    env: Mapping[str, str] | None = None,
    connection_factory: Callable[[], Any] | None = None,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    """Load and fully validate the current durable checkpoint head for one slate."""
    _assert_adapter_integrity(env)
    _require_read(env)
    checkpoint_key = step14a.checkpoint_key_for_slate(slate_date)
    slate_text = checkpoint_key.rsplit(":", 1)[-1]
    connection = _open_connection(env, connection_factory)
    cursor = None
    try:
        cursor = connection.cursor()
        _verify_schema_with_cursor(cursor)
        cursor.execute(_HEAD_SELECT_SQL, (checkpoint_key,))
        row = cursor.fetchone()
        normalized = _normalize_head_row(
            row,
            env=env,
            expected_slate_date=slate_text,
        )
        _safe_rollback(connection)
    except (
        WNBAStep14DatabaseAdapterDisabledError,
        WNBAStep14DatabaseAdapterInputError,
        WNBAStep14DatabaseAdapterIntegrityError,
        WNBAStep14DatabaseSchemaError,
    ):
        _safe_rollback(connection)
        raise
    except Exception as exc:
        _safe_rollback(connection)
        raise WNBAStep14DatabaseError("Step 14B checkpoint load failed.") from exc
    finally:
        _safe_close(cursor)
        _safe_close(connection)

    if normalized is None:
        return _build_result(
            operation="load",
            status="not_found",
            slate_date=slate_text,
            checkpoint_key=checkpoint_key,
            found=False,
            checkpoint_version=None,
            checkpoint_id=None,
            envelope_content_sha256=None,
            controller_state_sha256=None,
            checkpoint_envelope=None,
            controller_state_for_restart=None,
            generated_at_utc=generated_at_utc,
        )
    return _build_result(
        operation="load",
        status="loaded",
        slate_date=slate_text,
        checkpoint_key=checkpoint_key,
        found=True,
        checkpoint_version=normalized["checkpoint_version"],
        checkpoint_id=normalized["checkpoint_id"],
        envelope_content_sha256=normalized["envelope_content_sha256"],
        controller_state_sha256=normalized["controller_state_sha256"],
        checkpoint_envelope=normalized["checkpoint_envelope"],
        controller_state_for_restart=normalized["controller_state_for_restart"],
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
    """Persist one immutable envelope and atomically advance its slate head.

    expected_head_version=0 means the caller expects no current head. For an
    existing head, callers must provide the exact loaded version. If the desired
    envelope is already the current head, the operation is idempotent and does
    not append history or move the head.
    """
    _assert_adapter_integrity(env)
    _require_read(env)
    _require_write(env)
    expected_version = _normalize_expected_version(expected_head_version)
    validated = step14a.validate_step14a_checkpoint_envelope(
        checkpoint_envelope,
        env=env,
    )
    checkpoint_key = validated["checkpoint_key"]
    slate_text = validated["slate_date"]
    envelope_hash = validated["envelope_content_sha256"]
    checkpoint_id = checkpoint_id_for_envelope(validated)
    created_at = _parse_timestamp(validated["created_at_utc"], "checkpoint created_at_utc")
    write_time = (
        _parse_timestamp(generated_at_utc, "generated_at_utc")
        if generated_at_utc is not None
        else datetime.now(timezone.utc)
    )

    connection = _open_connection(env, connection_factory)
    cursor = None
    try:
        cursor = connection.cursor()
        _verify_schema_with_cursor(cursor)
        cursor.execute(_HEAD_SELECT_FOR_UPDATE_SQL, (checkpoint_key,))
        current = _normalize_head_row(
            cursor.fetchone(),
            env=env,
            expected_slate_date=slate_text,
        )
        current_version = 0 if current is None else current["checkpoint_version"]

        if current is not None and current["envelope_content_sha256"] == envelope_hash:
            connection.commit()
            return _build_result(
                operation="save",
                status="idempotent",
                slate_date=slate_text,
                checkpoint_key=checkpoint_key,
                found=True,
                checkpoint_version=current["checkpoint_version"],
                checkpoint_id=current["checkpoint_id"],
                envelope_content_sha256=current["envelope_content_sha256"],
                controller_state_sha256=current["controller_state_sha256"],
                checkpoint_envelope=current["checkpoint_envelope"],
                controller_state_for_restart=current["controller_state_for_restart"],
                generated_at_utc=generated_at_utc,
            )

        if current_version != expected_version:
            raise WNBAStep14DatabaseConflictError(
                f"Step 14B checkpoint head CAS conflict: expected version {expected_version}, current version {current_version}."
            )

        new_version = current_version + 1
        cursor.execute(
            _INSERT_HISTORY_SQL,
            (
                checkpoint_id,
                checkpoint_key,
                new_version,
                SEASON,
                SEASON_TYPE,
                date.fromisoformat(slate_text),
                STEP13D_FROZEN_SHA,
                STEP13_RELEASE_ID,
                STEP13_RELEASE_CONTENT_SHA256,
                STEP13C_FROZEN_SHA,
                validated["source_reliability_content_sha256"],
                validated["controller_state_sha256"],
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
            raise WNBAStep14DatabaseError(
                "Step 14B checkpoint history insert did not affect exactly one row."
            )

        if current is None:
            cursor.execute(
                _INSERT_HEAD_SQL,
                (checkpoint_key, new_version, checkpoint_id, envelope_hash, write_time),
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
            raise WNBAStep14DatabaseConflictError(
                "Step 14B checkpoint head compare-and-swap did not update exactly one row."
            )
        connection.commit()
    except (
        WNBAStep14DatabaseAdapterDisabledError,
        WNBAStep14DatabaseAdapterInputError,
        WNBAStep14DatabaseAdapterIntegrityError,
        WNBAStep14DatabaseSchemaError,
        WNBAStep14DatabaseConflictError,
        WNBAStep14DatabaseError,
    ):
        _safe_rollback(connection)
        raise
    except Exception as exc:
        _safe_rollback(connection)
        if _is_unique_violation(exc):
            raise WNBAStep14DatabaseConflictError(
                "Step 14B database uniqueness conflict; reload the head before retrying."
            ) from exc
        raise WNBAStep14DatabaseError("Step 14B checkpoint save failed.") from exc
    finally:
        _safe_close(cursor)
        _safe_close(connection)

    return _build_result(
        operation="save",
        status=status,
        slate_date=slate_text,
        checkpoint_key=checkpoint_key,
        found=True,
        checkpoint_version=new_version,
        checkpoint_id=checkpoint_id,
        envelope_content_sha256=envelope_hash,
        controller_state_sha256=validated["controller_state_sha256"],
        checkpoint_envelope=validated,
        controller_state_for_restart=validated["controller_state"],
        generated_at_utc=generated_at_utc,
    )


__all__ = [
    "ADAPTER_VERSION",
    "APPEND_ONLY_HISTORY_REQUIRED",
    "ATOMIC_HEAD_COMPARE_AND_SWAP_ALLOWED",
    "BRANCH",
    "CHECKPOINT_HEAD_TABLE_NAME",
    "CHECKPOINT_LOAD_ALLOWED",
    "CHECKPOINT_SAVE_ALLOWED",
    "CHECKPOINT_TABLE_NAME",
    "CROSS_PROCESS_DUPLICATE_RUN_GUARD_ALLOWED",
    "DATABASE_SCHEMA_NAME",
    "DATABASE_URL_ENV",
    "DEFAULT_ENABLED",
    "DURABLE_DISTRIBUTED_LEASE_ALLOWED",
    "DURABLE_RESTART_RECOVERY_ALLOWED",
    "PERSISTENCE_RUNTIME_ENABLED",
    "POSTGRESQL_DATABASE_READ_ALLOWED",
    "POSTGRESQL_DATABASE_WRITE_ALLOWED",
    "PRODUCTION_ACTIVATION_ALLOWED",
    "PUBLIC_FASTAPI_ACTIVATION_ALLOWED",
    "SCHEMA_VERSION",
    "SOURCE",
    "STEP13_RELEASE_CONTENT_SHA256",
    "STEP14A_FROZEN_SHA",
    "STEP14A_MANIFEST_CONTENT_SHA256",
    "STEP14A_SQL_SCHEMA_SHA256",
    "STEP14B_DATABASE_CHECKPOINT_ADAPTER_ENABLED_ENV",
    "STEP14B_DATABASE_READ_ENABLED_ENV",
    "STEP14B_DATABASE_WRITE_ENABLED_ENV",
    "SUPABASE_POSTGRES_COMPATIBLE",
    "SUPABASE_REST_WRITE_ALLOWED",
    "WNBAStep14DatabaseAdapterDisabledError",
    "WNBAStep14DatabaseAdapterInputError",
    "WNBAStep14DatabaseAdapterIntegrityError",
    "WNBAStep14DatabaseConflictError",
    "WNBAStep14DatabaseError",
    "WNBAStep14DatabaseSchemaError",
    "checkpoint_id_for_envelope",
    "load_step14b_checkpoint",
    "save_step14b_checkpoint",
    "step14b_database_checkpoint_adapter_enabled",
    "step14b_database_read_enabled",
    "step14b_database_write_enabled",
    "validate_step14b_adapter_result",
    "verify_step14b_database_schema",
]
