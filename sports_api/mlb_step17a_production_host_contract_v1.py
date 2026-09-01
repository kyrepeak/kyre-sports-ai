"""MLB Step 17A — production host contract.

Step 17A adds no always-on MLB behavior. It freezes the exact Step 16E release
against the already-provisioned Kyre Sports API Render Docker host, verifies the
host identity and container/health/start-stop contract, and keeps every MLB
runtime, scheduler, persistence-write, provider, actionable, and wagering gate
fail-closed.

The existing Render service is shared with the WNBA runtime. Step 17A is
therefore read-only with respect to Render: it MUST NOT replace the currently
running shared-host release. Step 17B is the first phase allowed to perform a
separately certified controlled hosted activation with rollback protection.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import re
from typing import Any, Mapping

from sports_api import mlb_step16e_final_production_freeze_v1 as step16e
from sports_api.mlb_step9_final_freeze_v1 import PROTECTED_INVARIANTS

DATA_TYPE = "mlb_step17a_production_host_contract_v1"
SCHEMA_VERSION = 1
CONTRACT_ID = "mlb_step17a_production_host_contract_2026_v1"
BRANCH = "mlb-step17a-production-host-contract"
FINAL_CERTIFICATION_MARKER = "MLB_STEP17A_PRODUCTION_HOST_CONTRACT_GREEN"
RUNTIME_MODE = "SHADOW_ONLY"

STEP16E_FROZEN_SHA = "9676d4b657b4928a61563014e1bc519dfe52fa26"
STEP16E_TESTED_HEAD_SHA = "b4a69b96c9783006d8dd463fc6407c44958081e5"
STEP16E_TREE_SHA = "d87955d61fa7c463ebe4f03601dab854ccc40622"
STEP16E_RELEASE_ID = "mlb_step16_controlled_production_activation_2026_regular_season_frozen_v1"
STEP16E_RELEASE_CONTENT_SHA256 = "769e16a66c87a49a627e9bec80f3d119ec10410f44abc5e10444b0ec3b0617ff"
STEP16E_FINAL_EVIDENCE_CONTENT_SHA256 = "5987ae2e98b72031007757c631772f26fac0134a2f6ca3a19e496bfc26e0d7a0"
STEP16E_FINAL_MARKER = "MLB_STEP16E_FINAL_PRODUCTION_FREEZE_GREEN"
STEP16E_DOCKERFILE_BLOB_SHA = "34a542b0a32456de58b81fd711fef215e618469f"
STEP16E_MAIN_BLOB_SHA = "839a7cae1b69b456260031803856df1f7f9661ec"

EVIDENCE_PATH = "sports_api/certification/mlb_step17a_production_host_contract_evidence.json"
EVIDENCE_CONTENT_SHA256 = "56203a5f1f02f6979e0089d85955597158cac663370d2dd362e7bee7ce4e9d98"

STEP17A_ENABLED_ENV = "MLB_STEP17A_HOST_CONTRACT_ENABLED"
EXPECTED_REVISION_ENV = "MLB_STEP17A_EXPECTED_REVISION"
DEPLOYMENT_MODE_ENV = "MLB_DEPLOYMENT_MODE"
DATABASE_URL_ENV = "KYRE_DATABASE_URL"
DEFAULT_ENABLED = False

EXPECTED_RENDER_SERVICE_ID = "srv-da84q6ifngtc73bdbm6g"
EXPECTED_RENDER_SERVICE_NAME = "kyre-sports-api"
EXPECTED_RENDER_SERVICE_TYPE = "web_service"
EXPECTED_RENDER_RUNTIME = "docker"
EXPECTED_RENDER_REPOSITORY = "https://github.com/kyrepeak/kyre-sports-ai"
EXPECTED_RENDER_URL = "https://kyre-sports-api.onrender.com"
EXPECTED_RENDER_REGION = "oregon"
EXPECTED_RENDER_ROOT_DIR = ""
EXPECTED_RENDER_HEALTH_CHECK_PATH = "/health"
EXPECTED_RENDER_NUM_INSTANCES = 1
EXPECTED_RENDER_AUTO_DEPLOY = "no"

CONTAINER_PORT_ENV = "PORT"
CONTAINER_DEFAULT_PORT = 8000
CONTAINER_EXPOSED_PORT = 8000
WEB_CONCURRENCY_ENV = "WEB_CONCURRENCY"
CONTAINER_DEFAULT_WORKERS = 2
HEALTH_PATH = "/health"
HEALTH_EXPECTED_STATUS = "ok"
HEALTH_EXPECTED_SERVICE = "kyre-sports-api"
START_COMMAND = (
    "exec uvicorn sports_api.main:app --host 0.0.0.0 "
    "--port ${PORT:-8000} --workers ${WEB_CONCURRENCY:-2}"
)

READ_ONLY_RENDER_INVENTORY_ALLOWED = True
LOCAL_FROZEN_CONTAINER_HEALTH_PROOF_ALLOWED = True
EXISTING_SHARED_HOST_IDENTIFIED = True
AUTO_DEPLOY_MUST_REMAIN_DISABLED = True
NEW_RENDER_SERVICE_CREATION_ALLOWED = False
RENDER_SERVICE_MUTATION_ALLOWED = False
RENDER_DEPLOY_ALLOWED = False
CONTINUOUS_PRODUCTION_RUNTIME_ALLOWED = False
PRODUCTION_SCHEDULER_ALLOWED = False
GLOBAL_PERSISTENCE_AUTOSTART_ALLOWED = False
AUTOMATIC_RESTART_AUTOSTART_ALLOWED = False
BACKGROUND_WORKER_ALLOWED = False
BACKGROUND_THREAD_ALLOWED = False
BACKGROUND_TASK_ALLOWED = False
PUBLIC_PERSISTENCE_API_ALLOWED = False
SUPABASE_REST_WRITE_ALLOWED = False
PROVIDER_CALLS_ALLOWED = False
SPORTSBOOK_CALLS_ALLOWED = False
ACTIONABLE_OUTPUT_ALLOWED = False
WAGERING_ALLOWED = False
AUTH_MUTATION_ALLOWED = False
COOKIE_MUTATION_ALLOWED = False
MODEL_MUTATION_ALLOWED = False
RANKING_MUTATION_ALLOWED = False
SECRETS_OUTPUT_ALLOWED = False
STEP17B_REQUIRED_FOR_HOSTED_ACTIVATION = True

_FORBIDDEN_TRUE_ENV_KEYS = (
    "MLB_PRODUCTION_RUNTIME_ENABLED",
    "MLB_PRODUCTION_SCHEDULER_ENABLED",
    "MLB_ACTIONABLE_OUTPUT_ENABLED",
    "MLB_WAGERING_ENABLED",
    "MLB_SUPABASE_REST_WRITE_ENABLED",
    "MLB_STEP16B_DURABLE_LIFECYCLE_ENABLED",
    "MLB_STEP16C_LIVE_POSTGRESQL_CANARY_ENABLED",
    "MLB_STEP16D_CONTROLLED_PRODUCTION_ACTIVATION_ENABLED",
    "MLB_STEP16E_FINAL_PRODUCTION_FREEZE_ENABLED",
    "MLB_STEP14C_DURABLE_RESTART_LEASE_ENABLED",
    "MLB_STEP14B_DATABASE_CHECKPOINT_ADAPTER_ENABLED",
    "MLB_STEP14B_DATABASE_READ_ENABLED",
    "MLB_STEP14B_DATABASE_WRITE_ENABLED",
)
_GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")

SAFETY_CONTRACT = {
    "render_service_mutation": False,
    "render_deploy": False,
    "new_render_service_creation": False,
    "continuous_production_runtime": False,
    "production_scheduler": False,
    "global_persistence_autostart": False,
    "automatic_restart_autostart": False,
    "background_worker": False,
    "background_thread": False,
    "background_task": False,
    "public_persistence_api": False,
    "supabase_rest_write": False,
    "provider_network_calls": False,
    "sportsbook_network_calls": False,
    "actionable_output": False,
    "wagering": False,
    "auth_mutation": False,
    "cookie_mutation": False,
    "model_mutation": False,
    "ranking_mutation": False,
    "secrets_in_output": False,
}


class MLBStep17AHostContractDisabledError(RuntimeError):
    """Raised unless the non-activating Step 17A contract gate is explicit."""


class MLBStep17AHostContractIntegrityError(RuntimeError):
    """Raised when frozen release or host identity boundaries drift."""


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled",
    }


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
    surface = deepcopy(dict(evidence))
    surface.pop("observed_at_utc", None)
    surface.pop("evidence_content_sha256", None)
    return surface


def step17a_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(STEP17A_ENABLED_ENV))


def expected_host_env(database_url: str = "postgresql://user:pass@example.invalid/postgres") -> dict[str, str]:
    env = {
        STEP17A_ENABLED_ENV: "true",
        EXPECTED_REVISION_ENV: STEP16E_FROZEN_SHA,
        DEPLOYMENT_MODE_ENV: "container",
        DATABASE_URL_ENV: database_url,
    }
    for key in _FORBIDDEN_TRUE_ENV_KEYS:
        env[key] = "false"
    return env


def _git_blob_sha(path: str | Path) -> str:
    raw = Path(path).read_bytes()
    header = f"blob {len(raw)}\0".encode("ascii")
    return hashlib.sha1(header + raw).hexdigest()


def validate_frozen_packaging(repo_root: str | Path = ".") -> dict[str, str]:
    root = Path(repo_root)
    observed = {
        "dockerfile_blob_sha": _git_blob_sha(root / "sports_api" / "Dockerfile"),
        "main_blob_sha": _git_blob_sha(root / "sports_api" / "main.py"),
    }
    expected = {
        "dockerfile_blob_sha": STEP16E_DOCKERFILE_BLOB_SHA,
        "main_blob_sha": STEP16E_MAIN_BLOB_SHA,
    }
    if observed != expected:
        raise MLBStep17AHostContractIntegrityError(
            f"Step 17A frozen packaging drift: observed={observed!r} expected={expected!r}"
        )
    return observed


def _assert_step16e_identity() -> None:
    checks = {
        "release_id": step16e.RELEASE_ID == STEP16E_RELEASE_ID,
        "marker": step16e.FINAL_CERTIFICATION_MARKER == STEP16E_FINAL_MARKER,
        "runtime_mode": step16e.RUNTIME_MODE == RUNTIME_MODE,
        "evidence_hash": step16e.FINAL_EVIDENCE_CONTENT_SHA256 == STEP16E_FINAL_EVIDENCE_CONTENT_SHA256,
        "continuous": step16e.CONTINUOUS_PRODUCTION_RUNTIME_ALLOWED is False,
        "scheduler": step16e.PRODUCTION_SCHEDULER_ALLOWED is False,
        "hosted": step16e.HOSTED_ALWAYS_ON_SERVICE_CERTIFIED is False,
        "providers": step16e.PROVIDER_CALLS_ALLOWED is False,
        "sportsbooks": step16e.SPORTSBOOK_CALLS_ALLOWED is False,
        "wagering": step16e.WAGERING_ALLOWED is False,
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise MLBStep17AHostContractIntegrityError(
            "Step 16E frozen identity drift: " + ", ".join(failed)
        )
    if any(value is not False for value in PROTECTED_INVARIANTS.values()):
        raise MLBStep17AHostContractIntegrityError("protected MLB invariant drift")


def load_step17a_evidence(path: str = EVIDENCE_PATH) -> dict[str, Any]:
    try:
        evidence = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MLBStep17AHostContractIntegrityError("Step 17A cannot load host evidence") from exc
    if not isinstance(evidence, dict):
        raise MLBStep17AHostContractIntegrityError("Step 17A evidence must be an object")
    observed = str(evidence.get("evidence_content_sha256") or "").lower()
    expected = _canonical_hash(_evidence_hash_surface(evidence))
    if observed != expected or expected != EVIDENCE_CONTENT_SHA256:
        raise MLBStep17AHostContractIntegrityError("Step 17A evidence content hash drift")
    return evidence


def validate_step17a_evidence(evidence: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(evidence, Mapping):
        raise MLBStep17AHostContractIntegrityError("Step 17A evidence must be a mapping")
    value = dict(evidence)
    if value.get("data_type") != "mlb_step17a_production_host_contract_evidence_v1":
        raise MLBStep17AHostContractIntegrityError("Step 17A evidence type drift")
    if value.get("schema_version") != 1:
        raise MLBStep17AHostContractIntegrityError("Step 17A evidence schema drift")

    frozen = value.get("step16e")
    inventory = value.get("render_inventory")
    boundary = value.get("host_boundary")
    safety = value.get("safety")
    if not all(isinstance(v, Mapping) for v in (frozen, inventory, boundary, safety)):
        raise MLBStep17AHostContractIntegrityError("Step 17A evidence shape drift")

    expected_frozen = {
        "main_merge_sha": STEP16E_FROZEN_SHA,
        "tested_head_sha": STEP16E_TESTED_HEAD_SHA,
        "tree_sha": STEP16E_TREE_SHA,
        "release_content_sha256": STEP16E_RELEASE_CONTENT_SHA256,
        "final_evidence_content_sha256": STEP16E_FINAL_EVIDENCE_CONTENT_SHA256,
        "dockerfile_blob_sha": STEP16E_DOCKERFILE_BLOB_SHA,
        "main_blob_sha": STEP16E_MAIN_BLOB_SHA,
    }
    for key, expected in expected_frozen.items():
        if frozen.get(key) != expected:
            raise MLBStep17AHostContractIntegrityError(f"Step 17A frozen evidence drift: {key}")

    if inventory.get("mutation_performed") is not False or inventory.get("service_count") != 1:
        raise MLBStep17AHostContractIntegrityError("Step 17A Render inventory boundary drift")
    validate_render_service_identity(inventory.get("service"), evidence_mode=True)

    required_boundary = {
        "existing_shared_service_identified": True,
        "new_service_created": False,
        "render_mutated": False,
        "deploy_triggered": False,
        "current_host_replaced": False,
        "mlb_always_on_activated": False,
        "step17b_required_for_activation": True,
    }
    for key, expected in required_boundary.items():
        if boundary.get(key) is not expected:
            raise MLBStep17AHostContractIntegrityError(f"Step 17A host-boundary drift: {key}")

    required_safety = {
        "production_runtime_started": False,
        "production_scheduler_started": False,
        "database_connection_opened": False,
        "database_write_performed": False,
        "provider_calls": 0,
        "sportsbook_calls": 0,
        "actionable_output_enabled": False,
        "wagering_enabled": False,
        "credential_value_exposed": False,
    }
    for key, expected in required_safety.items():
        if safety.get(key) != expected:
            raise MLBStep17AHostContractIntegrityError(f"Step 17A safety drift: {key}")
    return deepcopy(value)


def _service_shape(service: Mapping[str, Any]) -> dict[str, Any]:
    details = service.get("serviceDetails") if isinstance(service.get("serviceDetails"), Mapping) else {}
    return {
        "id": service.get("id"),
        "name": service.get("name"),
        "type": service.get("type"),
        "runtime": details.get("runtime") or details.get("env") or service.get("runtime"),
        "repo": service.get("repo"),
        "url": details.get("url") or service.get("url"),
        "region": details.get("region") or service.get("region"),
        "root_dir": service.get("rootDir") if "rootDir" in service else service.get("root_dir"),
        "health_check_path": details.get("healthCheckPath") or service.get("health_check_path"),
        "num_instances": details.get("numInstances") if "numInstances" in details else service.get("num_instances"),
        "auto_deploy": service.get("autoDeploy") if "autoDeploy" in service else service.get("auto_deploy"),
        "branch": service.get("branch") or service.get("observed_branch"),
    }


def validate_render_service_identity(
    service: Mapping[str, Any] | None,
    *,
    evidence_mode: bool = False,
) -> dict[str, Any]:
    if not isinstance(service, Mapping):
        raise MLBStep17AHostContractIntegrityError("Step 17A Render service is unavailable")
    observed = _service_shape(service)
    expected = {
        "id": EXPECTED_RENDER_SERVICE_ID,
        "name": EXPECTED_RENDER_SERVICE_NAME,
        "type": EXPECTED_RENDER_SERVICE_TYPE,
        "runtime": EXPECTED_RENDER_RUNTIME,
        "repo": EXPECTED_RENDER_REPOSITORY,
        "url": EXPECTED_RENDER_URL,
        "region": EXPECTED_RENDER_REGION,
        "root_dir": EXPECTED_RENDER_ROOT_DIR,
        "health_check_path": EXPECTED_RENDER_HEALTH_CHECK_PATH,
        "num_instances": EXPECTED_RENDER_NUM_INSTANCES,
        "auto_deploy": EXPECTED_RENDER_AUTO_DEPLOY,
    }
    for key, expected_value in expected.items():
        if observed.get(key) != expected_value:
            raise MLBStep17AHostContractIntegrityError(
                f"Step 17A Render identity drift: {key}={observed.get(key)!r} expected={expected_value!r}"
            )
    if evidence_mode and not str(observed.get("branch") or "").strip():
        raise MLBStep17AHostContractIntegrityError("Step 17A evidence missing observed shared-host branch")
    return observed


def _validate_database_url(value: object) -> None:
    raw = str(value or "").strip()
    if not raw:
        raise MLBStep17AHostContractDisabledError(
            f"Step 17A requires secret-manager {DATABASE_URL_ENV} to be configured"
        )
    if not (raw.startswith("postgresql://") or raw.startswith("postgres://")):
        raise MLBStep17AHostContractDisabledError(
            f"Step 17A requires {DATABASE_URL_ENV} to be a PostgreSQL URL"
        )


def validate_host_contract(
    env: Mapping[str, str] | None = None,
    *,
    build_revision: str | None = None,
    repo_root: str | Path = ".",
) -> dict[str, Any]:
    source = dict(os.environ if env is None else env)
    if not step17a_enabled(source):
        raise MLBStep17AHostContractDisabledError(f"Step 17A requires {STEP17A_ENABLED_ENV}=true")
    bad = [key for key in _FORBIDDEN_TRUE_ENV_KEYS if _truthy(source.get(key))]
    if bad:
        raise MLBStep17AHostContractDisabledError(
            "Step 17A refuses activation/write switches: " + ", ".join(bad)
        )
    if str(source.get(DEPLOYMENT_MODE_ENV) or "").strip().casefold() != "container":
        raise MLBStep17AHostContractDisabledError(f"Step 17A requires {DEPLOYMENT_MODE_ENV}=container")

    expected_revision = str(source.get(EXPECTED_REVISION_ENV) or "").strip().lower()
    if _GIT_SHA_RE.fullmatch(expected_revision) is None or expected_revision != STEP16E_FROZEN_SHA:
        raise MLBStep17AHostContractIntegrityError("Step 17A expected revision is not exact frozen Step 16E")
    if build_revision is not None and str(build_revision).strip().lower() != STEP16E_FROZEN_SHA:
        raise MLBStep17AHostContractIntegrityError("Step 17A build revision does not match frozen Step 16E")
    _validate_database_url(source.get(DATABASE_URL_ENV))
    _assert_step16e_identity()
    packaging = validate_frozen_packaging(repo_root)
    evidence = validate_step17a_evidence(load_step17a_evidence())

    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "contract_id": CONTRACT_ID,
        "branch": BRANCH,
        "status": "host_contract_ready_shared_host_unchanged_activation_deferred",
        "frozen_step16e_sha": STEP16E_FROZEN_SHA,
        "frozen_step16e_tested_head_sha": STEP16E_TESTED_HEAD_SHA,
        "frozen_step16e_tree_sha": STEP16E_TREE_SHA,
        "frozen_step16e_release_content_sha256": STEP16E_RELEASE_CONTENT_SHA256,
        "frozen_step16e_evidence_content_sha256": STEP16E_FINAL_EVIDENCE_CONTENT_SHA256,
        **packaging,
        "render_service_id": EXPECTED_RENDER_SERVICE_ID,
        "render_service_name": EXPECTED_RENDER_SERVICE_NAME,
        "render_service_url": EXPECTED_RENDER_URL,
        "render_runtime": EXPECTED_RENDER_RUNTIME,
        "render_repository": EXPECTED_RENDER_REPOSITORY,
        "render_region": EXPECTED_RENDER_REGION,
        "render_health_check_path": EXPECTED_RENDER_HEALTH_CHECK_PATH,
        "render_num_instances": EXPECTED_RENDER_NUM_INSTANCES,
        "render_auto_deploy": EXPECTED_RENDER_AUTO_DEPLOY,
        "inventory_observed_branch": evidence["render_inventory"]["service"]["observed_branch"],
        "container_port_env": CONTAINER_PORT_ENV,
        "container_default_port": CONTAINER_DEFAULT_PORT,
        "container_exposed_port": CONTAINER_EXPOSED_PORT,
        "web_concurrency_env": WEB_CONCURRENCY_ENV,
        "container_default_workers": CONTAINER_DEFAULT_WORKERS,
        "health_path": HEALTH_PATH,
        "health_expected_status": HEALTH_EXPECTED_STATUS,
        "health_expected_service": HEALTH_EXPECTED_SERVICE,
        "start_command": START_COMMAND,
        "fastapi_lifespan_shutdown_required": True,
        "database_secret_configured": True,
        "database_connection_opened": False,
        "database_secret_exposed": False,
        "read_only_render_inventory_allowed": True,
        "local_frozen_container_health_proof_allowed": True,
        "existing_shared_host_identified": True,
        "render_service_mutation_allowed": False,
        "render_deploy_allowed": False,
        "new_render_service_creation_allowed": False,
        "production_runtime_enabled": False,
        "production_scheduler_enabled": False,
        "provider_calls": 0,
        "sportsbook_calls": 0,
        "actionable_output_enabled": False,
        "wagering_enabled": False,
        "step17b_required_for_hosted_activation": True,
        "final_certification_marker": FINAL_CERTIFICATION_MARKER,
        "safety_contract": deepcopy(SAFETY_CONTRACT),
    }


def production_host_manifest() -> dict[str, Any]:
    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "contract_id": CONTRACT_ID,
        "branch": BRANCH,
        "final_certification_marker": FINAL_CERTIFICATION_MARKER,
        "default_enabled": DEFAULT_ENABLED,
        "step16e_frozen_sha": STEP16E_FROZEN_SHA,
        "step16e_tested_head_sha": STEP16E_TESTED_HEAD_SHA,
        "step16e_tree_sha": STEP16E_TREE_SHA,
        "step16e_release_content_sha256": STEP16E_RELEASE_CONTENT_SHA256,
        "step16e_final_evidence_content_sha256": STEP16E_FINAL_EVIDENCE_CONTENT_SHA256,
        "step16e_dockerfile_blob_sha": STEP16E_DOCKERFILE_BLOB_SHA,
        "step16e_main_blob_sha": STEP16E_MAIN_BLOB_SHA,
        "evidence_content_sha256": EVIDENCE_CONTENT_SHA256,
        "existing_render_service_id": EXPECTED_RENDER_SERVICE_ID,
        "existing_render_service_name": EXPECTED_RENDER_SERVICE_NAME,
        "existing_render_runtime": EXPECTED_RENDER_RUNTIME,
        "existing_render_repository": EXPECTED_RENDER_REPOSITORY,
        "existing_render_url": EXPECTED_RENDER_URL,
        "existing_render_region": EXPECTED_RENDER_REGION,
        "health_path": HEALTH_PATH,
        "start_command": START_COMMAND,
        "auto_deploy_must_remain_disabled": AUTO_DEPLOY_MUST_REMAIN_DISABLED,
        "read_only_render_inventory_allowed": READ_ONLY_RENDER_INVENTORY_ALLOWED,
        "local_frozen_container_health_proof_allowed": LOCAL_FROZEN_CONTAINER_HEALTH_PROOF_ALLOWED,
        "existing_shared_host_identified": EXISTING_SHARED_HOST_IDENTIFIED,
        "new_render_service_creation_allowed": NEW_RENDER_SERVICE_CREATION_ALLOWED,
        "render_service_mutation_allowed": RENDER_SERVICE_MUTATION_ALLOWED,
        "render_deploy_allowed": RENDER_DEPLOY_ALLOWED,
        "continuous_production_runtime_allowed": CONTINUOUS_PRODUCTION_RUNTIME_ALLOWED,
        "production_scheduler_allowed": PRODUCTION_SCHEDULER_ALLOWED,
        "step17b_required_for_hosted_activation": STEP17B_REQUIRED_FOR_HOSTED_ACTIVATION,
        "safety_contract": deepcopy(SAFETY_CONTRACT),
        **PROTECTED_INVARIANTS,
    }


__all__ = [
    "DATA_TYPE", "SCHEMA_VERSION", "CONTRACT_ID", "BRANCH",
    "FINAL_CERTIFICATION_MARKER", "STEP16E_FROZEN_SHA", "STEP16E_TESTED_HEAD_SHA",
    "STEP16E_TREE_SHA", "STEP16E_RELEASE_CONTENT_SHA256",
    "STEP16E_FINAL_EVIDENCE_CONTENT_SHA256", "STEP16E_DOCKERFILE_BLOB_SHA",
    "STEP16E_MAIN_BLOB_SHA", "EVIDENCE_PATH", "EVIDENCE_CONTENT_SHA256",
    "STEP17A_ENABLED_ENV", "EXPECTED_REVISION_ENV", "DEPLOYMENT_MODE_ENV",
    "DATABASE_URL_ENV", "EXPECTED_RENDER_SERVICE_ID", "EXPECTED_RENDER_SERVICE_NAME",
    "EXPECTED_RENDER_RUNTIME", "EXPECTED_RENDER_REPOSITORY", "EXPECTED_RENDER_URL",
    "EXPECTED_RENDER_REGION", "HEALTH_PATH", "START_COMMAND", "SAFETY_CONTRACT",
    "MLBStep17AHostContractDisabledError", "MLBStep17AHostContractIntegrityError",
    "step17a_enabled", "expected_host_env", "validate_frozen_packaging",
    "load_step17a_evidence", "validate_step17a_evidence",
    "validate_render_service_identity", "validate_host_contract",
    "production_host_manifest",
]
