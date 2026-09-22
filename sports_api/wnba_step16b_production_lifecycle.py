"""WNBA Step 16B: production packaging plus explicit FastAPI lifecycle binding.

Step 16B closes the three deployment blockers certified by Step 16A without
starting the production scheduler. The PostgreSQL driver is packaged into the
container, KYRE_DATABASE_URL is defined as a deployment-secret-manager contract,
and the frozen Step-14C durable runtime is bound to FastAPI lifespan state.

The lifespan integration is default-OFF. Even when explicitly enabled, Step 16B
only validates the packaging/secret prerequisites and exposes the already frozen
Step-14C foreground runner on ``app.state``. It does not connect to PostgreSQL,
run a scheduler cycle, create a background task/thread, or mutate model/ranking
behavior. A later Step 16C canary must explicitly invoke the bound runner.
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from copy import deepcopy
import importlib.util
import os
from typing import Any, AsyncIterator, Callable, Mapping
from urllib.parse import urlsplit

from sports_api import wnba_step14c_durable_restart_lease as step14c

SOURCE = "Kyre Sports API WNBA Step 16B production packaging and explicit lifecycle integration"
SCHEMA_VERSION = "wnba_step_16b_production_packaging_lifecycle_v1"
INTEGRATION_VERSION = "wnba_step16b_production_packaging_lifecycle_v1"
BRANCH = "wnba-step16b-production-packaging-lifecycle-20260828"
SEASON = 2026
SEASON_TYPE = "Regular Season"

STEP16A_CERTIFIED_SHA = "4ea88aa9a54f5110a03e9e4374219ed15ab30def"
STEP16A_CONTRACT_ID = "wnba_step16a_production_activation_readiness_2026_regular_v1"
STEP16A_CONTRACT_CONTENT_SHA256 = "2d8c373dded7eb971d6d6bf6b4a5c9bdfc7bd19de5ddcf1ef83158a0b7d2000e"
STEP15C_CERTIFIED_SHA = "5e24210d7aef90143ba016e368cd49d3ee1a7f19"
STEP15_RELEASE_ID = "wnba_step15_live_supabase_persistence_2026_regular_season_frozen_v1"
STEP15_RELEASE_CONTENT_SHA256 = "537df3ec10999071941597e71f4e6361e246db98b17c13a3a31a944f9b8e9a2b"

STEP16B_DURABLE_LIFECYCLE_ENABLED_ENV = "WNBA_STEP16B_DURABLE_LIFECYCLE_ENABLED"
DATABASE_URL_ENV = step14c.DATABASE_URL_ENV

DEFAULT_ENABLED = False
PRODUCTION_ACTIVATION_ALLOWED = False
PRODUCTION_CANARY_ALLOWED = False
AUTOMATIC_RUNTIME_EXECUTION_ALLOWED = False
BACKGROUND_DAEMON_ALLOWED = False
BACKGROUND_THREAD_ALLOWED = False
BACKGROUND_TASK_ALLOWED = False
PUBLIC_PERSISTENCE_API_ALLOWED = False
SUPABASE_REST_WRITE_ALLOWED = False
WAGERING_ALLOWED = False
AUTHENTICATION_ALLOWED = False
COOKIES_ALLOWED = False
BASKETBALL_MODEL_MUTATION_ALLOWED = False
RANKING_MUTATION_ALLOWED = False
SECRETS_IN_REPOSITORY_ALLOWED = False
DATABASE_CONNECTION_DURING_LIFESPAN_ALLOWED = False

PERSISTENCE_DRIVER_PACKAGING_ALLOWED = True
SECRET_MANAGER_REFERENCE_ALLOWED = True
FASTAPI_LIFESPAN_BINDING_ALLOWED = True
FROZEN_FOREGROUND_RUNNER_BINDING_ALLOWED = True

_FORBIDDEN_TRUE_ENV_KEYS = (
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_PERSISTENCE_ENABLED",
    "WNBA_SUPABASE_WRITE_ENABLED",
    "WNBA_WAGERING_ENABLED",
    "WNBA_STEP12_SCHEDULER_ENABLED",
)

SAFETY_CONTRACT = {
    "default_enablement": False,
    "production_runtime": False,
    "production_canary": False,
    "production_activation": False,
    "automatic_runtime_execution": False,
    "database_connection_during_lifespan": False,
    "background_daemon": False,
    "background_thread": False,
    "background_task": False,
    "public_persistence_api": False,
    "supabase_rest_write": False,
    "wager_action": False,
    "authentication": False,
    "cookies": False,
    "secrets_in_repository": False,
    "basketball_model_change": False,
    "step8_distribution_change": False,
    "step9_ranking_change": False,
    "step9_qualification_change": False,
}


class WNBAStep16BLifecycleDisabledError(RuntimeError):
    """Raised when the explicit Step-16B lifecycle gate is not satisfied."""


class WNBAStep16BLifecycleIntegrityError(RuntimeError):
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
        return {
            "configured": False,
            "scheme": None,
            "credential_value_exposed": False,
        }
    parsed = urlsplit(raw)
    scheme = parsed.scheme.casefold()
    if scheme not in {"postgres", "postgresql"}:
        raise WNBAStep16BLifecycleIntegrityError(
            f"Step 16B requires {DATABASE_URL_ENV} to use postgres:// or postgresql://."
        )
    if not parsed.hostname or not parsed.path or parsed.path == "/":
        raise WNBAStep16BLifecycleIntegrityError(
            f"Step 16B {DATABASE_URL_ENV} must identify a PostgreSQL host and database."
        )
    return {
        "configured": True,
        "scheme": scheme,
        "credential_value_exposed": False,
    }


def validate_step16b_enablement(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    source = dict(os.environ if env is None else env)
    if not step16b_durable_lifecycle_enabled(source):
        raise WNBAStep16BLifecycleDisabledError(
            f"Step 16B requires {STEP16B_DURABLE_LIFECYCLE_ENABLED_ENV}=true."
        )
    bad = [key for key in _FORBIDDEN_TRUE_ENV_KEYS if _truthy(source.get(key))]
    if bad:
        raise WNBAStep16BLifecycleDisabledError(
            "Step 16B refuses production/scheduler/persistence/write switches: "
            + ", ".join(bad)
        )
    if not persistence_driver_available():
        raise WNBAStep16BLifecycleIntegrityError(
            "Step 16B requires psycopg 3 to be packaged before lifecycle binding."
        )
    secret = _database_secret_status(source)
    if secret["configured"] is not True:
        raise WNBAStep16BLifecycleDisabledError(
            f"Step 16B requires {DATABASE_URL_ENV} from the deployment secret manager."
        )
    false_constants = (
        DEFAULT_ENABLED,
        PRODUCTION_ACTIVATION_ALLOWED,
        PRODUCTION_CANARY_ALLOWED,
        AUTOMATIC_RUNTIME_EXECUTION_ALLOWED,
        BACKGROUND_DAEMON_ALLOWED,
        BACKGROUND_THREAD_ALLOWED,
        BACKGROUND_TASK_ALLOWED,
        PUBLIC_PERSISTENCE_API_ALLOWED,
        SUPABASE_REST_WRITE_ALLOWED,
        WAGERING_ALLOWED,
        AUTHENTICATION_ALLOWED,
        COOKIES_ALLOWED,
        BASKETBALL_MODEL_MUTATION_ALLOWED,
        RANKING_MUTATION_ALLOWED,
        SECRETS_IN_REPOSITORY_ALLOWED,
        DATABASE_CONNECTION_DURING_LIFESPAN_ALLOWED,
    )
    if any(value is not False for value in false_constants):
        raise WNBAStep16BLifecycleIntegrityError("Step 16B safety constant drift.")
    true_constants = (
        PERSISTENCE_DRIVER_PACKAGING_ALLOWED,
        SECRET_MANAGER_REFERENCE_ALLOWED,
        FASTAPI_LIFESPAN_BINDING_ALLOWED,
        FROZEN_FOREGROUND_RUNNER_BINDING_ALLOWED,
    )
    if any(value is not True for value in true_constants):
        raise WNBAStep16BLifecycleIntegrityError("Step 16B integration capability drift.")
    if step14c.run_step14c_durable_restart_lease.__module__ != step14c.__name__:
        raise WNBAStep16BLifecycleIntegrityError("Step 16B frozen Step-14C runner binding drift.")
    return secret


def build_step16b_lifecycle_status(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    source = dict(os.environ if env is None else env)
    enabled = step16b_durable_lifecycle_enabled(source)
    if not enabled:
        return {
            "data_type": "wnba_step16b_lifecycle_status",
            "schema_version": SCHEMA_VERSION,
            "integration_version": INTEGRATION_VERSION,
            "enabled": False,
            "status": "disabled_default_off",
            "driver_available": persistence_driver_available(),
            "database_secret_configured": bool(str(source.get(DATABASE_URL_ENV) or "").strip()),
            "database_connected": False,
            "runtime_runner_bound": False,
            "runtime_executed": False,
            "background_task_started": False,
            "production_activation": False,
        }
    secret = validate_step16b_enablement(source)
    return {
        "data_type": "wnba_step16b_lifecycle_status",
        "schema_version": SCHEMA_VERSION,
        "integration_version": INTEGRATION_VERSION,
        "enabled": True,
        "status": "bound_not_executed",
        "driver_available": True,
        "database_secret_configured": True,
        "database_secret_scheme": secret["scheme"],
        "credential_value_exposed": False,
        "database_connected": False,
        "runtime_runner_bound": True,
        "runtime_executed": False,
        "background_task_started": False,
        "production_activation": False,
    }


def get_step16b_runtime_binding(
    env: Mapping[str, str] | None = None,
) -> Callable[..., dict[str, Any]] | None:
    source = dict(os.environ if env is None else env)
    if not step16b_durable_lifecycle_enabled(source):
        return None
    validate_step16b_enablement(source)
    return step14c.run_step14c_durable_restart_lease


def _set_app_state(app: Any, *, status: Mapping[str, Any], runner: Any) -> None:
    state = getattr(app, "state", None)
    if state is None:
        raise WNBAStep16BLifecycleIntegrityError("Step 16B FastAPI app must expose app.state.")
    setattr(state, "wnba_step16b_lifecycle", deepcopy(dict(status)))
    setattr(state, "wnba_step16b_runtime_runner", runner)


@asynccontextmanager
async def step16b_lifespan(app: Any) -> AsyncIterator[None]:
    """Bind the frozen foreground runner without executing or connecting it."""
    env = dict(os.environ)
    status = build_step16b_lifecycle_status(env)
    runner = get_step16b_runtime_binding(env)
    _set_app_state(app, status=status, runner=runner)
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
        _set_app_state(app, status=shutdown, runner=None)


__all__ = [
    "BRANCH",
    "DATABASE_URL_ENV",
    "DEFAULT_ENABLED",
    "INTEGRATION_VERSION",
    "SAFETY_CONTRACT",
    "SCHEMA_VERSION",
    "SOURCE",
    "STEP16A_CERTIFIED_SHA",
    "STEP16A_CONTRACT_CONTENT_SHA256",
    "STEP16A_CONTRACT_ID",
    "STEP16B_DURABLE_LIFECYCLE_ENABLED_ENV",
    "WNBAStep16BLifecycleDisabledError",
    "WNBAStep16BLifecycleIntegrityError",
    "build_step16b_lifecycle_status",
    "get_step16b_runtime_binding",
    "persistence_driver_available",
    "step16b_durable_lifecycle_enabled",
    "step16b_lifespan",
    "validate_step16b_enablement",
]
