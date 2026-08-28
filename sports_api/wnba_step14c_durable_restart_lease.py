"""WNBA Step 14C: durable restart recovery plus PostgreSQL cross-process lease.

Step 14C is additive to frozen Steps 8-14B. It explicitly wires the verified
Step-14B checkpoint handoff back into the frozen Step-13B ``initial_previous_state``
contract and protects a slate with a PostgreSQL lease carrying a UUID token and
monotonic fencing generation. The orchestration remains explicit, foreground-only,
default-OFF, non-production, and does not spawn a renewal thread or daemon.
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
from uuid import UUID, uuid4

from sports_api import wnba_step13b_runtime_supervisor as step13b
from sports_api import wnba_step13c_reliability_recovery as step13c
from sports_api import wnba_step14a_persistence_contract as step14a
from sports_api import wnba_step14b_database_checkpoint_adapter as step14b

SOURCE = "Kyre Sports API WNBA Step 14C durable restart recovery and cross-process lease"
SCHEMA_VERSION = "wnba_step_14c_durable_restart_lease_v1"
RUNTIME_VERSION = "wnba_step14c_foreground_durable_restart_lease_2026_regular_v1"
BRANCH = "wnba-step14c-durable-restart-lease-20260828"
SEASON = 2026
SEASON_TYPE = "Regular Season"

STEP14B_FROZEN_SHA = "dfea123c0702331ecccf3ca285baf1d69b8f3c2e"
STEP14A_FROZEN_SHA = step14b.STEP14A_FROZEN_SHA
STEP13D_FROZEN_SHA = step14b.STEP13D_FROZEN_SHA
STEP13C_FROZEN_SHA = step14b.STEP13C_FROZEN_SHA
STEP13B_FROZEN_SHA = step14a.STEP13B_FROZEN_SHA
STEP13_RELEASE_ID = step14b.STEP13_RELEASE_ID
STEP13_RELEASE_CONTENT_SHA256 = step14b.STEP13_RELEASE_CONTENT_SHA256
STEP14A_SQL_SCHEMA_SHA256 = step14b.STEP14A_SQL_SCHEMA_SHA256

DATABASE_SCHEMA_NAME = step14b.DATABASE_SCHEMA_NAME
LEASE_TABLE_NAME = "wnba_runtime_leases"
LEASE_SQL_SCHEMA_PATH = "sports_api/sql/wnba_step14c_runtime_lease_schema.sql"
LEASE_SQL_SCHEMA_SHA256 = "49376bd4de581606819dc70ace6d462aadb77e641b0344bcde61c69f5a03b5bb"
DATABASE_URL_ENV = step14b.DATABASE_URL_ENV

STEP14C_DURABLE_RESTART_LEASE_ENABLED_ENV = "WNBA_STEP14C_DURABLE_RESTART_LEASE_ENABLED"

DEFAULT_ENABLED = False
FOREGROUND_DURABLE_RESTART_ORCHESTRATION_ALLOWED = True
DURABLE_RESTART_RECOVERY_ALLOWED = True
DURABLE_DISTRIBUTED_LEASE_ALLOWED = True
CROSS_PROCESS_DUPLICATE_RUN_GUARD_ALLOWED = True
CHECKPOINT_PERSIST_AFTER_SUCCESS_ALLOWED = True
FENCING_GENERATION_REQUIRED = True
LEASE_EXPIRY_REQUIRED = True
PERSISTENCE_RUNTIME_ENABLED = False
AUTOMATIC_PRODUCTION_RESTART_ACTIVATION_ALLOWED = False
SUPABASE_REST_WRITE_ALLOWED = False
PRODUCTION_ACTIVATION_ALLOWED = False
PUBLIC_FASTAPI_ACTIVATION_ALLOWED = False
WAGERING_ALLOWED = False
AUTHENTICATION_ALLOWED = False
COOKIES_ALLOWED = False
BACKGROUND_DAEMON_ALLOWED = False
BACKGROUND_THREAD_ALLOWED = False
BASKETBALL_MODEL_MUTATION_ALLOWED = False
RANKING_MUTATION_ALLOWED = False

MIN_LEASE_TTL_SECONDS = 60
MAX_LEASE_TTL_SECONDS = 604_800
LEASE_SAFETY_MARGIN_SECONDS = 60

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

_SCHEMA_EXISTENCE_SQL = "SELECT to_regclass(%s) IS NOT NULL"
_ACQUIRE_LEASE_SQL = f"""
INSERT INTO {DATABASE_SCHEMA_NAME}.{LEASE_TABLE_NAME} AS l (
    lease_key, owner_id, lease_token, fencing_generation,
    acquired_at, renewed_at, expires_at, updated_at
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


class WNBAStep14CDurableRuntimeDisabledError(RuntimeError):
    pass


class WNBAStep14CDurableRuntimeInputError(ValueError):
    pass


class WNBAStep14CDurableRuntimeIntegrityError(RuntimeError):
    pass


class WNBAStep14CLeaseSchemaError(RuntimeError):
    pass


class WNBAStep14CLeaseUnavailableError(RuntimeError):
    pass


class WNBAStep14CLeaseLostError(RuntimeError):
    pass


class WNBAStep14CDatabaseError(RuntimeError):
    pass


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() not in {"", "0", "false", "no", "off", "disabled"}


def step14c_durable_restart_lease_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(STEP14C_DURABLE_RESTART_LEASE_ENABLED_ENV))


def _canonical_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                     allow_nan=False, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _valid_sha256(value: Any) -> bool:
    text = str(value or "").strip().lower()
    return len(text) == 64 and all(ch in "0123456789abcdef" for ch in text)


def _strict_positive_int(value: Any, label: str, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise WNBAStep14CDurableRuntimeInputError(f"Step 14C {label} must be an integer.")
    if not minimum <= value <= maximum:
        raise WNBAStep14CDurableRuntimeInputError(
            f"Step 14C {label} must be from {minimum} through {maximum}."
        )
    return value


def _strict_owner_id(value: Any) -> str:
    text = str(value or "").strip()
    if not 1 <= len(text) <= 255:
        raise WNBAStep14CDurableRuntimeInputError("Step 14C owner_id must contain 1 through 255 characters.")
    return text


def _parse_timestamp(value: Any, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value or "").strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise WNBAStep14CDurableRuntimeIntegrityError(f"Step 14C {label} must be ISO-8601.") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise WNBAStep14CDurableRuntimeIntegrityError(f"Step 14C {label} must be timezone-aware.")
    return parsed.astimezone(timezone.utc)


def _assert_integrity(env: Mapping[str, str] | None = None) -> None:
    source = os.environ if env is None else env
    if not step14c_durable_restart_lease_enabled(source):
        raise WNBAStep14CDurableRuntimeDisabledError(
            f"Step 14C requires {STEP14C_DURABLE_RESTART_LEASE_ENABLED_ENV}=true."
        )
    bad = [key for key in _FORBIDDEN_TRUE_ENV_KEYS if _truthy(source.get(key))]
    if bad:
        raise WNBAStep14CDurableRuntimeDisabledError(
            "Step 14C refuses production/global-persistence/wagering switches: " + ", ".join(bad)
        )
    missing = [key for key in _REQUIRED_TRUE_ENV_KEYS if not _truthy(source.get(key))]
    if missing:
        raise WNBAStep14CDurableRuntimeDisabledError(
            "Step 14C requires the frozen Step-14B/14A/13/12 runtime gates: " + ", ".join(missing)
        )
    if step14b.DURABLE_RESTART_RECOVERY_ALLOWED is not False:
        raise WNBAStep14CDurableRuntimeIntegrityError("Step 14C detected Step-14B restart boundary drift.")
    if step14b.DURABLE_DISTRIBUTED_LEASE_ALLOWED is not False:
        raise WNBAStep14CDurableRuntimeIntegrityError("Step 14C detected Step-14B lease boundary drift.")
    if step14b.CROSS_PROCESS_DUPLICATE_RUN_GUARD_ALLOWED is not False:
        raise WNBAStep14CDurableRuntimeIntegrityError("Step 14C detected Step-14B duplicate-run boundary drift.")
    if step14a.DURABLE_DISTRIBUTED_LEASE_ALLOWED is not False:
        raise WNBAStep14CDurableRuntimeIntegrityError("Step 14C detected Step-14A lease boundary drift.")
    try:
        if hashlib.sha256(Path(step14a.SQL_SCHEMA_PATH).read_bytes()).hexdigest() != STEP14A_SQL_SCHEMA_SHA256:
            raise WNBAStep14CDurableRuntimeIntegrityError("Step 14C frozen Step-14A SQL schema hash drift.")
        if hashlib.sha256(Path(LEASE_SQL_SCHEMA_PATH).read_bytes()).hexdigest() != LEASE_SQL_SCHEMA_SHA256:
            raise WNBAStep14CDurableRuntimeIntegrityError("Step 14C lease SQL schema hash drift.")
    except OSError as exc:
        raise WNBAStep14CDurableRuntimeIntegrityError("Step 14C could not read a required SQL schema file.") from exc
    true_values = (
        FOREGROUND_DURABLE_RESTART_ORCHESTRATION_ALLOWED,
        DURABLE_RESTART_RECOVERY_ALLOWED,
        DURABLE_DISTRIBUTED_LEASE_ALLOWED,
        CROSS_PROCESS_DUPLICATE_RUN_GUARD_ALLOWED,
        CHECKPOINT_PERSIST_AFTER_SUCCESS_ALLOWED,
        FENCING_GENERATION_REQUIRED,
        LEASE_EXPIRY_REQUIRED,
    )
    if any(value is not True for value in true_values):
        raise WNBAStep14CDurableRuntimeIntegrityError("Step 14C required capability drift.")
    false_values = (
        DEFAULT_ENABLED, PERSISTENCE_RUNTIME_ENABLED,
        AUTOMATIC_PRODUCTION_RESTART_ACTIVATION_ALLOWED, SUPABASE_REST_WRITE_ALLOWED,
        PRODUCTION_ACTIVATION_ALLOWED, PUBLIC_FASTAPI_ACTIVATION_ALLOWED,
        WAGERING_ALLOWED, AUTHENTICATION_ALLOWED, COOKIES_ALLOWED,
        BACKGROUND_DAEMON_ALLOWED, BACKGROUND_THREAD_ALLOWED,
        BASKETBALL_MODEL_MUTATION_ALLOWED, RANKING_MUTATION_ALLOWED,
    )
    if any(value is not False for value in false_values):
        raise WNBAStep14CDurableRuntimeIntegrityError("Step 14C forbidden capability drift.")


def _open_connection(env: Mapping[str, str] | None, connection_factory: Callable[[], Any] | None) -> Any:
    if connection_factory is not None:
        try:
            connection = connection_factory()
        except Exception as exc:
            raise WNBAStep14CDatabaseError("Step 14C injected database connection factory failed.") from exc
        if connection is None:
            raise WNBAStep14CDatabaseError("Step 14C database connection factory returned no connection.")
        return connection
    source = os.environ if env is None else env
    dsn = str(source.get(DATABASE_URL_ENV) or "").strip()
    if not dsn:
        raise WNBAStep14CDurableRuntimeDisabledError(
            f"Step 14C live PostgreSQL access requires {DATABASE_URL_ENV}; credentials are never embedded in code."
        )
    try:
        import psycopg  # type: ignore
        return psycopg.connect(dsn, connect_timeout=10, application_name="kyre-sports-ai-step14c")
    except ImportError as exc:
        raise WNBAStep14CDatabaseError("Step 14C live PostgreSQL access requires psycopg 3.") from exc
    except Exception as exc:
        raise WNBAStep14CDatabaseError("Step 14C could not open the PostgreSQL connection.") from exc


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
    cursor.execute(_SCHEMA_EXISTENCE_SQL, (f"{DATABASE_SCHEMA_NAME}.{LEASE_TABLE_NAME}",))
    row = cursor.fetchone()
    if not isinstance(row, (tuple, list)) or len(row) != 1:
        raise WNBAStep14CLeaseSchemaError("Step 14C lease schema probe returned an invalid shape.")
    if row[0] is not True:
        raise WNBAStep14CLeaseSchemaError("Step 14C requires its isolated durable lease table.")


def verify_step14c_lease_schema(*, env: Mapping[str, str] | None = None,
                                connection_factory: Callable[[], Any] | None = None) -> dict[str, Any]:
    _assert_integrity(env)
    connection = _open_connection(env, connection_factory)
    cursor = None
    try:
        cursor = connection.cursor()
        _verify_lease_schema_with_cursor(cursor)
        _safe_rollback(connection)
    except (WNBAStep14CDurableRuntimeDisabledError, WNBAStep14CDurableRuntimeIntegrityError,
            WNBAStep14CLeaseSchemaError):
        _safe_rollback(connection)
        raise
    except Exception as exc:
        _safe_rollback(connection)
        raise WNBAStep14CDatabaseError("Step 14C lease schema verification failed.") from exc
    finally:
        _safe_close(cursor)
        _safe_close(connection)
    return {
        "database_schema": DATABASE_SCHEMA_NAME,
        "lease_table": LEASE_TABLE_NAME,
        "lease_sql_schema_sha256": LEASE_SQL_SCHEMA_SHA256,
        "table_present": True,
    }


def lease_key_for_slate(slate_date: str | date) -> str:
    return step14a.checkpoint_key_for_slate(slate_date) + ":scheduler-lease"


def _normalize_lease_row(row: Any, *, expected_key: str, expected_owner: str | None = None,
                         expected_token: str | None = None,
                         expected_generation: int | None = None) -> dict[str, Any]:
    if not isinstance(row, (tuple, list)) or len(row) != 7:
        raise WNBAStep14CDurableRuntimeIntegrityError("Step 14C lease query returned an invalid row shape.")
    key, owner, token, generation, acquired_at, renewed_at, expires_at = row
    key = str(key or "")
    owner = str(owner or "")
    try:
        token = str(UUID(str(token)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise WNBAStep14CDurableRuntimeIntegrityError("Step 14C lease token is not a valid UUID.") from exc
    if isinstance(generation, bool) or not isinstance(generation, int) or generation < 1:
        raise WNBAStep14CDurableRuntimeIntegrityError("Step 14C fencing generation is invalid.")
    acquired = _parse_timestamp(acquired_at, "lease acquired_at")
    renewed = _parse_timestamp(renewed_at, "lease renewed_at")
    expires = _parse_timestamp(expires_at, "lease expires_at")
    if not (acquired <= renewed < expires):
        raise WNBAStep14CDurableRuntimeIntegrityError("Step 14C lease timestamps are inconsistent.")
    checks = [key == expected_key]
    if expected_owner is not None:
        checks.append(owner == expected_owner)
    if expected_token is not None:
        checks.append(token == str(UUID(str(expected_token))))
    if expected_generation is not None:
        checks.append(generation == expected_generation)
    if not all(checks):
        raise WNBAStep14CDurableRuntimeIntegrityError("Step 14C lease ownership/fencing row mismatch.")
    return {
        "lease_key": key,
        "owner_id": owner,
        "lease_token": token,
        "fencing_generation": generation,
        "acquired_at_utc": acquired.isoformat(),
        "renewed_at_utc": renewed.isoformat(),
        "expires_at_utc": expires.isoformat(),
    }


def acquire_step14c_lease(*, slate_date: str | date, owner_id: str, lease_ttl_seconds: int,
                          env: Mapping[str, str] | None = None,
                          connection_factory: Callable[[], Any] | None = None,
                          token_factory: Callable[[], Any] | None = None) -> dict[str, Any]:
    _assert_integrity(env)
    owner = _strict_owner_id(owner_id)
    ttl = _strict_positive_int(lease_ttl_seconds, "lease_ttl_seconds", MIN_LEASE_TTL_SECONDS, MAX_LEASE_TTL_SECONDS)
    lease_key = lease_key_for_slate(slate_date)
    raw_token = (token_factory or uuid4)()
    try:
        token = str(UUID(str(raw_token)))
    except (ValueError, TypeError, AttributeError) as exc:
        raise WNBAStep14CDurableRuntimeInputError("Step 14C token_factory must return a UUID value.") from exc
    connection = _open_connection(env, connection_factory)
    cursor = None
    try:
        cursor = connection.cursor()
        _verify_lease_schema_with_cursor(cursor)
        cursor.execute(_ACQUIRE_LEASE_SQL, (lease_key, owner, token, ttl, ttl))
        row = cursor.fetchone()
        if row is None:
            _safe_rollback(connection)
            raise WNBAStep14CLeaseUnavailableError(
                "Step 14C refuses a duplicate cross-process slate run while an unexpired lease exists."
            )
        handle = _normalize_lease_row(row, expected_key=lease_key, expected_owner=owner, expected_token=token)
        connection.commit()
        return handle
    except (WNBAStep14CDurableRuntimeDisabledError, WNBAStep14CDurableRuntimeInputError,
            WNBAStep14CDurableRuntimeIntegrityError, WNBAStep14CLeaseSchemaError,
            WNBAStep14CLeaseUnavailableError):
        _safe_rollback(connection)
        raise
    except Exception as exc:
        _safe_rollback(connection)
        raise WNBAStep14CDatabaseError("Step 14C durable lease acquisition failed.") from exc
    finally:
        _safe_close(cursor)
        _safe_close(connection)


def _validated_handle(handle: Mapping[str, Any]) -> tuple[str, str, str, int]:
    if not isinstance(handle, Mapping):
        raise WNBAStep14CDurableRuntimeInputError("Step 14C lease handle must be an object.")
    key = str(handle.get("lease_key") or "").strip()
    owner = _strict_owner_id(handle.get("owner_id"))
    try:
        token = str(UUID(str(handle.get("lease_token"))))
    except (ValueError, TypeError, AttributeError) as exc:
        raise WNBAStep14CDurableRuntimeInputError("Step 14C lease handle token is invalid.") from exc
    generation = handle.get("fencing_generation")
    generation = _strict_positive_int(generation, "fencing_generation", 1, 9_223_372_036_854_775_807)
    if not key:
        raise WNBAStep14CDurableRuntimeInputError("Step 14C lease handle key is required.")
    return key, owner, token, generation


def renew_step14c_lease(*, handle: Mapping[str, Any], lease_ttl_seconds: int,
                        env: Mapping[str, str] | None = None,
                        connection_factory: Callable[[], Any] | None = None) -> dict[str, Any]:
    _assert_integrity(env)
    key, owner, token, generation = _validated_handle(handle)
    ttl = _strict_positive_int(lease_ttl_seconds, "lease_ttl_seconds", MIN_LEASE_TTL_SECONDS, MAX_LEASE_TTL_SECONDS)
    connection = _open_connection(env, connection_factory)
    cursor = None
    try:
        cursor = connection.cursor()
        _verify_lease_schema_with_cursor(cursor)
        cursor.execute(_RENEW_LEASE_SQL, (ttl, key, owner, token, generation))
        row = cursor.fetchone()
        if row is None:
            _safe_rollback(connection)
            raise WNBAStep14CLeaseLostError(
                "Step 14C lease ownership was lost or expired; stale process is fenced from persistence."
            )
        renewed = _normalize_lease_row(row, expected_key=key, expected_owner=owner,
                                      expected_token=token, expected_generation=generation)
        connection.commit()
        return renewed
    except (WNBAStep14CDurableRuntimeDisabledError, WNBAStep14CDurableRuntimeInputError,
            WNBAStep14CDurableRuntimeIntegrityError, WNBAStep14CLeaseSchemaError,
            WNBAStep14CLeaseLostError):
        _safe_rollback(connection)
        raise
    except Exception as exc:
        _safe_rollback(connection)
        raise WNBAStep14CDatabaseError("Step 14C durable lease renewal failed.") from exc
    finally:
        _safe_close(cursor)
        _safe_close(connection)


def release_step14c_lease(*, handle: Mapping[str, Any], env: Mapping[str, str] | None = None,
                          connection_factory: Callable[[], Any] | None = None) -> bool:
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
            raise WNBAStep14CLeaseLostError(
                "Step 14C stale lease owner cannot release a newer/expired lease."
            )
        connection.commit()
        return True
    except (WNBAStep14CDurableRuntimeDisabledError, WNBAStep14CDurableRuntimeInputError,
            WNBAStep14CDurableRuntimeIntegrityError, WNBAStep14CLeaseSchemaError,
            WNBAStep14CLeaseLostError):
        _safe_rollback(connection)
        raise
    except Exception as exc:
        _safe_rollback(connection)
        raise WNBAStep14CDatabaseError("Step 14C durable lease release failed.") from exc
    finally:
        _safe_close(cursor)
        _safe_close(connection)


def _verify_step13c_request(request: Mapping[str, Any]) -> None:
    if not isinstance(request, Mapping):
        raise WNBAStep14CDurableRuntimeInputError("Step 14C requires a Step-13C request object.")
    if request.get("data_type") != "wnba_step13c_reliability_recovery_request":
        raise WNBAStep14CDurableRuntimeInputError("Step 14C requires the frozen Step-13C request data type.")
    if request.get("schema_version") != step13c.REQUEST_SCHEMA_VERSION:
        raise WNBAStep14CDurableRuntimeIntegrityError("Step 14C Step-13C request schema drift.")
    parent = request.get("supervisor_request")
    if not isinstance(parent, Mapping) or parent.get("schema_version") != step13b.REQUEST_SCHEMA_VERSION:
        raise WNBAStep14CDurableRuntimeIntegrityError("Step 14C nested Step-13B request schema drift.")
    parent_observed = str(parent.get("request_content_sha256") or "").strip().lower()
    parent_expected = _canonical_hash({k: deepcopy(v) for k, v in parent.items() if k != "request_content_sha256"})
    if not _valid_sha256(parent_observed) or parent_observed != parent_expected:
        raise WNBAStep14CDurableRuntimeIntegrityError("Step 14C detected nested Step-13B request hash drift.")
    observed = str(request.get("request_content_sha256") or "").strip().lower()
    expected = _canonical_hash({k: deepcopy(v) for k, v in request.items() if k != "request_content_sha256"})
    if not _valid_sha256(observed) or observed != expected:
        raise WNBAStep14CDurableRuntimeIntegrityError("Step 14C detected Step-13C request hash drift.")


def build_recovered_step13c_request(*, step13c_request: Mapping[str, Any],
                                    durable_controller_state: Mapping[str, Any] | None) -> dict[str, Any]:
    _verify_step13c_request(step13c_request)
    parent = dict(step13c_request["supervisor_request"])
    state = durable_controller_state
    if state is not None:
        if not isinstance(state, Mapping):
            raise WNBAStep14CDurableRuntimeInputError("Step 14C durable controller state must be an object.")
        state = deepcopy(dict(state))
        if state.get("season") is not None and state.get("season") != parent.get("season"):
            raise WNBAStep14CDurableRuntimeIntegrityError("Step 14C durable state season does not match request.")
        if state.get("slate_date") is not None and state.get("slate_date") != parent.get("initial_slate_date"):
            raise WNBAStep14CDurableRuntimeIntegrityError("Step 14C durable state slate does not match request.")
    else:
        original = parent.get("initial_previous_state")
        state = None if original is None else deepcopy(dict(original))
    rebuilt_parent = step13b.build_step13b_request(
        season=parent["season"],
        initial_slate_date=parent["initial_slate_date"],
        slate_timezone=parent["slate_timezone"],
        rollover_policy=parent["rollover_policy"],
        max_supervisor_sessions=parent["max_supervisor_sessions"],
        max_supervisor_runtime_seconds=parent["max_supervisor_runtime_seconds"],
        max_total_intersession_sleep_seconds=parent["max_total_intersession_sleep_seconds"],
        scheduler_cycles_per_session=parent["scheduler_cycles_per_session"],
        scheduler_sleep_budget_seconds_per_session=parent["scheduler_sleep_budget_seconds_per_session"],
        initial_previous_state=state,
        controller_policy=parent.get("controller_policy") or {},
        refresh_policy=parent.get("refresh_policy") or {},
        qualification_policy=parent.get("qualification_policy") or {},
    )
    rebuilt = step13c.build_step13c_request(
        supervisor_request=rebuilt_parent,
        max_recovery_attempts=step13c_request["max_recovery_attempts"],
        base_recovery_backoff_seconds=step13c_request["base_recovery_backoff_seconds"],
        max_total_recovery_sleep_seconds=step13c_request["max_total_recovery_sleep_seconds"],
    )
    _verify_step13c_request(rebuilt)
    return rebuilt


def required_lease_ttl_seconds(step13c_request: Mapping[str, Any]) -> int:
    _verify_step13c_request(step13c_request)
    parent = step13c_request["supervisor_request"]
    bound = (
        int(parent["max_supervisor_runtime_seconds"]) * int(step13c_request["max_recovery_attempts"])
        + int(step13c_request["max_total_recovery_sleep_seconds"])
        + LEASE_SAFETY_MARGIN_SECONDS
    )
    return _strict_positive_int(max(MIN_LEASE_TTL_SECONDS, bound), "required lease TTL",
                                MIN_LEASE_TTL_SECONDS, MAX_LEASE_TTL_SECONDS)


def load_step14c_restart_checkpoint(*, slate_date: str | date,
                                    env: Mapping[str, str] | None = None,
                                    checkpoint_connection_factory: Callable[[], Any] | None = None) -> dict[str, Any]:
    _assert_integrity(env)
    loaded = step14b.load_step14b_checkpoint(
        slate_date=slate_date, env=env, connection_factory=checkpoint_connection_factory
    )
    return step14b.validate_step14b_adapter_result(loaded)


def _result_hash_surface(result: Mapping[str, Any]) -> dict[str, Any]:
    return {k: deepcopy(v) for k, v in result.items()
            if k not in {"generated_at_utc", "runtime_content_sha256"}}


def validate_step14c_runtime_result(result: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(result, Mapping):
        raise WNBAStep14CDurableRuntimeInputError("Step 14C result must be an object.")
    if result.get("data_type") != "wnba_step14c_durable_restart_lease_result":
        raise WNBAStep14CDurableRuntimeIntegrityError("Step 14C result data type drift.")
    if result.get("schema_version") != SCHEMA_VERSION or result.get("runtime_version") != RUNTIME_VERSION:
        raise WNBAStep14CDurableRuntimeIntegrityError("Step 14C result schema/runtime drift.")
    observed = str(result.get("runtime_content_sha256") or "").strip().lower()
    if not _valid_sha256(observed) or observed != _canonical_hash(_result_hash_surface(result)):
        raise WNBAStep14CDurableRuntimeIntegrityError("Step 14C runtime result content hash mismatch.")
    guards = result.get("guardrails")
    if not isinstance(guards, Mapping):
        raise WNBAStep14CDurableRuntimeIntegrityError("Step 14C result guardrails missing.")
    for key in ("background_daemon_started", "background_thread_spawned", "supabase_rest_write",
                "production_activation", "public_fastapi_activation", "wager_action",
                "basketball_model_mutation", "ranking_mutation"):
        if guards.get(key) is not False:
            raise WNBAStep14CDurableRuntimeIntegrityError(f"Step 14C forbidden result guard drift: {key}.")
    for key in ("durable_restart_recovery", "durable_distributed_lease",
                "cross_process_duplicate_run_guard", "fencing_generation_enforced",
                "checkpoint_cas_enforced"):
        if guards.get(key) is not True:
            raise WNBAStep14CDurableRuntimeIntegrityError(f"Step 14C required result guard drift: {key}.")
    return deepcopy(dict(result))


def run_step14c_durable_restart_lease(
    step13c_request: Mapping[str, Any],
    *,
    owner_id: str,
    env: Mapping[str, str] | None = None,
    lease_ttl_seconds: int | None = None,
    lease_connection_factory: Callable[[], Any] | None = None,
    checkpoint_connection_factory: Callable[[], Any] | None = None,
    token_factory: Callable[[], Any] | None = None,
    step13c_runner: Callable[..., Mapping[str, Any]] | None = None,
    runner_kwargs: Mapping[str, Any] | None = None,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    """Execute one explicit foreground durable cycle under a fenced database lease."""
    _assert_integrity(env)
    _verify_step13c_request(step13c_request)
    parent = step13c_request["supervisor_request"]
    slate_date = str(parent["initial_slate_date"])
    ttl = required_lease_ttl_seconds(step13c_request) if lease_ttl_seconds is None else _strict_positive_int(
        lease_ttl_seconds, "lease_ttl_seconds", MIN_LEASE_TTL_SECONDS, MAX_LEASE_TTL_SECONDS
    )
    required_ttl = required_lease_ttl_seconds(step13c_request)
    if ttl < required_ttl:
        raise WNBAStep14CDurableRuntimeInputError(
            f"Step 14C lease_ttl_seconds must be at least the bounded execution window ({required_ttl})."
        )
    lease = acquire_step14c_lease(
        slate_date=slate_date, owner_id=owner_id, lease_ttl_seconds=ttl, env=env,
        connection_factory=lease_connection_factory, token_factory=token_factory,
    )
    result: dict[str, Any] | None = None
    try:
        loaded = load_step14c_restart_checkpoint(
            slate_date=slate_date, env=env, checkpoint_connection_factory=checkpoint_connection_factory
        )
        durable_state = loaded["controller_state_for_restart"] if loaded["found"] else None
        recovered_request = build_recovered_step13c_request(
            step13c_request=step13c_request, durable_controller_state=durable_state
        )
        runner = step13c_runner or step13c.run_step13c_reliability_recovery
        kwargs = dict(runner_kwargs or {})
        response = runner(deepcopy(recovered_request), env=env, **kwargs)
        if not isinstance(response, Mapping):
            raise WNBAStep14CDurableRuntimeIntegrityError("Step 14C runner returned a non-object response.")
        if response.get("data_type") != "wnba_step13c_reliability_recovery_response":
            raise WNBAStep14CDurableRuntimeIntegrityError("Step 14C runner returned the wrong frozen response type.")
        if response.get("status") != "completed":
            raise WNBAStep14CDurableRuntimeIntegrityError(
                "Step 14C refuses to persist a Step-13C run that did not complete successfully."
            )
        envelope = step14a.build_step14a_checkpoint_envelope(
            step13c_response=response, slate_date=slate_date, env=env,
            created_at_utc=generated_at_utc,
        )
        lease = renew_step14c_lease(
            handle=lease, lease_ttl_seconds=ttl, env=env,
            connection_factory=lease_connection_factory,
        )
        expected_version = int(loaded["checkpoint_version"] or 0)
        saved = step14b.save_step14b_checkpoint(
            checkpoint_envelope=envelope,
            expected_head_version=expected_version,
            env=env,
            connection_factory=checkpoint_connection_factory,
            generated_at_utc=generated_at_utc,
        )
        saved = step14b.validate_step14b_adapter_result(saved)
        generated = _parse_timestamp(generated_at_utc, "generated_at_utc") if generated_at_utc else datetime.now(timezone.utc)
        result = {
            "data_type": "wnba_step14c_durable_restart_lease_result",
            "schema_version": SCHEMA_VERSION,
            "runtime_version": RUNTIME_VERSION,
            "status": "completed",
            "slate_date": slate_date,
            "checkpoint_key": loaded["checkpoint_key"],
            "recovered_from_durable_checkpoint": bool(loaded["found"]),
            "loaded_checkpoint_version": loaded["checkpoint_version"],
            "saved_checkpoint_version": saved["checkpoint_version"],
            "saved_checkpoint_status": saved["status"],
            "saved_envelope_content_sha256": saved["envelope_content_sha256"],
            "controller_state_sha256": saved["controller_state_sha256"],
            "lease_key": lease["lease_key"],
            "lease_fencing_generation": lease["fencing_generation"],
            "lineage": {
                "step14b_frozen_sha": STEP14B_FROZEN_SHA,
                "step14a_frozen_sha": STEP14A_FROZEN_SHA,
                "step13d_frozen_sha": STEP13D_FROZEN_SHA,
                "step13c_frozen_sha": STEP13C_FROZEN_SHA,
                "step13b_frozen_sha": STEP13B_FROZEN_SHA,
                "step13_release_id": STEP13_RELEASE_ID,
                "step13_release_content_sha256": STEP13_RELEASE_CONTENT_SHA256,
            },
            "guardrails": {
                "explicit_foreground_orchestration": True,
                "durable_restart_recovery": True,
                "durable_distributed_lease": True,
                "cross_process_duplicate_run_guard": True,
                "fencing_generation_enforced": True,
                "lease_revalidated_before_checkpoint_save": True,
                "checkpoint_cas_enforced": True,
                "append_only_checkpoint_history": True,
                "background_daemon_started": False,
                "background_thread_spawned": False,
                "global_persistence_runtime_enabled": False,
                "automatic_production_restart_activation": False,
                "supabase_rest_write": False,
                "production_activation": False,
                "public_fastapi_activation": False,
                "wager_action": False,
                "authentication": False,
                "cookies": False,
                "basketball_model_mutation": False,
                "ranking_mutation": False,
            },
            "generated_at_utc": generated.isoformat(),
        }
        result["runtime_content_sha256"] = _canonical_hash(_result_hash_surface(result))
    except Exception:
        try:
            release_step14c_lease(handle=lease, env=env, connection_factory=lease_connection_factory)
        except Exception:
            pass
        raise
    release_step14c_lease(handle=lease, env=env, connection_factory=lease_connection_factory)
    if result is None:
        raise WNBAStep14CDurableRuntimeIntegrityError("Step 14C completed without a runtime result.")
    return validate_step14c_runtime_result(result)


__all__ = [
    "AUTOMATIC_PRODUCTION_RESTART_ACTIVATION_ALLOWED",
    "BACKGROUND_DAEMON_ALLOWED", "BACKGROUND_THREAD_ALLOWED", "BRANCH",
    "CHECKPOINT_PERSIST_AFTER_SUCCESS_ALLOWED", "CROSS_PROCESS_DUPLICATE_RUN_GUARD_ALLOWED",
    "DEFAULT_ENABLED", "DURABLE_DISTRIBUTED_LEASE_ALLOWED", "DURABLE_RESTART_RECOVERY_ALLOWED",
    "FENCING_GENERATION_REQUIRED", "LEASE_SQL_SCHEMA_PATH", "LEASE_SQL_SCHEMA_SHA256",
    "LEASE_TABLE_NAME", "MAX_LEASE_TTL_SECONDS", "MIN_LEASE_TTL_SECONDS",
    "PERSISTENCE_RUNTIME_ENABLED", "PRODUCTION_ACTIVATION_ALLOWED", "RUNTIME_VERSION",
    "SCHEMA_VERSION", "SOURCE", "STEP14B_FROZEN_SHA", "SUPABASE_REST_WRITE_ALLOWED",
    "WNBAStep14CDatabaseError", "WNBAStep14CDurableRuntimeDisabledError",
    "WNBAStep14CDurableRuntimeInputError", "WNBAStep14CDurableRuntimeIntegrityError",
    "WNBAStep14CLeaseLostError", "WNBAStep14CLeaseSchemaError", "WNBAStep14CLeaseUnavailableError",
    "acquire_step14c_lease", "build_recovered_step13c_request", "lease_key_for_slate",
    "load_step14c_restart_checkpoint", "release_step14c_lease", "renew_step14c_lease",
    "required_lease_ttl_seconds", "run_step14c_durable_restart_lease",
    "step14c_durable_restart_lease_enabled", "validate_step14c_runtime_result",
    "verify_step14c_lease_schema",
]
