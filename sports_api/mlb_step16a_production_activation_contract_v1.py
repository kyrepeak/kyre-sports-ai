"""MLB Step 16A — production activation readiness contract.

Step 16A is deliberately contract-only. It inspects the frozen Step-15 live
persistence release and the existing deployment surface, records the exact
blockers that must be closed before any production canary may exist, and fails
closed if a production/runtime/actionable switch is already on.

A GREEN Step 16A means the readiness gate accurately identifies the current
state. It does NOT authorize production activation, a scheduler run, a canary,
provider/sportsbook calls, or any Streamlit/API behavior change.
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

from sports_api import mlb_step15_final_live_persistence_release_freeze_v1 as step15c
from sports_api import mlb_step15b_live_adapter_transaction_smoke_v1 as step15b
from sports_api.mlb_step9_final_freeze_v1 import PROTECTED_INVARIANTS

DATA_TYPE = "mlb_step16a_production_activation_readiness_contract_v1"
SCHEMA_VERSION = 1
INTEGRATION_VERSION = "mlb_step16a_production_activation_readiness_2026_v1"
CONTRACT_ID = "mlb_step16a_production_activation_readiness_2026_regular_v1"
FINAL_CERTIFICATION_MARKER = "MLB_STEP16A_PRODUCTION_ACTIVATION_CONTRACT_GREEN"
RUNTIME_MODE = "SHADOW_ONLY"
BRANCH = "mlb-step16a-production-activation-contract"

STEP16A_BASE_MAIN_SHA = "a67d415e5e1d8614d632fd34cfa09d551792a71f"
STEP15C_CERTIFIED_MAIN_SHA = STEP16A_BASE_MAIN_SHA
STEP15C_SOURCE_BLOB_SHA = "2ba73d80704054a5de8da4ea6daab8b9537bc7e0"
STEP15_RELEASE_ID = "mlb_step15_live_supabase_persistence_2026_regular_season_frozen_v1"
STEP15_RELEASE_MANIFEST_SHA256 = (
    "d5c184988de8db66af6ef2c4e158dd8016a3403f968d42296f41dfa69bf83ada"
)
STEP15C_FINAL_MARKER = "MLB_STEP15C_FINAL_LIVE_PERSISTENCE_FREEZE_GREEN"

EVIDENCE_PATH = (
    "sports_api/certification/"
    "mlb_step16a_production_activation_readiness_evidence.json"
)
EVIDENCE_CONTENT_SHA256 = (
    "faf001523cbd4185633aacfa053d78b886e659c22c9bc584c9d40b167c8d3964"
)

DOCKERFILE_PATH = "sports_api/Dockerfile"
README_PATH = "sports_api/README.md"
MAIN_PATH = "sports_api/main.py"
PRODUCTION_ENV_PATH = "sports_api/production.env.example"
BASE_REQUIREMENTS_PATH = "sports_api/requirements.txt"
PERSISTENCE_REQUIREMENTS_PATH = (
    "sports_api/requirements-mlb-step14b-persistence.txt"
)

EXPECTED_DEPLOYMENT_BLOBS = {
    DOCKERFILE_PATH: "e06eed5c3b9d65c238e47b3fd2fde1529a785fdf",
    README_PATH: "4f93bb2c1890a1c65ff7b6c7cc21bb857a39f5b5",
    MAIN_PATH: "4816cc7eff7ae140c503f6fa7c1e97f5f0074192",
    PRODUCTION_ENV_PATH: "6962aa11e75906691869d2ed04d2bf50822821c8",
    PERSISTENCE_REQUIREMENTS_PATH: "46331822d0a55f5a4983d289c73a45ea9745ca89",
    BASE_REQUIREMENTS_PATH: "84e666d78549778a84f216e80d2bb979c1f6160a",
}

BLOCKING_REQUIREMENTS = (
    "docker_install_mlb_persistence_requirements",
    "deployment_secret_manager_supply_kyre_database_url",
    "declare_mlb_activation_switches_default_off",
    "bind_frozen_step13_to_step15_runtime_into_explicit_application_lifecycle",
)

STEP16A_PRODUCTION_ACTIVATION_CONTRACT_ENABLED_ENV = (
    "MLB_STEP16A_PRODUCTION_ACTIVATION_CONTRACT_ENABLED"
)

DEFAULT_ENABLED = False
PRODUCTION_ACTIVATION_ALLOWED = False
PRODUCTION_CANARY_ALLOWED = False
PRODUCTION_SCHEDULER_ALLOWED = False
GLOBAL_PERSISTENCE_AUTOSTART_ALLOWED = False
AUTOMATIC_RESTART_ACTIVATION_ALLOWED = False
BACKGROUND_WORKER_ALLOWED = False
PUBLIC_PERSISTENCE_API_ALLOWED = False
SUPABASE_REST_WRITE_ALLOWED = False
ACTIONABLE_OUTPUT_ALLOWED = False
WAGERING_ALLOWED = False
PROVIDER_NETWORK_CALLS_ALLOWED = False
SPORTSBOOK_NETWORK_CALLS_ALLOWED = False
RUNTIME_MUTATION_ALLOWED = False
SECRETS_IN_REPOSITORY_ALLOWED = False

READINESS_INSPECTION_ALLOWED = True
DEPLOYMENT_CONTRACT_DEFINITION_ALLOWED = True
FAIL_CLOSED_BLOCKER_CERTIFICATION_ALLOWED = True

SAFETY_CONTRACT = {
    "default_enablement": False,
    "production_runtime": False,
    "production_scheduler": False,
    "production_canary": False,
    "production_activation": False,
    "global_persistence_autostart": False,
    "automatic_restart_activation": False,
    "background_worker": False,
    "public_persistence_api": False,
    "supabase_rest_write": False,
    "actionable_output": False,
    "wager_action": False,
    "provider_network_calls": False,
    "sportsbook_network_calls": False,
    "secrets_in_repository": False,
    "runtime_mutation": False,
    "mlb_model_change": False,
    "projection_change": False,
    "probability_change": False,
    "simulation_change": False,
    "ranking_change": False,
    "grading_change": False,
    "wnba_change": False,
}

_FORBIDDEN_TRUE_ENV_KEYS = (
    "MLB_PRODUCTION_RUNTIME_ENABLED",
    "MLB_PRODUCTION_SCHEDULER_ENABLED",
    "MLB_ACTIONABLE_OUTPUT_ENABLED",
    "MLB_WAGERING_ENABLED",
    "MLB_SUPABASE_REST_WRITE_ENABLED",
)

_REQUIRED_PARENT_TRUE_ENV_KEYS = (
    step15c.STEP15C_FINAL_LIVE_PERSISTENCE_FREEZE_ENABLED_ENV,
    step15b.STEP15B_LIVE_ADAPTER_SMOKE_ENABLED_ENV,
)


class MLBStep16AProductionActivationContractDisabledError(RuntimeError):
    """Raised unless the Step16A readiness gate is explicitly isolated."""


class MLBStep16AProductionActivationContractIntegrityError(RuntimeError):
    """Raised when frozen readiness evidence or safety boundaries drift."""


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() not in {
        "", "0", "false", "no", "off", "disabled"
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


def step16a_production_activation_contract_enabled(
    env: Mapping[str, str] | None = None,
) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(STEP16A_PRODUCTION_ACTIVATION_CONTRACT_ENABLED_ENV))


def _read(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise MLBStep16AProductionActivationContractIntegrityError(
            f"Step 16A cannot read required deployment file: {path}"
        ) from exc


def _evidence_hash_surface(evidence: Mapping[str, Any]) -> dict[str, Any]:
    result = deepcopy(dict(evidence))
    result.pop("observed_at_utc", None)
    result.pop("evidence_content_sha256", None)
    return result


def load_step16a_readiness_evidence(
    path: str = EVIDENCE_PATH,
) -> dict[str, Any]:
    try:
        evidence = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MLBStep16AProductionActivationContractIntegrityError(
            "Step 16A cannot load readiness evidence"
        ) from exc
    if not isinstance(evidence, dict):
        raise MLBStep16AProductionActivationContractIntegrityError(
            "Step 16A readiness evidence must be an object"
        )
    expected = _hash(_evidence_hash_surface(evidence))
    observed = str(evidence.get("evidence_content_sha256") or "").lower()
    if expected != EVIDENCE_CONTENT_SHA256 or observed != expected:
        raise MLBStep16AProductionActivationContractIntegrityError(
            "Step 16A readiness evidence content hash drift"
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
        "uvicorn_entrypoint": (
            "sports_api.main:app" if "sports_api.main:app" in dockerfile else None
        ),
        "default_web_concurrency": 2 if "WEB_CONCURRENCY=2" in dockerfile else None,
        "deployment_replica_count": (
            1 if "WNBA_DEPLOYMENT_REPLICA_COUNT=1" in dockerfile else None
        ),
        "hosted_staging_provider": "render" if "Render" in readme else None,
        "persistent_volume_root": (
            "/var/lib/kyre-sports-api"
            if "/var/lib/kyre-sports-api" in dockerfile
            and "/var/lib/kyre-sports-api" in prod_env
            else None
        ),
        "mlb_production_runtime_default_off": (
            "MLB_PRODUCTION_RUNTIME_ENABLED=false" in prod_env
        ),
        "mlb_production_scheduler_default_off": (
            "MLB_PRODUCTION_SCHEDULER_ENABLED=false" in prod_env
        ),
        "persistence_requirement_defined": (
            persistence_requirements == "psycopg[binary]>=3.2,<4"
        ),
        "persistence_requirement": persistence_requirements,
        "docker_installs_base_requirements": (
            "sports_api/requirements.txt" in dockerfile
            and "pip install --no-cache-dir -r /app/sports_api/requirements.txt"
            in dockerfile
        ),
        "docker_installs_mlb_persistence_requirements": (
            "requirements-mlb-step14b-persistence.txt" in dockerfile
            or "psycopg" in base_requirements.casefold()
        ),
        "production_env_declares_kyre_database_url": "KYRE_DATABASE_URL" in prod_env,
        "fastapi_startup_binds_step13_to_step15_runtime": all(
            token in main
            for token in (
                "mlb_step13c_reliability_recovery_v1",
                "mlb_step14c_durable_restart_lease_v1",
                "mlb_step15_final_live_persistence_release_freeze_v1",
            )
        ),
    }


def validate_step16a_readiness_evidence(
    evidence: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(evidence, Mapping):
        raise MLBStep16AProductionActivationContractIntegrityError(
            "Step 16A evidence must be an object"
        )
    if evidence.get("data_type") != (
        "mlb_step16a_production_activation_readiness_evidence"
    ):
        raise MLBStep16AProductionActivationContractIntegrityError(
            "Step 16A evidence data_type drift"
        )

    parent = evidence.get("frozen_parent")
    files = evidence.get("deployment_files")
    existing = evidence.get("existing_deployment_contract")
    findings = evidence.get("readiness_findings")
    blockers = evidence.get("blocking_requirements")
    activation = evidence.get("activation_boundary")
    if not all(
        isinstance(value, Mapping)
        for value in (parent, files, existing, findings, activation)
    ):
        raise MLBStep16AProductionActivationContractIntegrityError(
            "Step 16A evidence object shape drift"
        )

    expected_parent = {
        "step15_release_id": STEP15_RELEASE_ID,
        "step15_release_manifest_sha256": STEP15_RELEASE_MANIFEST_SHA256,
        "step15c_certified_main_sha": STEP15C_CERTIFIED_MAIN_SHA,
        "step15c_final_marker": STEP15C_FINAL_MARKER,
        "step15c_source_blob_sha": STEP15C_SOURCE_BLOB_SHA,
    }
    if dict(parent) != expected_parent:
        raise MLBStep16AProductionActivationContractIntegrityError(
            "Step 16A frozen Step-15 lineage drift"
        )
    if dict(files) != EXPECTED_DEPLOYMENT_BLOBS:
        raise MLBStep16AProductionActivationContractIntegrityError(
            "Step 16A frozen deployment-file identity drift"
        )

    observed_surface = inspect_current_deployment_surface()
    expected_surface = {
        "container_runtime": existing.get("container_runtime"),
        "uvicorn_entrypoint": existing.get("uvicorn_entrypoint"),
        "default_web_concurrency": existing.get("default_web_concurrency"),
        "deployment_replica_count": existing.get("deployment_replica_count"),
        "hosted_staging_provider": existing.get("hosted_staging_provider"),
        "persistent_volume_root": existing.get("persistent_volume_root"),
        "mlb_production_runtime_default_off": findings.get(
            "mlb_production_runtime_default_off"
        ),
        "mlb_production_scheduler_default_off": findings.get(
            "mlb_production_scheduler_default_off"
        ),
        "persistence_requirement_defined": findings.get(
            "persistence_requirement_defined"
        ),
        "persistence_requirement": findings.get("persistence_requirement"),
        "docker_installs_base_requirements": findings.get(
            "docker_installs_base_requirements"
        ),
        "docker_installs_mlb_persistence_requirements": findings.get(
            "docker_installs_mlb_persistence_requirements"
        ),
        "production_env_declares_kyre_database_url": findings.get(
            "production_env_declares_kyre_database_url"
        ),
        "fastapi_startup_binds_step13_to_step15_runtime": findings.get(
            "fastapi_startup_binds_step13_to_step15_runtime"
        ),
    }
    if observed_surface != expected_surface:
        raise MLBStep16AProductionActivationContractIntegrityError(
            "Step 16A observed deployment surface drift"
        )

    for key in (
        "live_step15_schema_certified",
        "live_step15_transactions_certified",
        "live_step15_release_frozen",
        "persistence_requirement_defined",
        "docker_installs_base_requirements",
    ):
        if findings.get(key) is not True:
            raise MLBStep16AProductionActivationContractIntegrityError(
                f"Step 16A required readiness fact drift: {key}"
            )
    for key in (
        "docker_installs_mlb_persistence_requirements",
        "production_env_declares_kyre_database_url",
        "mlb_production_runtime_default_off",
        "mlb_production_scheduler_default_off",
        "fastapi_startup_binds_step13_to_step15_runtime",
        "production_activation_ready",
    ):
        if findings.get(key) is not False:
            raise MLBStep16AProductionActivationContractIntegrityError(
                f"Step 16A fail-closed blocker drift: {key}"
            )

    if tuple(blockers or ()) != BLOCKING_REQUIREMENTS:
        raise MLBStep16AProductionActivationContractIntegrityError(
            "Step 16A blocking requirement set drift"
        )
    if not activation or any(value is not False for value in activation.values()):
        raise MLBStep16AProductionActivationContractIntegrityError(
            "Step 16A activation boundary drift"
        )
    return deepcopy(dict(evidence))


def _assert_integrity(
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    source = dict(os.environ if env is None else env)
    if not step16a_production_activation_contract_enabled(source):
        raise MLBStep16AProductionActivationContractDisabledError(
            f"Step 16A requires "
            f"{STEP16A_PRODUCTION_ACTIVATION_CONTRACT_ENABLED_ENV}=true"
        )
    bad = [key for key in _FORBIDDEN_TRUE_ENV_KEYS if _truthy(source.get(key))]
    if bad:
        raise MLBStep16AProductionActivationContractDisabledError(
            "Step 16A refuses active production/actionable switches: "
            + ", ".join(bad)
        )
    missing = [
        key for key in _REQUIRED_PARENT_TRUE_ENV_KEYS if not _truthy(source.get(key))
    ]
    if missing:
        raise MLBStep16AProductionActivationContractDisabledError(
            "Step 16A requires frozen Step-15 parent gates: " + ", ".join(missing)
        )

    if step15c.FINAL_CERTIFICATION_MARKER != STEP15C_FINAL_MARKER:
        raise MLBStep16AProductionActivationContractIntegrityError(
            "Step 16A Step-15C marker drift"
        )
    if step15c.RELEASE_ID != STEP15_RELEASE_ID:
        raise MLBStep16AProductionActivationContractIntegrityError(
            "Step 16A Step-15 release identity drift"
        )
    parent_manifest = step15c.final_live_persistence_release_manifest(
        env=source,
        generated_at_utc="2026-09-01T21:01:59.087801+00:00",
    )
    if parent_manifest.get("release_manifest_sha256") != (
        STEP15_RELEASE_MANIFEST_SHA256
    ):
        raise MLBStep16AProductionActivationContractIntegrityError(
            "Step 16A frozen Step-15 release manifest hash drift"
        )
    if parent_manifest.get("phase_boundary", {}).get(
        "step15_complete_and_frozen"
    ) is not True:
        raise MLBStep16AProductionActivationContractIntegrityError(
            "Step 16A requires frozen completed Step 15"
        )

    false_constants = (
        DEFAULT_ENABLED,
        PRODUCTION_ACTIVATION_ALLOWED,
        PRODUCTION_CANARY_ALLOWED,
        PRODUCTION_SCHEDULER_ALLOWED,
        GLOBAL_PERSISTENCE_AUTOSTART_ALLOWED,
        AUTOMATIC_RESTART_ACTIVATION_ALLOWED,
        BACKGROUND_WORKER_ALLOWED,
        PUBLIC_PERSISTENCE_API_ALLOWED,
        SUPABASE_REST_WRITE_ALLOWED,
        ACTIONABLE_OUTPUT_ALLOWED,
        WAGERING_ALLOWED,
        PROVIDER_NETWORK_CALLS_ALLOWED,
        SPORTSBOOK_NETWORK_CALLS_ALLOWED,
        RUNTIME_MUTATION_ALLOWED,
        SECRETS_IN_REPOSITORY_ALLOWED,
    )
    if any(value is not False for value in false_constants):
        raise MLBStep16AProductionActivationContractIntegrityError(
            "Step 16A safety constant drift"
        )
    true_constants = (
        READINESS_INSPECTION_ALLOWED,
        DEPLOYMENT_CONTRACT_DEFINITION_ALLOWED,
        FAIL_CLOSED_BLOCKER_CERTIFICATION_ALLOWED,
    )
    if any(value is not True for value in true_constants):
        raise MLBStep16AProductionActivationContractIntegrityError(
            "Step 16A readiness capability drift"
        )
    if any(value is not False for value in SAFETY_CONTRACT.values()):
        raise MLBStep16AProductionActivationContractIntegrityError(
            "Step 16A safety contract drift"
        )
    for key, value in PROTECTED_INVARIANTS.items():
        if value is not False:
            raise MLBStep16AProductionActivationContractIntegrityError(
                f"Step 16A protected invariant drift: {key}"
            )
    return validate_step16a_readiness_evidence(load_step16a_readiness_evidence())


def build_step16a_production_activation_contract(
    *,
    env: Mapping[str, str] | None = None,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    evidence = _assert_integrity(env)
    generated = generated_at_utc or datetime.now(timezone.utc).isoformat()
    result: dict[str, Any] = {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "integration_version": INTEGRATION_VERSION,
        "contract_id": CONTRACT_ID,
        "final_certification_marker": FINAL_CERTIFICATION_MARKER,
        "runtime_mode": RUNTIME_MODE,
        "branch": BRANCH,
        "generated_at_utc": generated,
        "step16a_base_main_sha": STEP16A_BASE_MAIN_SHA,
        "lineage": {
            "step15c_certified_main_sha": STEP15C_CERTIFIED_MAIN_SHA,
            "step15c_source_blob_sha": STEP15C_SOURCE_BLOB_SHA,
            "step15_release_id": STEP15_RELEASE_ID,
            "step15_release_manifest_sha256": STEP15_RELEASE_MANIFEST_SHA256,
            "step15c_final_marker": STEP15C_FINAL_MARKER,
            "readiness_evidence_content_sha256": EVIDENCE_CONTENT_SHA256,
        },
        "current_deployment_contract": deepcopy(
            evidence["existing_deployment_contract"]
        ),
        "readiness": {
            "step15_live_schema_certified": True,
            "step15_live_transactions_certified": True,
            "step15_release_frozen": True,
            "production_activation_ready": False,
            "blocking_requirements": list(BLOCKING_REQUIREMENTS),
            "blocker_count": len(BLOCKING_REQUIREMENTS),
        },
        "required_before_any_future_production_canary": {
            "install_psycopg_in_production_image": True,
            "supply_kyre_database_url_via_deployment_secret_manager": True,
            "never_commit_database_secret": True,
            "declare_mlb_production_runtime_default_off": True,
            "declare_mlb_production_scheduler_default_off": True,
            "bind_frozen_step13_to_step15_runtime_to_explicit_app_lifecycle": True,
            "require_durable_lease_before_scheduler_execution": True,
            "recover_valid_checkpoint_before_first_scheduler_cycle": True,
            "fail_closed_on_schema_hash_lineage_or_lease_mismatch": True,
            "preserve_projection_probability_simulation_math": True,
            "preserve_ranking_and_grading_behavior": True,
            "keep_actionable_output_off_until_later_activation": True,
            "keep_wagering_out_of_scope": True,
        },
        "activation_contract": {
            "step16a_is_contract_only": True,
            "production_canary_allowed": False,
            "production_runtime_enabled": False,
            "production_scheduler_started": False,
            "global_persistence_autostart_enabled": False,
            "automatic_restart_activation_enabled": False,
            "background_worker_started": False,
            "public_persistence_api_exposed": False,
            "supabase_rest_write_path_enabled": False,
            "actionable_output_enabled": False,
            "provider_calls": 0,
            "sportsbook_calls": 0,
            "runtime_cycle_executed": False,
        },
        "safety_contract": deepcopy(SAFETY_CONTRACT),
        "phase_boundary": {
            "step15_complete_and_frozen": True,
            "step16a_complete": True,
            "readiness_contract_defined": True,
            "current_activation_blockers_certified": True,
            "production_packaging_integration_not_started": True,
            "controlled_production_canary_not_started": True,
            "production_activation_not_started": True,
            "global_persistence_autostart_not_started": True,
            "step16b_production_packaging_lifecycle_required": True,
        },
        **PROTECTED_INVARIANTS,
    }
    surface = deepcopy(result)
    surface.pop("generated_at_utc", None)
    result["contract_content_sha256"] = _hash(surface)
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
    "FINAL_CERTIFICATION_MARKER",
    "INTEGRATION_VERSION",
    "MLBStep16AProductionActivationContractDisabledError",
    "MLBStep16AProductionActivationContractIntegrityError",
    "PRODUCTION_ACTIVATION_ALLOWED",
    "PRODUCTION_CANARY_ALLOWED",
    "SAFETY_CONTRACT",
    "SCHEMA_VERSION",
    "STEP15C_CERTIFIED_MAIN_SHA",
    "STEP15C_SOURCE_BLOB_SHA",
    "STEP15_RELEASE_ID",
    "STEP15_RELEASE_MANIFEST_SHA256",
    "STEP16A_BASE_MAIN_SHA",
    "STEP16A_PRODUCTION_ACTIVATION_CONTRACT_ENABLED_ENV",
    "build_step16a_production_activation_contract",
    "inspect_current_deployment_surface",
    "load_step16a_readiness_evidence",
    "step16a_production_activation_contract_enabled",
    "validate_step16a_readiness_evidence",
]
