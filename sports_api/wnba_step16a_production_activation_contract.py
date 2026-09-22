"""WNBA Step 16A: production activation readiness contract.

This step is deliberately contract-only. It inspects the frozen Step-15 release
and the existing deployment surface, records the exact blockers that must be
closed before a production canary may exist, and fails closed if any production
runtime switch is already on.

A GREEN Step 16A means the readiness gate correctly identifies the current state;
it does NOT mean production activation is ready or permitted.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any

SOURCE = "Kyre Sports API WNBA Step 16A production activation readiness contract"
SCHEMA_VERSION = "wnba_step_16a_production_activation_readiness_contract_v1"
INTEGRATION_VERSION = "wnba_step16a_production_activation_readiness_v1"
CONTRACT_ID = "wnba_step16a_production_activation_readiness_2026_regular_v1"
BRANCH = "wnba-step16a-production-activation-contract-20260828"
SEASON = 2026
SEASON_TYPE = "Regular Season"

STEP15C_CERTIFIED_SHA = "5e24210d7aef90143ba016e368cd49d3ee1a7f19"
STEP15_RELEASE_ID = "wnba_step15_live_supabase_persistence_2026_regular_season_frozen_v1"
STEP15_RELEASE_CONTENT_SHA256 = "537df3ec10999071941597e71f4e6361e246db98b17c13a3a31a944f9b8e9a2b"

EVIDENCE_PATH = "sports_api/certification/wnba_step16a_production_activation_readiness_evidence.json"
EVIDENCE_CONTENT_SHA256 = "9cf0f80ee2fcf45b1dcf06ca2076ee300cb2f87091135b2da824df8584f8ba97"

DOCKERFILE_PATH = "sports_api/Dockerfile"
README_PATH = "sports_api/README.md"
MAIN_PATH = "sports_api/main.py"
PRODUCTION_ENV_PATH = "sports_api/production.env.example"
BASE_REQUIREMENTS_PATH = "sports_api/requirements.txt"
PERSISTENCE_REQUIREMENTS_PATH = "sports_api/requirements-persistence.txt"

EXPECTED_DEPLOYMENT_BLOBS = {
    DOCKERFILE_PATH: "e06eed5c3b9d65c238e47b3fd2fde1529a785fdf",
    README_PATH: "4f93bb2c1890a1c65ff7b6c7cc21bb857a39f5b5",
    MAIN_PATH: "3735590ad639126ea768103ef234604691362be3",
    PRODUCTION_ENV_PATH: "6962aa11e75906691869d2ed04d2bf50822821c8",
    BASE_REQUIREMENTS_PATH: "84e666d78549778a84f216e80d2bb979c1f6160a",
    PERSISTENCE_REQUIREMENTS_PATH: "46331822d0a55f5a4983d289c73a45ea9745ca89",
}

BLOCKING_REQUIREMENTS = (
    "docker_install_persistence_requirements",
    "deployment_secret_manager_supply_kyre_database_url",
    "bind_frozen_step13_to_step15_runtime_into_explicit_application_lifecycle",
)

STEP16A_PRODUCTION_ACTIVATION_CONTRACT_ENABLED_ENV = (
    "WNBA_STEP16A_PRODUCTION_ACTIVATION_CONTRACT_ENABLED"
)

DEFAULT_ENABLED = False
PRODUCTION_ACTIVATION_ALLOWED = False
PRODUCTION_CANARY_ALLOWED = False
GLOBAL_PERSISTENCE_AUTOSTART_ALLOWED = False
AUTOMATIC_RESTART_ACTIVATION_ALLOWED = False
BACKGROUND_DAEMON_ALLOWED = False
BACKGROUND_THREAD_ALLOWED = False
PUBLIC_PERSISTENCE_API_ALLOWED = False
SUPABASE_REST_WRITE_ALLOWED = False
WAGERING_ALLOWED = False
AUTHENTICATION_ALLOWED = False
COOKIES_ALLOWED = False
BASKETBALL_MODEL_MUTATION_ALLOWED = False
RANKING_MUTATION_ALLOWED = False
RUNTIME_MUTATION_ALLOWED = False
SECRETS_IN_REPOSITORY_ALLOWED = False

READINESS_INSPECTION_ALLOWED = True
DEPLOYMENT_CONTRACT_DEFINITION_ALLOWED = True
FAIL_CLOSED_BLOCKER_CERTIFICATION_ALLOWED = True

SAFETY_CONTRACT = {
    "default_enablement": False,
    "production_runtime": False,
    "production_canary": False,
    "production_activation": False,
    "global_persistence_autostart": False,
    "automatic_restart_activation": False,
    "background_daemon": False,
    "background_thread": False,
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
    "runtime_mutation": False,
}

_FORBIDDEN_TRUE_ENV_KEYS = (
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_PERSISTENCE_ENABLED",
    "WNBA_SUPABASE_WRITE_ENABLED",
    "WNBA_WAGERING_ENABLED",
    "WNBA_STEP12_SCHEDULER_ENABLED",
)


class WNBAStep16AProductionActivationContractDisabledError(RuntimeError):
    """Raised when Step 16A is not isolated behind its explicit gate."""


class WNBAStep16AProductionActivationContractIntegrityError(RuntimeError):
    """Raised when frozen readiness evidence or safety boundaries drift."""


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled"
    }


def step16a_production_activation_contract_enabled(
    env: Mapping[str, str] | None = None,
) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(STEP16A_PRODUCTION_ACTIVATION_CONTRACT_ENABLED_ENV))


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


def _read(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise WNBAStep16AProductionActivationContractIntegrityError(
            f"Step 16A cannot read required deployment file: {path}."
        ) from exc


def _evidence_hash_surface(evidence: Mapping[str, Any]) -> dict[str, Any]:
    result = deepcopy(dict(evidence))
    result.pop("observed_at_utc", None)
    result.pop("evidence_content_sha256", None)
    return result


def load_step16a_readiness_evidence(path: str = EVIDENCE_PATH) -> dict[str, Any]:
    try:
        evidence = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WNBAStep16AProductionActivationContractIntegrityError(
            "Step 16A cannot load readiness evidence."
        ) from exc
    if not isinstance(evidence, dict):
        raise WNBAStep16AProductionActivationContractIntegrityError(
            "Step 16A readiness evidence must be a JSON object."
        )
    expected = _canonical_hash(_evidence_hash_surface(evidence))
    observed = str(evidence.get("evidence_content_sha256") or "").lower()
    if expected != EVIDENCE_CONTENT_SHA256 or observed != expected:
        raise WNBAStep16AProductionActivationContractIntegrityError(
            "Step 16A readiness evidence content hash drift."
        )
    return evidence


def inspect_current_deployment_surface() -> dict[str, Any]:
    dockerfile = _read(DOCKERFILE_PATH)
    readme = _read(README_PATH)
    main = _read(MAIN_PATH)
    prod_env = _read(PRODUCTION_ENV_PATH)
    base_requirements = _read(BASE_REQUIREMENTS_PATH)
    persistence_requirements = _read(PERSISTENCE_REQUIREMENTS_PATH).strip()

    return {
        "container_runtime": "FROM python:3.12-slim" in dockerfile,
        "uvicorn_entrypoint": "sports_api.main:app" if "sports_api.main:app" in dockerfile else None,
        "default_web_concurrency": 2 if "WEB_CONCURRENCY=2" in dockerfile else None,
        "deployment_replica_count": 1 if "WNBA_DEPLOYMENT_REPLICA_COUNT=1" in dockerfile else None,
        "hosted_staging_provider": "render" if "Render" in readme else None,
        "persistent_volume_root": (
            "/var/lib/kyre-sports-api"
            if "/var/lib/kyre-sports-api" in dockerfile and "/var/lib/kyre-sports-api" in prod_env
            else None
        ),
        "production_runtime_default_off": "WNBA_PRODUCTION_RUNTIME_ENABLED=false" in prod_env,
        "persistence_requirement_defined": persistence_requirements == "psycopg[binary]>=3.2,<4",
        "persistence_requirement": persistence_requirements,
        "docker_installs_base_requirements": (
            "sports_api/requirements.txt" in dockerfile
            and "pip install --no-cache-dir -r /app/sports_api/requirements.txt" in dockerfile
        ),
        "docker_installs_persistence_requirements": (
            "requirements-persistence.txt" in dockerfile
            or "psycopg" in base_requirements.casefold()
        ),
        "production_env_declares_kyre_database_url": "KYRE_DATABASE_URL" in prod_env,
        "fastapi_startup_binds_step13_to_step15_runtime": any(
            token in main
            for token in (
                "wnba_step13c_reliability_recovery",
                "wnba_step14c_durable_restart_lease",
                "wnba_step15_release_freeze",
            )
        ),
    }


def validate_step16a_readiness_evidence(
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(evidence, Mapping):
        raise WNBAStep16AProductionActivationContractIntegrityError(
            "Step 16A evidence must be an object."
        )
    if evidence.get("data_type") != "wnba_step16a_production_activation_readiness_evidence":
        raise WNBAStep16AProductionActivationContractIntegrityError(
            "Step 16A evidence data_type drift."
        )
    parent = evidence.get("frozen_parent")
    files = evidence.get("deployment_files")
    existing = evidence.get("existing_deployment_contract")
    findings = evidence.get("readiness_findings")
    blockers = evidence.get("blocking_requirements")
    activation = evidence.get("activation_boundary")
    if not all(isinstance(x, Mapping) for x in (parent, files, existing, findings, activation)):
        raise WNBAStep16AProductionActivationContractIntegrityError(
            "Step 16A evidence object shape drift."
        )
    if (
        parent.get("step15c_certified_sha") != STEP15C_CERTIFIED_SHA
        or parent.get("step15_release_id") != STEP15_RELEASE_ID
        or parent.get("step15_release_content_sha256") != STEP15_RELEASE_CONTENT_SHA256
    ):
        raise WNBAStep16AProductionActivationContractIntegrityError(
            "Step 16A frozen Step-15 lineage drift."
        )
    if dict(files) != EXPECTED_DEPLOYMENT_BLOBS:
        raise WNBAStep16AProductionActivationContractIntegrityError(
            "Step 16A frozen deployment-file identity drift."
        )
    observed_surface = inspect_current_deployment_surface()
    expected_surface = {
        "container_runtime": existing.get("container_runtime"),
        "uvicorn_entrypoint": existing.get("uvicorn_entrypoint"),
        "default_web_concurrency": existing.get("default_web_concurrency"),
        "deployment_replica_count": existing.get("deployment_replica_count"),
        "hosted_staging_provider": existing.get("hosted_staging_provider"),
        "persistent_volume_root": existing.get("persistent_volume_root"),
        "production_runtime_default_off": existing.get("production_runtime_default_off"),
        "persistence_requirement_defined": findings.get("persistence_requirement_defined"),
        "persistence_requirement": findings.get("persistence_requirement"),
        "docker_installs_base_requirements": findings.get("docker_installs_base_requirements"),
        "docker_installs_persistence_requirements": findings.get("docker_installs_persistence_requirements"),
        "production_env_declares_kyre_database_url": findings.get("production_env_declares_kyre_database_url"),
        "fastapi_startup_binds_step13_to_step15_runtime": findings.get("fastapi_startup_binds_step13_to_step15_runtime"),
    }
    if observed_surface != expected_surface:
        raise WNBAStep16AProductionActivationContractIntegrityError(
            "Step 16A observed deployment surface drift."
        )
    if findings.get("live_step15_schema_certified") is not True:
        raise WNBAStep16AProductionActivationContractIntegrityError(
            "Step 16A lost Step-15 schema certification."
        )
    if findings.get("live_step15_transactions_certified") is not True:
        raise WNBAStep16AProductionActivationContractIntegrityError(
            "Step 16A lost Step-15 transaction certification."
        )
    if findings.get("production_activation_ready") is not False:
        raise WNBAStep16AProductionActivationContractIntegrityError(
            "Step 16A must fail closed while blockers remain."
        )
    if tuple(blockers or ()) != BLOCKING_REQUIREMENTS:
        raise WNBAStep16AProductionActivationContractIntegrityError(
            "Step 16A blocking requirement set drift."
        )
    if any(value is not False for value in activation.values()):
        raise WNBAStep16AProductionActivationContractIntegrityError(
            "Step 16A activation boundary drift."
        )
    return deepcopy(dict(evidence))


def _assert_integrity(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    source = dict(os.environ if env is None else env)
    if not step16a_production_activation_contract_enabled(source):
        raise WNBAStep16AProductionActivationContractDisabledError(
            f"Step 16A requires {STEP16A_PRODUCTION_ACTIVATION_CONTRACT_ENABLED_ENV}=true."
        )
    bad = [key for key in _FORBIDDEN_TRUE_ENV_KEYS if _truthy(source.get(key))]
    if bad:
        raise WNBAStep16AProductionActivationContractDisabledError(
            "Step 16A refuses active production/scheduler/persistence/write switches: "
            + ", ".join(bad)
        )
    false_constants = (
        DEFAULT_ENABLED,
        PRODUCTION_ACTIVATION_ALLOWED,
        PRODUCTION_CANARY_ALLOWED,
        GLOBAL_PERSISTENCE_AUTOSTART_ALLOWED,
        AUTOMATIC_RESTART_ACTIVATION_ALLOWED,
        BACKGROUND_DAEMON_ALLOWED,
        BACKGROUND_THREAD_ALLOWED,
        PUBLIC_PERSISTENCE_API_ALLOWED,
        SUPABASE_REST_WRITE_ALLOWED,
        WAGERING_ALLOWED,
        AUTHENTICATION_ALLOWED,
        COOKIES_ALLOWED,
        BASKETBALL_MODEL_MUTATION_ALLOWED,
        RANKING_MUTATION_ALLOWED,
        RUNTIME_MUTATION_ALLOWED,
        SECRETS_IN_REPOSITORY_ALLOWED,
    )
    if any(value is not False for value in false_constants):
        raise WNBAStep16AProductionActivationContractIntegrityError(
            "Step 16A safety constant drift."
        )
    true_constants = (
        READINESS_INSPECTION_ALLOWED,
        DEPLOYMENT_CONTRACT_DEFINITION_ALLOWED,
        FAIL_CLOSED_BLOCKER_CERTIFICATION_ALLOWED,
    )
    if any(value is not True for value in true_constants):
        raise WNBAStep16AProductionActivationContractIntegrityError(
            "Step 16A readiness capability drift."
        )
    return validate_step16a_readiness_evidence(load_step16a_readiness_evidence())


def build_step16a_production_activation_contract(
    *,
    env: Mapping[str, str] | None = None,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    """Build the deterministic Step-16A fail-closed readiness contract."""
    evidence = _assert_integrity(env)
    generated = generated_at_utc or datetime.now(timezone.utc).isoformat()
    result = {
        "data_type": "wnba_step16a_production_activation_readiness_contract",
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        "integration_version": INTEGRATION_VERSION,
        "contract_id": CONTRACT_ID,
        "generated_at_utc": generated,
        "season": SEASON,
        "season_type": SEASON_TYPE,
        "branch": BRANCH,
        "lineage": {
            "step15c_certified_sha": STEP15C_CERTIFIED_SHA,
            "step15_release_id": STEP15_RELEASE_ID,
            "step15_release_content_sha256": STEP15_RELEASE_CONTENT_SHA256,
            "readiness_evidence_content_sha256": EVIDENCE_CONTENT_SHA256,
        },
        "current_deployment_contract": deepcopy(evidence["existing_deployment_contract"]),
        "readiness": {
            "step15_live_schema_certified": True,
            "step15_live_transactions_certified": True,
            "production_activation_ready": False,
            "blocking_requirements": list(BLOCKING_REQUIREMENTS),
        },
        "required_before_any_future_production_canary": {
            "install_psycopg_in_production_image": True,
            "supply_kyre_database_url_via_deployment_secret_manager": True,
            "never_commit_database_secret": True,
            "bind_frozen_step13_to_step15_runtime_to_explicit_app_lifecycle": True,
            "require_durable_lease_before_scheduler_execution": True,
            "recover_valid_checkpoint_before_first_scheduler_cycle": True,
            "fail_closed_on_schema_hash_lineage_or_lease_mismatch": True,
            "preserve_step8_projection_behavior": True,
            "preserve_step9_ranking_behavior": True,
            "keep_wagering_out_of_scope": True,
        },
        "activation_contract": {
            "step16a_is_contract_only": True,
            "production_canary_allowed": False,
            "production_runtime_enabled": False,
            "scheduler_started": False,
            "global_persistence_autostart_enabled": False,
            "automatic_restart_activation_enabled": False,
            "background_worker_started": False,
            "public_persistence_api_exposed": False,
            "supabase_rest_write_path_enabled": False,
        },
        "safety_contract": deepcopy(SAFETY_CONTRACT),
        "phase_boundary": {
            "step16a_complete": True,
            "readiness_contract_defined": True,
            "current_activation_blockers_certified": True,
            "production_packaging_integration_not_started": True,
            "controlled_production_canary_not_started": True,
            "production_activation_not_started": True,
            "global_persistence_autostart_not_started": True,
        },
    }
    surface = deepcopy(result)
    surface.pop("generated_at_utc", None)
    result["contract_content_sha256"] = _canonical_hash(surface)
    _assert_integrity(env)
    return result


__all__ = [
    "BLOCKING_REQUIREMENTS",
    "BRANCH",
    "CONTRACT_ID",
    "DEFAULT_ENABLED",
    "EVIDENCE_CONTENT_SHA256",
    "EVIDENCE_PATH",
    "EXPECTED_DEPLOYMENT_BLOBS",
    "INTEGRATION_VERSION",
    "PRODUCTION_ACTIVATION_ALLOWED",
    "PRODUCTION_CANARY_ALLOWED",
    "SAFETY_CONTRACT",
    "SCHEMA_VERSION",
    "SOURCE",
    "STEP15C_CERTIFIED_SHA",
    "STEP15_RELEASE_CONTENT_SHA256",
    "STEP15_RELEASE_ID",
    "STEP16A_PRODUCTION_ACTIVATION_CONTRACT_ENABLED_ENV",
    "WNBAStep16AProductionActivationContractDisabledError",
    "WNBAStep16AProductionActivationContractIntegrityError",
    "build_step16a_production_activation_contract",
    "inspect_current_deployment_surface",
    "load_step16a_readiness_evidence",
    "step16a_production_activation_contract_enabled",
    "validate_step16a_readiness_evidence",
]
