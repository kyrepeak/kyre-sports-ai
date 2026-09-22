"""MLB Step 16B — production packaging and explicit FastAPI lifecycle binding.

Step 16B closes the deployment blockers certified by Step 16A without starting
production. The PostgreSQL driver is packaged into the container, the deployment
template declares a secret-manager-only KYRE_DATABASE_URL contract, and the
frozen Step 13 scheduler/recovery controls plus Step 14C durable persistence
surface are bound to FastAPI lifespan state.

The integration is default-OFF. Even when explicitly enabled, lifespan performs
no database connection, scheduler cycle, provider/sportsbook call, background
thread/task, or production activation. Step 16C must explicitly execute a
controlled canary before any production activation may be considered.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from copy import deepcopy
import importlib.util
import os
from typing import Any, AsyncIterator, Callable, Mapping
from urllib.parse import urlsplit

from sports_api import mlb_step13a_bounded_scheduler_v1 as step13a
from sports_api import mlb_step13b_runtime_supervisor_v1 as step13b
from sports_api import mlb_step13c_reliability_recovery_v1 as step13c
from sports_api import mlb_step14c_durable_restart_lease_v1 as step14c
from sports_api.mlb_step9_final_freeze_v1 import PROTECTED_INVARIANTS

DATA_TYPE = "mlb_step16b_production_lifecycle_v1"
SCHEMA_VERSION = 1
INTEGRATION_VERSION = "mlb_step16b_production_packaging_lifecycle_2026_v1"
RUNTIME_MODE = "SHADOW_ONLY"
BRANCH = "mlb-step16b-production-packaging-lifecycle"

STEP16A_CERTIFIED_MAIN_SHA = "c5ad6047224aaf014cec13f5efa6e5cd650da939"
STEP16A_SOURCE_BLOB_SHA = "a8ce0bfef0918fd471c383964ccbf0f99f13611f"
STEP16A_CONTRACT_ID = "mlb_step16a_production_activation_readiness_2026_regular_v1"
STEP16A_CONTRACT_CONTENT_SHA256 = "fc5d15c1d38367c76d4fb7dc1ed611dea001d2b48459af3afc297e432c686a1d"
STEP15C_CERTIFIED_MAIN_SHA = "a67d415e5e1d8614d632fd34cfa09d551792a71f"
STEP15_RELEASE_ID = "mlb_step15_live_supabase_persistence_2026_regular_season_frozen_v1"
STEP15_RELEASE_MANIFEST_SHA256 = "d5c184988de8db66af6ef2c4e158dd8016a3403f968d42296f41dfa69bf83ada"

STEP16B_DURABLE_LIFECYCLE_ENABLED_ENV = "MLB_STEP16B_DURABLE_LIFECYCLE_ENABLED"
DATABASE_URL_ENV = step14c.DATABASE_URL_ENV

DEFAULT_ENABLED = False
PRODUCTION_ACTIVATION_ALLOWED = False
PRODUCTION_CANARY_ALLOWED = False
AUTOMATIC_RUNTIME_EXECUTION_ALLOWED = False
DATABASE_CONNECTION_DURING_LIFESPAN_ALLOWED = False
BACKGROUND_WORKER_ALLOWED = False
BACKGROUND_THREAD_ALLOWED = False
BACKGROUND_TASK_ALLOWED = False
PUBLIC_PERSISTENCE_API_ALLOWED = False
SUPABASE_REST_WRITE_ALLOWED = False
ACTIONABLE_OUTPUT_ALLOWED = False
WAGERING_ALLOWED = False
PROVIDER_NETWORK_CALLS_ALLOWED = False
SPORTSBOOK_NETWORK_CALLS_ALLOWED = False
RUNTIME_MUTATION_ALLOWED = False
SECRETS_IN_REPOSITORY_ALLOWED = False

PERSISTENCE_DRIVER_PACKAGING_ALLOWED = True
SECRET_MANAGER_REFERENCE_ALLOWED = True
FASTAPI_LIFESPAN_BINDING_ALLOWED = True
FROZEN_STEP13_CONTROL_BINDING_ALLOWED = True
FROZEN_STEP14C_PERSISTENCE_BINDING_ALLOWED = True

_FORBIDDEN_TRUE_ENV_KEYS = (
    "MLB_PRODUCTION_RUNTIME_ENABLED",
    "MLB_PRODUCTION_SCHEDULER_ENABLED",
    "MLB_ACTIONABLE_OUTPUT_ENABLED",
    "MLB_WAGERING_ENABLED",
    "MLB_SUPABASE_REST_WRITE_ENABLED",
)

SAFETY_CONTRACT = {
    "default_enablement": False,
    "production_runtime": False,
    "production_scheduler": False,
    "production_canary": False,
    "production_activation": False,
    "automatic_runtime_execution": False,
    "database_connection_during_lifespan": False,
    "background_worker": False,
    "background_thread": False,
    "background_task": False,
    "public_persistence_api": False,
    "supabase_rest_write": False,
    "actionable_output": False,
    "wager_action": False,
    "provider_network_calls": False,
    "sportsbook_network_calls": False,
    "runtime_mutation": False,
    "secrets_in_repository": False,
    "mlb_model_change": False,
    "projection_change": False,
    "probability_change": False,
    "simulation_change": False,
    "ranking_change": False,
    "grading_change": False,
    "wnba_change": False,
}


class MLBStep16BLifecycleDisabledError(RuntimeError):
    """Raised when the explicit Step 16B lifecycle gate is not satisfied."""


class MLBStep16BLifecycleIntegrityError(RuntimeError):
    """Raised when packaging, secret, lineage, or lifecycle boundaries drift."""


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled"
    }


def step16b_durable_lifecycle_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(STEP16B_DURABLE_LIFECYCLE_ENABLED_ENV))


def persistence_driver_available() -> bool:
    return importlib.util.find_spec("psycopg") is not None


def _database_secret_status(env: Mapping[str, str]) -> dict[str, Any]:
    raw = str(env.get(DATABASE_URL_ENV) or "").strip()
    if not raw:
        return {"configured": False, "scheme": None, "credential_value_exposed": False}
    parsed = urlsplit(raw)
    scheme = parsed.scheme.casefold()
    if scheme not in {"postgres", "postgresql"}:
        raise MLBStep16BLifecycleIntegrityError(
            f"Step 16B requires {DATABASE_URL_ENV} to use postgres:// or postgresql://"
        )
    if not parsed.hostname or not parsed.path or parsed.path == "/":
        raise MLBStep16BLifecycleIntegrityError(
            f"Step 16B {DATABASE_URL_ENV} must identify a PostgreSQL host and database"
        )
    return {"configured": True, "scheme": scheme, "credential_value_exposed": False}


def _assert_frozen_parent_identity() -> None:
    exact = {
        "step13a_marker": step13a.FINAL_CERTIFICATION_MARKER == "MLB_STEP13A_BOUNDED_SCHEDULER_GREEN",
        "step13b_marker": step13b.FINAL_CERTIFICATION_MARKER == "MLB_STEP13B_RUNTIME_SUPERVISOR_GREEN",
        "step13c_marker": step13c.FINAL_CERTIFICATION_MARKER == "MLB_STEP13C_RELIABILITY_RECOVERY_GREEN",
        "step14c_marker": step14c.FINAL_CERTIFICATION_MARKER == "MLB_STEP14C_DURABLE_RESTART_LEASE_GREEN",
        "step13a_shadow": step13a.RUNTIME_MODE == RUNTIME_MODE,
        "step13b_shadow": step13b.RUNTIME_MODE == RUNTIME_MODE,
        "step13c_shadow": step13c.RUNTIME_MODE == RUNTIME_MODE,
        "step14c_shadow": step14c.RUNTIME_MODE == RUNTIME_MODE,
    }
    failed = [name for name, ok in exact.items() if not ok]
    if failed:
        raise MLBStep16BLifecycleIntegrityError(
            "Step 16B frozen parent identity drift: " + ", ".join(failed)
        )
    if any(value is not False for value in PROTECTED_INVARIANTS.values()):
        raise MLBStep16BLifecycleIntegrityError("Step 16B protected invariant drift")


def validate_step16b_enablement(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    source = dict(os.environ if env is None else env)
    if not step16b_durable_lifecycle_enabled(source):
        raise MLBStep16BLifecycleDisabledError(
            f"Step 16B requires {STEP16B_DURABLE_LIFECYCLE_ENABLED_ENV}=true"
        )
    bad = [key for key in _FORBIDDEN_TRUE_ENV_KEYS if _truthy(source.get(key))]
    if bad:
        raise MLBStep16BLifecycleDisabledError(
            "Step 16B refuses production/actionable switches: " + ", ".join(bad)
        )
    if not persistence_driver_available():
        raise MLBStep16BLifecycleIntegrityError(
            "Step 16B requires psycopg 3 to be packaged before lifecycle binding"
        )
    secret = _database_secret_status(source)
    if secret["configured"] is not True:
        raise MLBStep16BLifecycleDisabledError(
            f"Step 16B requires {DATABASE_URL_ENV} from the deployment secret manager"
        )
    false_constants = (
        DEFAULT_ENABLED, PRODUCTION_ACTIVATION_ALLOWED, PRODUCTION_CANARY_ALLOWED,
        AUTOMATIC_RUNTIME_EXECUTION_ALLOWED, DATABASE_CONNECTION_DURING_LIFESPAN_ALLOWED,
        BACKGROUND_WORKER_ALLOWED, BACKGROUND_THREAD_ALLOWED, BACKGROUND_TASK_ALLOWED,
        PUBLIC_PERSISTENCE_API_ALLOWED, SUPABASE_REST_WRITE_ALLOWED,
        ACTIONABLE_OUTPUT_ALLOWED, WAGERING_ALLOWED, PROVIDER_NETWORK_CALLS_ALLOWED,
        SPORTSBOOK_NETWORK_CALLS_ALLOWED, RUNTIME_MUTATION_ALLOWED,
        SECRETS_IN_REPOSITORY_ALLOWED,
    )
    if any(value is not False for value in false_constants):
        raise MLBStep16BLifecycleIntegrityError("Step 16B safety constant drift")
    true_constants = (
        PERSISTENCE_DRIVER_PACKAGING_ALLOWED, SECRET_MANAGER_REFERENCE_ALLOWED,
        FASTAPI_LIFESPAN_BINDING_ALLOWED, FROZEN_STEP13_CONTROL_BINDING_ALLOWED,
        FROZEN_STEP14C_PERSISTENCE_BINDING_ALLOWED,
    )
    if any(value is not True for value in true_constants):
        raise MLBStep16BLifecycleIntegrityError("Step 16B integration capability drift")
    _assert_frozen_parent_identity()
    return secret


def _runtime_binding() -> dict[str, Callable[..., Any]]:
    return {
        "scheduler_tick": step13a.build_bounded_scheduler_tick,
        "runtime_supervision": step13b.build_runtime_supervision,
        "recovery_decision": step13c.build_recovery_decision,
        "load_restart_context": step14c.load_step14c_restart_context,
        "restart_inputs": step14c.restart_inputs_from_context,
        "persist_checkpoint": step14c.persist_step14c_checkpoint_under_lease,
        "renew_lease": step14c.renew_step14c_lease,
        "release_lease": step14c.release_step14c_lease,
    }


def get_step16b_runtime_binding(
    env: Mapping[str, str] | None = None,
) -> dict[str, Callable[..., Any]] | None:
    source = dict(os.environ if env is None else env)
    if not step16b_durable_lifecycle_enabled(source):
        return None
    validate_step16b_enablement(source)
    return _runtime_binding()


def build_step16b_lifecycle_status(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    source = dict(os.environ if env is None else env)
    enabled = step16b_durable_lifecycle_enabled(source)
    if not enabled:
        return {
            "data_type": DATA_TYPE,
            "schema_version": SCHEMA_VERSION,
            "integration_version": INTEGRATION_VERSION,
            "enabled": False,
            "status": "disabled_default_off",
            "driver_available": persistence_driver_available(),
            "database_secret_configured": bool(str(source.get(DATABASE_URL_ENV) or "").strip()),
            "database_connected": False,
            "runtime_binding_count": 0,
            "runtime_executed": False,
            "background_task_started": False,
            "production_activation": False,
        }
    secret = validate_step16b_enablement(source)
    binding = _runtime_binding()
    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "integration_version": INTEGRATION_VERSION,
        "enabled": True,
        "status": "bound_not_executed",
        "driver_available": True,
        "database_secret_configured": True,
        "database_secret_scheme": secret["scheme"],
        "credential_value_exposed": False,
        "database_connected": False,
        "runtime_binding_count": len(binding),
        "runtime_executed": False,
        "background_task_started": False,
        "production_activation": False,
    }


def _set_app_state(app: Any, *, status: Mapping[str, Any], binding: Any) -> None:
    state = getattr(app, "state", None)
    if state is None:
        raise MLBStep16BLifecycleIntegrityError("Step 16B FastAPI app must expose app.state")
    setattr(state, "mlb_step16b_lifecycle", deepcopy(dict(status)))
    setattr(state, "mlb_step16b_runtime_binding", binding)


@asynccontextmanager
async def step16b_lifespan(app: Any) -> AsyncIterator[None]:
    """Bind frozen control/persistence callables without executing them."""
    env = dict(os.environ)
    status = build_step16b_lifecycle_status(env)
    binding = get_step16b_runtime_binding(env)
    _set_app_state(app, status=status, binding=binding)
    try:
        yield
    finally:
        shutdown = deepcopy(status)
        shutdown["status"] = (
            "shutdown_bound_never_executed" if status["enabled"] else "shutdown_disabled"
        )
        shutdown["database_connected"] = False
        shutdown["runtime_executed"] = False
        shutdown["background_task_started"] = False
        shutdown["production_activation"] = False
        _set_app_state(app, status=shutdown, binding=None)


__all__ = [
    "DATA_TYPE", "SCHEMA_VERSION", "INTEGRATION_VERSION", "RUNTIME_MODE", "BRANCH",
    "STEP16A_CERTIFIED_MAIN_SHA", "STEP16A_SOURCE_BLOB_SHA", "STEP16A_CONTRACT_ID",
    "STEP16A_CONTRACT_CONTENT_SHA256", "STEP15C_CERTIFIED_MAIN_SHA", "STEP15_RELEASE_ID",
    "STEP15_RELEASE_MANIFEST_SHA256", "STEP16B_DURABLE_LIFECYCLE_ENABLED_ENV",
    "DATABASE_URL_ENV", "DEFAULT_ENABLED", "SAFETY_CONTRACT",
    "MLBStep16BLifecycleDisabledError", "MLBStep16BLifecycleIntegrityError",
    "step16b_durable_lifecycle_enabled", "persistence_driver_available",
    "validate_step16b_enablement", "get_step16b_runtime_binding",
    "build_step16b_lifecycle_status", "step16b_lifespan",
]
