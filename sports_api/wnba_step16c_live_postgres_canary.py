"""WNBA Step 16C: live PostgreSQL canary plus bound-runner integration canary.

Step 16C is additive to certified Step 16B. It seals a real PostgreSQL canary
executed against the live Supabase ``kyre_runtime`` schema and separately
executes the exact Step-16B-bound frozen Step-14C foreground runner in CI through
injected DBAPI transports. This split is deliberate: the connected Supabase
management surface can execute PostgreSQL but does not expose the database
password required for a direct psycopg connection from the deployed container.

Production remains OFF. No background scheduler, global persistence autostart,
public persistence endpoint, wagering, model mutation, or ranking mutation is
authorized here. Direct deployed-container psycopg connectivity is still a
Step-16D activation prerequisite.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from sports_api import wnba_step14c_durable_restart_lease as step14c
from sports_api import wnba_step16b_production_lifecycle as step16b

SOURCE = "Kyre Sports API WNBA Step 16C live PostgreSQL and bound runner canary"
SCHEMA_VERSION = "wnba_step_16c_live_postgres_canary_v1"
INTEGRATION_VERSION = "wnba_step16c_live_postgres_bound_runner_canary_v1"
CONTRACT_ID = "wnba_step16c_live_postgres_bound_runner_canary_2026_regular_v1"
BRANCH = "wnba-step16c-live-postgres-canary-20260828"
SEASON = 2026
SEASON_TYPE = "Regular Season"

STEP16B_CERTIFIED_SHA = "f898ca410c10db59f635888166d1666a952d8bd7"
STEP16B_CONTRACT_ID = "wnba_step16b_production_packaging_lifecycle_2026_regular_v1"
STEP16B_CONTRACT_CONTENT_SHA256 = "bcc79487cacf86bfb65e94ad0de2b8906c2bca1546ec1afd76ddc413ad30dd1e"
STEP16A_CERTIFIED_SHA = "4ea88aa9a54f5110a03e9e4374219ed15ab30def"
STEP16A_CONTRACT_CONTENT_SHA256 = "2d8c373dded7eb971d6d6bf6b4a5c9bdfc7bd19de5ddcf1ef83158a0b7d2000e"
STEP15C_CERTIFIED_SHA = "5e24210d7aef90143ba016e368cd49d3ee1a7f19"
STEP15_RELEASE_CONTENT_SHA256 = "537df3ec10999071941597e71f4e6361e246db98b17c13a3a31a944f9b8e9a2b"

LIVE_EVIDENCE_PATH = "sports_api/certification/wnba_step16c_live_postgres_canary_evidence.json"
LIVE_EVIDENCE_CONTENT_SHA256 = "48463e66cf35c4cd47192436267f08d76d2e980f8f5f8b5d7b7fbc72b47e5810"
EXPECTED_SUPABASE_PROJECT_REF = "jqajcdckalsfizbvngiu"
EXPECTED_CANARY_SLATE_DATE = "2026-01-16"
EXPECTED_CHECKPOINT_KEY = "wnba:runtime:2026:regular-season:2026-01-16"
EXPECTED_LEASE_KEY = EXPECTED_CHECKPOINT_KEY + ":scheduler-lease"
EXPECTED_ENVELOPE_SHA256 = "97a9b26d9e5e668a748d99558ba7d5702283aa5b372747d6c153dee0fc086791"
EXPECTED_CONTROLLER_STATE_SHA256 = "4c0758c6cce74a93ca7c9d4c62f94fd5e569e6a4e8034f5dde4515a40ff9d70f"

STEP16C_LIVE_POSTGRES_CANARY_ENABLED_ENV = "WNBA_STEP16C_LIVE_POSTGRES_CANARY_ENABLED"

DEFAULT_ENABLED = False
LIVE_POSTGRESQL_MANAGEMENT_CANARY_CERTIFIED = True
BOUND_STEP14C_RUNNER_CANARY_ALLOWED = True
INJECTED_DBAPI_CANARY_TRANSPORT_ALLOWED = True
DIRECT_PSYCOG_LIVE_CONNECTION_CERTIFIED = False
DEPLOYED_FASTAPI_CONTAINER_CANARY_CERTIFIED = False
CONTROLLED_PRODUCTION_ACTIVATION_READY = False
PRODUCTION_ACTIVATION_ALLOWED = False
PRODUCTION_RUNTIME_ALLOWED = False
GLOBAL_PERSISTENCE_AUTOSTART_ALLOWED = False
AUTOMATIC_RESTART_ACTIVATION_ALLOWED = False
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
    "production_activation": False,
    "controlled_production_activation_ready": False,
    "global_persistence_autostart": False,
    "automatic_restart_activation": False,
    "background_daemon": False,
    "background_thread": False,
    "background_task": False,
    "public_persistence_api": False,
    "supabase_rest_write": False,
    "wager_action": False,
    "authentication": False,
    "cookies": False,
    "basketball_model_change": False,
    "step8_distribution_change": False,
    "step9_ranking_change": False,
    "step9_qualification_change": False,
    "direct_psycopg_live_connection_certified": False,
    "deployed_fastapi_container_canary_certified": False,
}


class WNBAStep16CCanaryDisabledError(RuntimeError):
    pass


class WNBAStep16CCanaryIntegrityError(RuntimeError):
    pass


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled"
    }


def step16c_canary_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(STEP16C_LIVE_POSTGRES_CANARY_ENABLED_ENV))


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


def _evidence_hash_surface(evidence: Mapping[str, Any]) -> dict[str, Any]:
    result = deepcopy(dict(evidence))
    result.pop("observed_at_utc", None)
    result.pop("evidence_content_sha256", None)
    return result


def _result_hash_surface(result: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: deepcopy(value)
        for key, value in result.items()
        if key not in {"generated_at_utc", "canary_content_sha256"}
    }


def load_step16c_live_evidence(path: str = LIVE_EVIDENCE_PATH) -> dict[str, Any]:
    try:
        evidence = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WNBAStep16CCanaryIntegrityError(
            "Step 16C cannot load committed live PostgreSQL canary evidence."
        ) from exc
    if not isinstance(evidence, dict):
        raise WNBAStep16CCanaryIntegrityError("Step 16C evidence must be an object.")
    observed = str(evidence.get("evidence_content_sha256") or "").lower()
    expected = _canonical_hash(_evidence_hash_surface(evidence))
    if observed != expected or expected != LIVE_EVIDENCE_CONTENT_SHA256:
        raise WNBAStep16CCanaryIntegrityError("Step 16C live evidence content hash drift.")
    return evidence


def validate_step16c_live_evidence(evidence: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(evidence, Mapping):
        raise WNBAStep16CCanaryIntegrityError("Step 16C evidence must be an object.")
    if evidence.get("data_type") != "wnba_step16c_live_postgres_canary_evidence":
        raise WNBAStep16CCanaryIntegrityError("Step 16C evidence data_type drift.")

    project = evidence.get("supabase_project")
    lineage = evidence.get("frozen_lineage")
    scope = evidence.get("canary_scope")
    live = evidence.get("live_results")
    boundary = evidence.get("execution_boundary")
    phase = evidence.get("phase_boundary")
    if not all(isinstance(value, Mapping) for value in (project, lineage, scope, live, boundary, phase)):
        raise WNBAStep16CCanaryIntegrityError("Step 16C evidence object shape drift.")

    if (
        project.get("ref") != EXPECTED_SUPABASE_PROJECT_REF
        or project.get("status") != "ACTIVE_HEALTHY"
        or str(project.get("postgres_engine")) != "17"
    ):
        raise WNBAStep16CCanaryIntegrityError("Step 16C live project identity/health drift.")
    if (
        lineage.get("step16b_certified_sha") != STEP16B_CERTIFIED_SHA
        or lineage.get("step16b_contract_id") != STEP16B_CONTRACT_ID
        or lineage.get("step16b_contract_content_sha256") != STEP16B_CONTRACT_CONTENT_SHA256
        or lineage.get("step16a_certified_sha") != STEP16A_CERTIFIED_SHA
        or lineage.get("step16a_contract_content_sha256") != STEP16A_CONTRACT_CONTENT_SHA256
        or lineage.get("step15c_certified_sha") != STEP15C_CERTIFIED_SHA
        or lineage.get("step15_release_content_sha256") != STEP15_RELEASE_CONTENT_SHA256
    ):
        raise WNBAStep16CCanaryIntegrityError("Step 16C frozen lineage evidence drift.")
    if (
        scope.get("slate_date") != EXPECTED_CANARY_SLATE_DATE
        or scope.get("checkpoint_key") != EXPECTED_CHECKPOINT_KEY
        or scope.get("lease_key") != EXPECTED_LEASE_KEY
        or scope.get("database_role") != "postgres"
    ):
        raise WNBAStep16CCanaryIntegrityError("Step 16C canary scope drift.")

    expected_live = {
        "baseline_checkpoint_rows": 0,
        "baseline_checkpoint_head_rows": 0,
        "baseline_lease_rows": 0,
        "initial_fencing_generation": 1,
        "duplicate_active_acquire_rows": 0,
        "owner_renew_rows": 1,
        "wrong_owner_renew_rows": 0,
        "checkpoint_rows_inside_canary": 1,
        "checkpoint_head_rows_inside_canary": 1,
        "loaded_envelope_sha256": EXPECTED_ENVELOPE_SHA256,
        "loaded_controller_state_sha256": EXPECTED_CONTROLLER_STATE_SHA256,
        "owner_release_rows": 1,
        "lease_rows_after_release_inside_canary": 0,
        "post_rollback_checkpoint_rows": 0,
        "post_rollback_checkpoint_head_rows": 0,
        "post_rollback_lease_rows": 0,
    }
    for key, expected in expected_live.items():
        if live.get(key) != expected:
            raise WNBAStep16CCanaryIntegrityError(f"Step 16C live result drift: {key}.")
    for key in (
        "checkpoint_load_round_trip_exact",
        "transaction_rolled_back",
        "canary_checkpoint_absent_after_rollback",
        "canary_head_absent_after_rollback",
        "canary_lease_absent_after_rollback",
    ):
        if live.get(key) is not True:
            raise WNBAStep16CCanaryIntegrityError(f"Step 16C required live result missing: {key}.")

    required_true_boundary = (
        "live_postgresql_used",
        "supabase_management_sql_used",
        "frozen_step14b_step14c_sql_semantics_exercised_live",
        "bound_step14c_python_runner_canary_required_in_github_actions",
    )
    if any(boundary.get(key) is not True for key in required_true_boundary):
        raise WNBAStep16CCanaryIntegrityError("Step 16C live execution boundary evidence missing.")
    required_false_boundary = (
        "direct_python_psycopg_live_connection",
        "deployed_fastapi_container_connected_live",
        "bound_step14c_python_runner_executed_live",
        "github_actions_live_database_credentials_used",
        "production_scheduler_started",
        "global_persistence_runtime_started",
        "automatic_restart_activation_started",
        "background_worker_started",
        "public_persistence_api_exposed",
        "supabase_rest_write_enabled",
        "wagering_enabled",
    )
    if any(boundary.get(key) is not False for key in required_false_boundary):
        raise WNBAStep16CCanaryIntegrityError("Step 16C execution safety boundary drift.")
    if phase.get("step16c_live_database_canary_complete") is not True:
        raise WNBAStep16CCanaryIntegrityError("Step 16C live database canary is not complete.")
    if phase.get("step16c_bound_runner_path_pending_ci_certification") is not True:
        raise WNBAStep16CCanaryIntegrityError("Step 16C bound runner CI boundary drift.")
    if phase.get("deployed_container_direct_psycopg_canary_not_certified") is not True:
        raise WNBAStep16CCanaryIntegrityError("Step 16C direct psycopg boundary drift.")
    if phase.get("controlled_production_activation_not_authorized") is not True:
        raise WNBAStep16CCanaryIntegrityError("Step 16C production activation boundary drift.")
    return deepcopy(dict(evidence))


def _assert_step16c_integrity(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    source = dict(os.environ if env is None else env)
    if not step16c_canary_enabled(source):
        raise WNBAStep16CCanaryDisabledError(
            f"Step 16C requires {STEP16C_LIVE_POSTGRES_CANARY_ENABLED_ENV}=true."
        )
    bad = [key for key in _FORBIDDEN_TRUE_ENV_KEYS if _truthy(source.get(key))]
    if bad:
        raise WNBAStep16CCanaryDisabledError(
            "Step 16C refuses production/scheduler/global-persistence switches: " + ", ".join(bad)
        )
    try:
        step16b.validate_step16b_enablement(source)
    except Exception as exc:
        raise WNBAStep16CCanaryDisabledError(
            "Step 16C requires the certified Step-16B lifecycle prerequisites."
        ) from exc
    bound = step16b.get_step16b_runtime_binding(source)
    if bound is not step14c.run_step14c_durable_restart_lease:
        raise WNBAStep16CCanaryIntegrityError("Step 16C frozen bound-runner identity drift.")

    false_constants = (
        DEFAULT_ENABLED,
        DIRECT_PSYCOG_LIVE_CONNECTION_CERTIFIED,
        DEPLOYED_FASTAPI_CONTAINER_CANARY_CERTIFIED,
        CONTROLLED_PRODUCTION_ACTIVATION_READY,
        PRODUCTION_ACTIVATION_ALLOWED,
        PRODUCTION_RUNTIME_ALLOWED,
        GLOBAL_PERSISTENCE_AUTOSTART_ALLOWED,
        AUTOMATIC_RESTART_ACTIVATION_ALLOWED,
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
    )
    if any(value is not False for value in false_constants):
        raise WNBAStep16CCanaryIntegrityError("Step 16C forbidden capability drift.")
    true_constants = (
        LIVE_POSTGRESQL_MANAGEMENT_CANARY_CERTIFIED,
        BOUND_STEP14C_RUNNER_CANARY_ALLOWED,
        INJECTED_DBAPI_CANARY_TRANSPORT_ALLOWED,
    )
    if any(value is not True for value in true_constants):
        raise WNBAStep16CCanaryIntegrityError("Step 16C required canary capability drift.")
    evidence = validate_step16c_live_evidence(load_step16c_live_evidence())
    return evidence


def run_step16c_bound_runner_canary(
    step13c_request: Mapping[str, Any],
    *,
    owner_id: str,
    env: Mapping[str, str] | None = None,
    lease_ttl_seconds: int,
    lease_connection_factory: Callable[[], Any] | None,
    checkpoint_connection_factory: Callable[[], Any] | None,
    token_factory: Callable[[], Any] | None = None,
    step13c_runner: Callable[..., Mapping[str, Any]] | None = None,
    runner_kwargs: Mapping[str, Any] | None = None,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    """Invoke the exact Step-16B-bound Step-14C runner using injected CI transports."""
    evidence = _assert_step16c_integrity(env)
    if lease_connection_factory is None or checkpoint_connection_factory is None:
        raise WNBAStep16CCanaryDisabledError(
            "Step 16C CI bound-runner canary requires injected DBAPI transports; direct live psycopg is deferred."
        )
    source = dict(os.environ if env is None else env)
    bound = step16b.get_step16b_runtime_binding(source)
    if bound is not step14c.run_step14c_durable_restart_lease:
        raise WNBAStep16CCanaryIntegrityError("Step 16C bound runner identity changed before invocation.")
    runtime = bound(
        deepcopy(dict(step13c_request)),
        owner_id=owner_id,
        env=source,
        lease_ttl_seconds=lease_ttl_seconds,
        lease_connection_factory=lease_connection_factory,
        checkpoint_connection_factory=checkpoint_connection_factory,
        token_factory=token_factory,
        step13c_runner=step13c_runner,
        runner_kwargs=runner_kwargs,
        generated_at_utc=generated_at_utc,
    )
    runtime = step14c.validate_step14c_runtime_result(runtime)
    generated = (
        datetime.fromisoformat(generated_at_utc.replace("Z", "+00:00")).astimezone(timezone.utc)
        if generated_at_utc
        else datetime.now(timezone.utc)
    )
    result = {
        "data_type": "wnba_step16c_bound_runner_canary_result",
        "schema_version": SCHEMA_VERSION,
        "integration_version": INTEGRATION_VERSION,
        "status": "completed",
        "bound_runner_invoked": True,
        "bound_runner_module": step14c.__name__,
        "database_transport": "injected_dbapi_ci",
        "live_postgresql_management_canary_certified": True,
        "live_evidence_content_sha256": evidence["evidence_content_sha256"],
        "direct_psycopg_live_connection": False,
        "deployed_fastapi_container_connected_live": False,
        "production_activation": False,
        "background_task_started": False,
        "step14c_runtime_result": runtime,
        "generated_at_utc": generated.isoformat(),
    }
    result["canary_content_sha256"] = _canonical_hash(_result_hash_surface(result))
    return result


def validate_step16c_bound_runner_result(result: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(result, Mapping):
        raise WNBAStep16CCanaryIntegrityError("Step 16C bound runner result must be an object.")
    if result.get("data_type") != "wnba_step16c_bound_runner_canary_result":
        raise WNBAStep16CCanaryIntegrityError("Step 16C bound runner result type drift.")
    if result.get("status") != "completed" or result.get("bound_runner_invoked") is not True:
        raise WNBAStep16CCanaryIntegrityError("Step 16C bound runner canary did not complete.")
    if result.get("database_transport") != "injected_dbapi_ci":
        raise WNBAStep16CCanaryIntegrityError("Step 16C bound runner canary transport drift.")
    for key in (
        "direct_psycopg_live_connection",
        "deployed_fastapi_container_connected_live",
        "production_activation",
        "background_task_started",
    ):
        if result.get(key) is not False:
            raise WNBAStep16CCanaryIntegrityError(f"Step 16C forbidden bound runner result drift: {key}.")
    runtime = result.get("step14c_runtime_result")
    step14c.validate_step14c_runtime_result(runtime)
    observed = str(result.get("canary_content_sha256") or "").lower()
    expected = _canonical_hash(_result_hash_surface(result))
    if observed != expected:
        raise WNBAStep16CCanaryIntegrityError("Step 16C bound runner content hash mismatch.")
    return deepcopy(dict(result))


def build_step16c_canary_manifest(
    *,
    env: Mapping[str, str] | None = None,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    evidence = _assert_step16c_integrity(env)
    generated = (
        datetime.fromisoformat(generated_at_utc.replace("Z", "+00:00")).astimezone(timezone.utc)
        if generated_at_utc
        else datetime.now(timezone.utc)
    )
    manifest = {
        "data_type": "wnba_step16c_live_postgres_canary_manifest",
        "schema_version": SCHEMA_VERSION,
        "integration_version": INTEGRATION_VERSION,
        "contract_id": CONTRACT_ID,
        "source": SOURCE,
        "season": SEASON,
        "season_type": SEASON_TYPE,
        "lineage": {
            "step16b_certified_sha": STEP16B_CERTIFIED_SHA,
            "step16b_contract_id": STEP16B_CONTRACT_ID,
            "step16b_contract_content_sha256": STEP16B_CONTRACT_CONTENT_SHA256,
            "step16a_certified_sha": STEP16A_CERTIFIED_SHA,
            "step15c_certified_sha": STEP15C_CERTIFIED_SHA,
            "step15_release_content_sha256": STEP15_RELEASE_CONTENT_SHA256,
        },
        "live_database_canary": {
            "certified": True,
            "supabase_project_ref": EXPECTED_SUPABASE_PROJECT_REF,
            "transaction_rolled_back": True,
            "zero_residue_verified": True,
            "lease_fencing_verified": True,
            "checkpoint_round_trip_verified": True,
            "live_evidence_content_sha256": evidence["evidence_content_sha256"],
        },
        "bound_runner_canary": {
            "exact_step16b_bound_step14c_runner": True,
            "github_actions_injected_dbapi_transport_required": True,
            "direct_psycopg_live_connection_certified": False,
            "deployed_fastapi_container_canary_certified": False,
        },
        "safety_contract": deepcopy(SAFETY_CONTRACT),
        "phase_boundary": {
            "step16c_live_database_canary_complete": True,
            "step16c_bound_runner_ci_canary_required_for_certification": True,
            "direct_deployed_container_psycopg_canary_deferred_to_step16d": True,
            "controlled_production_activation_not_authorized": True,
            "step16d_not_started": True,
        },
        "generated_at_utc": generated.isoformat(),
    }
    surface = {key: deepcopy(value) for key, value in manifest.items() if key != "generated_at_utc"}
    manifest["manifest_content_sha256"] = _canonical_hash(surface)
    return manifest


__all__ = [
    "BOUND_STEP14C_RUNNER_CANARY_ALLOWED",
    "BRANCH",
    "CONTRACT_ID",
    "DEFAULT_ENABLED",
    "DIRECT_PSYCOG_LIVE_CONNECTION_CERTIFIED",
    "EXPECTED_CANARY_SLATE_DATE",
    "EXPECTED_CHECKPOINT_KEY",
    "EXPECTED_LEASE_KEY",
    "INTEGRATION_VERSION",
    "LIVE_EVIDENCE_CONTENT_SHA256",
    "LIVE_EVIDENCE_PATH",
    "LIVE_POSTGRESQL_MANAGEMENT_CANARY_CERTIFIED",
    "PRODUCTION_ACTIVATION_ALLOWED",
    "SAFETY_CONTRACT",
    "SCHEMA_VERSION",
    "SOURCE",
    "STEP16B_CERTIFIED_SHA",
    "STEP16B_CONTRACT_CONTENT_SHA256",
    "STEP16B_CONTRACT_ID",
    "STEP16C_LIVE_POSTGRES_CANARY_ENABLED_ENV",
    "WNBAStep16CCanaryDisabledError",
    "WNBAStep16CCanaryIntegrityError",
    "build_step16c_canary_manifest",
    "load_step16c_live_evidence",
    "run_step16c_bound_runner_canary",
    "step16c_canary_enabled",
    "validate_step16c_bound_runner_result",
    "validate_step16c_live_evidence",
]
