"""MLB Step 16C — one-shot packaged lifecycle PostgreSQL canary.

This is the first step allowed to open the packaged MLB lifecycle against the
real PostgreSQL database. It is explicit, foreground-only and one-shot. It
exercises only the frozen Step 14B/14C persistence read + lease path through the
Step 16B FastAPI lifespan binding. It never calls the scheduler, model runtime,
providers, sportsbooks, actionable output, wagering, or production activation.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from typing import Any
from uuid import uuid4

from sports_api import mlb_step14b_database_checkpoint_adapter_v1 as step14b
from sports_api import mlb_step14c_durable_restart_lease_v1 as step14c
from sports_api import mlb_step16b_packaging_lifecycle_contract_v1 as step16b_contract
from sports_api import mlb_step16b_production_lifecycle_v1 as lifecycle
from sports_api.mlb_step9_final_freeze_v1 import PROTECTED_INVARIANTS

DATA_TYPE = "mlb_step16c_live_postgresql_canary_v1"
SCHEMA_VERSION = 1
CANARY_VERSION = "mlb_step16c_packaged_lifecycle_postgresql_canary_2026_v1"
RUNTIME_MODE = "SHADOW_ONLY"
BRANCH = "mlb-step16c-live-postgresql-canary"
STEP16C_BASE_MAIN_SHA = "eb0ea430caea02f90b6367b8bc0ea28f698246bf"
STEP16B_FINAL_MARKER = "MLB_STEP16B_PRODUCTION_PACKAGING_LIFECYCLE_GREEN"
FINAL_CERTIFICATION_MARKER = "MLB_STEP16C_LIVE_POSTGRESQL_CANARY_GREEN"

STEP16C_LIVE_POSTGRESQL_CANARY_ENABLED_ENV = (
    "MLB_STEP16C_LIVE_POSTGRESQL_CANARY_ENABLED"
)
STEP16C_CANARY_SLATE_DATE_ENV = "MLB_STEP16C_CANARY_SLATE_DATE"
STEP16C_CANARY_OWNER_ID_ENV = "MLB_STEP16C_CANARY_OWNER_ID"
DEFAULT_CANARY_SLATE_DATE = "2026-01-15"
DEFAULT_LEASE_TTL_SECONDS = 120

DEFAULT_ENABLED = False
PRODUCTION_RUNTIME_ALLOWED = False
PRODUCTION_SCHEDULER_ALLOWED = False
SCHEDULER_CYCLE_ALLOWED = False
PROVIDER_CALLS_ALLOWED = False
SPORTSBOOK_CALLS_ALLOWED = False
ACTIONABLE_OUTPUT_ALLOWED = False
WAGERING_ALLOWED = False
PUBLIC_PERSISTENCE_API_ALLOWED = False
SUPABASE_REST_WRITE_ALLOWED = False
BACKGROUND_WORKER_ALLOWED = False
BACKGROUND_TASK_ALLOWED = False
CHECKPOINT_WRITE_ALLOWED = False
AUTOMATIC_RESTART_ALLOWED = False
PRODUCTION_ACTIVATION_ALLOWED = False

PACKAGED_FASTAPI_LIFECYCLE_CANARY_ALLOWED = True
DIRECT_PSYCOG_CONNECTION_ALLOWED = True
CHECKPOINT_READ_ALLOWED = True
TEMPORARY_DURABLE_LEASE_ALLOWED = True
LEASE_RENEW_ALLOWED = True
LEASE_RELEASE_REQUIRED = True
POST_CANARY_ZERO_LEASE_ROWS_REQUIRED = True

_FORBIDDEN_TRUE_ENV_KEYS = (
    "MLB_PRODUCTION_RUNTIME_ENABLED",
    "MLB_PRODUCTION_SCHEDULER_ENABLED",
    "MLB_ACTIONABLE_OUTPUT_ENABLED",
    "MLB_WAGERING_ENABLED",
    "MLB_SUPABASE_REST_WRITE_ENABLED",
)
_REQUIRED_TRUE_ENV_KEYS = (
    lifecycle.STEP16B_DURABLE_LIFECYCLE_ENABLED_ENV,
    step14c.STEP14C_DURABLE_RESTART_LEASE_ENABLED_ENV,
    step14b.STEP14B_DATABASE_CHECKPOINT_ADAPTER_ENABLED_ENV,
    step14b.STEP14B_DATABASE_READ_ENABLED_ENV,
    step14b.STEP14B_DATABASE_WRITE_ENABLED_ENV,
)

class MLBStep16CCanaryDisabledError(RuntimeError):
    """Raised unless the one-shot Step 16C canary is explicitly enabled."""

class MLBStep16CCanaryIntegrityError(RuntimeError):
    """Raised when lineage, safety boundaries, or cleanup drift."""

class MLBStep16CCanaryDatabaseError(RuntimeError):
    """Raised when the live packaged database canary fails."""

def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled",
    }

def _hash(value: Any) -> str:
    raw = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False, default=str,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()

def _evidence_hash_surface(evidence: Mapping[str, Any]) -> dict[str, Any]:
    result = deepcopy(dict(evidence))
    result.pop("observed_at_utc", None)
    result.pop("evidence_content_sha256", None)
    return result

def step16c_live_postgresql_canary_enabled(
    env: Mapping[str, str] | None = None,
) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(STEP16C_LIVE_POSTGRESQL_CANARY_ENABLED_ENV))

def validate_step16c_enablement(
    env: Mapping[str, str] | None = None,
) -> dict[str, str]:
    source = dict(os.environ if env is None else env)
    if not step16c_live_postgresql_canary_enabled(source):
        raise MLBStep16CCanaryDisabledError(
            f"Step 16C requires {STEP16C_LIVE_POSTGRESQL_CANARY_ENABLED_ENV}=true"
        )
    bad = [key for key in _FORBIDDEN_TRUE_ENV_KEYS if _truthy(source.get(key))]
    if bad:
        raise MLBStep16CCanaryDisabledError(
            "Step 16C refuses production/actionable switches: " + ", ".join(bad)
        )
    missing = [key for key in _REQUIRED_TRUE_ENV_KEYS if not _truthy(source.get(key))]
    if missing:
        raise MLBStep16CCanaryDisabledError(
            "Step 16C requires frozen persistence/lifecycle gates: " + ", ".join(missing)
        )
    if not str(source.get(lifecycle.DATABASE_URL_ENV) or "").strip():
        raise MLBStep16CCanaryDisabledError(
            f"Step 16C requires {lifecycle.DATABASE_URL_ENV} from the secret manager"
        )

    if step16b_contract.FINAL_CERTIFICATION_MARKER != STEP16B_FINAL_MARKER:
        raise MLBStep16CCanaryIntegrityError("Step 16B final marker drift")
    if step16b_contract.STEP16C_LIVE_CANARY_REQUIRED is not True:
        raise MLBStep16CCanaryIntegrityError("Step 16B no longer requires Step 16C")
    if step16b_contract.LIVE_CANARY_EXECUTED is not False:
        raise MLBStep16CCanaryIntegrityError("Step 16B frozen canary boundary drift")
    if lifecycle.PRODUCTION_ACTIVATION_ALLOWED is not False:
        raise MLBStep16CCanaryIntegrityError("Step 16B production activation drift")
    if any(value is not False for value in PROTECTED_INVARIANTS.values()):
        raise MLBStep16CCanaryIntegrityError("protected MLB invariant drift")

    lifecycle.validate_step16b_enablement(source)
    return source

def _direct_database_probe(
    *,
    env: Mapping[str, str],
    lease_key: str,
) -> dict[str, Any]:
    try:
        import psycopg
        connection = psycopg.connect(
            str(env[lifecycle.DATABASE_URL_ENV]),
            connect_timeout=10,
            application_name="kyre-sports-ai-mlb-step16c",
        )
    except Exception as exc:
        raise MLBStep16CCanaryDatabaseError(
            "Step 16C could not open the packaged psycopg PostgreSQL connection"
        ) from exc

    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute(
            """
            SELECT current_database(), version(),
                   to_regclass('kyre_runtime.mlb_runtime_checkpoints') IS NOT NULL,
                   to_regclass('kyre_runtime.mlb_runtime_checkpoint_heads') IS NOT NULL,
                   to_regclass('kyre_runtime.mlb_runtime_leases') IS NOT NULL
            """
        )
        row = cursor.fetchone()
        if not isinstance(row, (tuple, list)) or len(row) != 5:
            raise MLBStep16CCanaryDatabaseError("Step 16C database identity probe shape drift")
        cursor.execute(
            "SELECT count(*) FROM kyre_runtime.mlb_runtime_leases WHERE lease_key = %s",
            (lease_key,),
        )
        lease_row = cursor.fetchone()
        if not isinstance(lease_row, (tuple, list)) or len(lease_row) != 1:
            raise MLBStep16CCanaryDatabaseError("Step 16C lease cleanup probe shape drift")
        connection.rollback()
        return {
            "database_name": str(row[0]),
            "postgres_version": str(row[1]).split(",")[0],
            "checkpoint_table_present": row[2] is True,
            "checkpoint_head_table_present": row[3] is True,
            "lease_table_present": row[4] is True,
            "canary_lease_rows": int(lease_row[0]),
        }
    except MLBStep16CCanaryDatabaseError:
        try:
            connection.rollback()
        except Exception:
            pass
        raise
    except Exception as exc:
        try:
            connection.rollback()
        except Exception:
            pass
        raise MLBStep16CCanaryDatabaseError("Step 16C database probe failed") from exc
    finally:
        try:
            if cursor is not None:
                cursor.close()
        finally:
            connection.close()

def _build_evidence(
    *,
    slate_date: str,
    owner_id: str,
    restart_context: Mapping[str, Any],
    renewed_handle: Mapping[str, Any],
    released: bool,
    lifecycle_status: Mapping[str, Any],
    shutdown_status: Mapping[str, Any],
    probe: Mapping[str, Any],
    observed_at_utc: str,
) -> dict[str, Any]:
    lease = restart_context.get("lease") or {}
    guardrails = restart_context.get("guardrails") or {}
    evidence: dict[str, Any] = {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "canary_version": CANARY_VERSION,
        "runtime_mode": RUNTIME_MODE,
        "frozen_lineage": {
            "step16c_base_main_sha": STEP16C_BASE_MAIN_SHA,
            "step16b_final_marker": step16b_contract.FINAL_CERTIFICATION_MARKER,
            "step16b_contract_id": step16b_contract.CONTRACT_ID,
            "step15_release_id": lifecycle.STEP15_RELEASE_ID,
        },
        "canary_scope": {
            "slate_date": slate_date,
            "lease_key": step14c.lease_key_for_slate(slate_date),
            "owner_id_recorded": bool(owner_id),
            "checkpoint_write_allowed": False,
        },
        "packaged_lifecycle": {
            "fastapi_lifespan_bound": True,
            "step16b_enabled": lifecycle_status.get("enabled") is True,
            "step16b_status": lifecycle_status.get("status"),
            "runtime_binding_count": lifecycle_status.get("runtime_binding_count"),
            "shutdown_status": shutdown_status.get("status"),
        },
        "database_canary": {
            "direct_psycopg_connection": True,
            "database_name": probe.get("database_name"),
            "postgres_version": probe.get("postgres_version"),
            "checkpoint_table_present": probe.get("checkpoint_table_present"),
            "checkpoint_head_table_present": probe.get("checkpoint_head_table_present"),
            "lease_table_present": probe.get("lease_table_present"),
            "checkpoint_found": bool(restart_context.get("found")),
            "restart_status": restart_context.get("status"),
            "lease_acquired": bool(lease),
            "lease_generation": lease.get("fencing_generation"),
            "lease_renewed": (
                renewed_handle.get("fencing_generation") == lease.get("fencing_generation")
            ),
            "lease_released": released is True,
            "canary_lease_rows_after_cleanup": probe.get("canary_lease_rows"),
        },
        "safety_boundary": {
            "production_runtime_started": False,
            "production_scheduler_started": False,
            "scheduler_cycle_executed": False,
            "checkpoint_write_executed": False,
            "automatic_restart_executed": False,
            "background_worker_started": False,
            "background_task_started": False,
            "public_persistence_api_exposed": False,
            "supabase_rest_write_path_enabled": False,
            "provider_calls": int(guardrails.get("provider_network_calls", 0)),
            "sportsbook_calls": int(guardrails.get("sportsbook_network_calls", 0)),
            "actionable_output_enabled": False,
            "wagering_enabled": False,
            "production_activation": 0,
            "credential_value_exposed": False,
        },
        "observed_at_utc": observed_at_utc,
    }
    evidence["evidence_content_sha256"] = _hash(_evidence_hash_surface(evidence))
    return evidence

async def run_step16c_live_postgresql_canary(
    *,
    env: Mapping[str, str] | None = None,
    app: Any | None = None,
    owner_id: str | None = None,
) -> dict[str, Any]:
    source = validate_step16c_enablement(env)
    slate_date = str(
        source.get(STEP16C_CANARY_SLATE_DATE_ENV) or DEFAULT_CANARY_SLATE_DATE
    ).strip()
    owner = (
        owner_id
        or str(source.get(STEP16C_CANARY_OWNER_ID_ENV) or "").strip()
        or f"mlb-step16c-{uuid4()}"
    )

    if app is None:
        from sports_api.main import app as packaged_app
        app = packaged_app

    lifespan = getattr(getattr(app, "router", None), "lifespan_context", None)
    if lifespan is None:
        raise MLBStep16CCanaryIntegrityError("packaged FastAPI lifespan is not bound")

    restart_context: dict[str, Any] | None = None
    renewed: dict[str, Any] | None = None
    released = False
    lifecycle_status: dict[str, Any] = {}
    shutdown_status: dict[str, Any] = {}

    try:
        async with lifespan(app):
            lifecycle_status = deepcopy(dict(app.state.mlb_step16b_lifecycle))
            binding = app.state.mlb_step16b_runtime_binding
            if not isinstance(binding, dict) or len(binding) != 8:
                raise MLBStep16CCanaryIntegrityError("Step 16B runtime binding count drift")
            restart_context = binding["load_restart_context"](
                slate_date=slate_date,
                owner_id=owner,
                lease_ttl_seconds=DEFAULT_LEASE_TTL_SECONDS,
                env=source,
            )
            renewed = binding["renew_lease"](
                handle=restart_context["lease"],
                lease_ttl_seconds=DEFAULT_LEASE_TTL_SECONDS,
                env=source,
            )
            released = binding["release_lease"](
                handle=renewed,
                env=source,
            )
        shutdown_status = deepcopy(dict(app.state.mlb_step16b_lifecycle))
    except Exception:
        if restart_context is not None and not released:
            try:
                lifecycle._runtime_binding()["release_lease"](
                    handle=(renewed or restart_context["lease"]),
                    env=source,
                )
            except Exception:
                pass
        raise

    if restart_context is None or renewed is None or released is not True:
        raise MLBStep16CCanaryIntegrityError("Step 16C canary did not complete lease lifecycle")

    lease_key = step14c.lease_key_for_slate(slate_date)
    probe = _direct_database_probe(env=source, lease_key=lease_key)
    if probe["canary_lease_rows"] != 0:
        raise MLBStep16CCanaryIntegrityError("Step 16C canary lease cleanup failed")
    if not all(
        probe[key] is True
        for key in (
            "checkpoint_table_present",
            "checkpoint_head_table_present",
            "lease_table_present",
        )
    ):
        raise MLBStep16CCanaryIntegrityError("Step 16C required PostgreSQL schema is missing")

    observed = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    evidence = _build_evidence(
        slate_date=slate_date,
        owner_id=owner,
        restart_context=restart_context,
        renewed_handle=renewed,
        released=released,
        lifecycle_status=lifecycle_status,
        shutdown_status=shutdown_status,
        probe=probe,
        observed_at_utc=observed,
    )
    safety = evidence["safety_boundary"]
    if any(safety[key] != 0 for key in ("provider_calls", "sportsbook_calls", "production_activation")):
        raise MLBStep16CCanaryIntegrityError("Step 16C forbidden execution occurred")
    return evidence

def run_step16c_live_postgresql_canary_sync(
    *,
    env: Mapping[str, str] | None = None,
    app: Any | None = None,
    owner_id: str | None = None,
) -> dict[str, Any]:
    import asyncio
    return asyncio.run(
        run_step16c_live_postgresql_canary(env=env, app=app, owner_id=owner_id)
    )

__all__ = [
    "DATA_TYPE", "SCHEMA_VERSION", "CANARY_VERSION", "RUNTIME_MODE", "BRANCH",
    "STEP16C_BASE_MAIN_SHA", "FINAL_CERTIFICATION_MARKER",
    "STEP16C_LIVE_POSTGRESQL_CANARY_ENABLED_ENV", "DEFAULT_CANARY_SLATE_DATE",
    "DEFAULT_ENABLED", "MLBStep16CCanaryDisabledError",
    "MLBStep16CCanaryIntegrityError", "MLBStep16CCanaryDatabaseError",
    "step16c_live_postgresql_canary_enabled", "validate_step16c_enablement",
    "run_step16c_live_postgresql_canary", "run_step16c_live_postgresql_canary_sync",
]
