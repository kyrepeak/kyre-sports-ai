"""MLB Step 16B — production packaging + lifecycle certification contract.

This module content-addresses the Step 16B deployment changes that close the
four blockers certified by Step 16A. It does not authorize or execute a live
canary. Production remains fail-closed until Step 16C.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping

from sports_api import mlb_step16b_production_lifecycle_v1 as lifecycle
from sports_api import mlb_step13a_bounded_scheduler_v1 as step13a
from sports_api import mlb_step13b_runtime_supervisor_v1 as step13b
from sports_api import mlb_step13c_reliability_recovery_v1 as step13c
from sports_api import mlb_step14c_durable_restart_lease_v1 as step14c
from sports_api import mlb_step16a_production_activation_contract_v1 as step16a
from sports_api.mlb_step9_final_freeze_v1 import PROTECTED_INVARIANTS

DATA_TYPE = "mlb_step16b_production_packaging_lifecycle_contract_v1"
SCHEMA_VERSION = 1
INTEGRATION_VERSION = "mlb_step16b_production_packaging_lifecycle_contract_2026_v1"
CONTRACT_ID = "mlb_step16b_production_packaging_lifecycle_2026_regular_v1"
FINAL_CERTIFICATION_MARKER = "MLB_STEP16B_PRODUCTION_PACKAGING_LIFECYCLE_GREEN"
RUNTIME_MODE = "SHADOW_ONLY"
BRANCH = "mlb-step16b-production-packaging-lifecycle"

STEP16B_BASE_MAIN_SHA = "9d4685760bc6b2d7c0391bcb092583a127283d67"
STEP16A_CERTIFIED_MAIN_SHA = "c5ad6047224aaf014cec13f5efa6e5cd650da939"
STEP16A_SOURCE_BLOB_SHA = "a8ce0bfef0918fd471c383964ccbf0f99f13611f"
STEP16A_CONTRACT_ID = "mlb_step16a_production_activation_readiness_2026_regular_v1"
STEP16A_CONTRACT_CONTENT_SHA256 = "fc5d15c1d38367c76d4fb7dc1ed611dea001d2b48459af3afc297e432c686a1d"
STEP15C_CERTIFIED_MAIN_SHA = "a67d415e5e1d8614d632fd34cfa09d551792a71f"
STEP15_RELEASE_ID = "mlb_step15_live_supabase_persistence_2026_regular_season_frozen_v1"
STEP15_RELEASE_MANIFEST_SHA256 = "d5c184988de8db66af6ef2c4e158dd8016a3403f968d42296f41dfa69bf83ada"

EVIDENCE_PATH = "sports_api/certification/mlb_step16b_production_packaging_lifecycle_evidence.json"
EVIDENCE_CONTENT_SHA256 = "12465ef207569c39a95bc05ae9e68ac5ff5533b753cc928797712341671ae253"
DOCKERFILE_PATH = "sports_api/Dockerfile"
MAIN_PATH = "sports_api/main.py"
ENV_EXAMPLE_PATH = "sports_api/production.env.example"
BASE_REQUIREMENTS_PATH = "sports_api/requirements.txt"
PERSISTENCE_REQUIREMENTS_PATH = "sports_api/requirements-mlb-step14b-persistence.txt"
LIFECYCLE_PATH = "sports_api/mlb_step16b_production_lifecycle_v1.py"

EXPECTED_BLOB_SHAS = {
    DOCKERFILE_PATH: "34a542b0a32456de58b81fd711fef215e618469f",
    MAIN_PATH: "839a7cae1b69b456260031803856df1f7f9661ec",
    ENV_EXAMPLE_PATH: "25d7a2196f5502e6aa3e25c6885c76a05c887f3f",
    BASE_REQUIREMENTS_PATH: "84e666d78549778a84f216e80d2bb979c1f6160a",
    PERSISTENCE_REQUIREMENTS_PATH: "46331822d0a55f5a4983d289c73a45ea9745ca89",
    LIFECYCLE_PATH: "86e5a0f11c12e34bdbe213623026b2f368484985",
}

PRODUCTION_ACTIVATION_READY = False
STEP16C_LIVE_CANARY_REQUIRED = True
LIVE_CANARY_EXECUTED = False
PRODUCTION_RUNTIME_ENABLED = False
PRODUCTION_SCHEDULER_ENABLED = False
GLOBAL_PERSISTENCE_AUTOSTART_ENABLED = False
AUTOMATIC_RESTART_ACTIVATION_ENABLED = False
BACKGROUND_WORKER_ENABLED = False
PUBLIC_PERSISTENCE_API_ENABLED = False
SUPABASE_REST_WRITE_ENABLED = False
ACTIONABLE_OUTPUT_ENABLED = False
WAGERING_ENABLED = False
DATABASE_CONNECTION_EXECUTED = False
RUNTIME_EXECUTED = False
PROVIDER_CALLS_EXECUTED = False
SPORTSBOOK_CALLS_EXECUTED = False

SAFETY_CONTRACT = {
    "production_activation_ready": False,
    "live_canary_executed": False,
    "production_runtime": False,
    "production_scheduler": False,
    "global_persistence_autostart": False,
    "automatic_restart_activation": False,
    "database_connection_executed": False,
    "runtime_executed": False,
    "background_worker": False,
    "background_thread": False,
    "background_task": False,
    "public_persistence_api": False,
    "supabase_rest_write": False,
    "actionable_output": False,
    "wager_action": False,
    "provider_network_calls": False,
    "sportsbook_network_calls": False,
    "secret_value_committed": False,
    "mlb_model_change": False,
    "projection_change": False,
    "probability_change": False,
    "simulation_change": False,
    "ranking_change": False,
    "grading_change": False,
    "wnba_change": False,
}


class MLBStep16BContractIntegrityError(RuntimeError):
    """Raised when Step 16B evidence or deployment packaging drifts."""


def _canonical_hash(value: Any) -> str:
    raw = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False, default=str,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _git_blob_sha_bytes(raw: bytes) -> str:
    return hashlib.sha1(f"blob {len(raw)}\0".encode("ascii") + raw).hexdigest()


def git_blob_sha(path: str) -> str:
    try:
        return _git_blob_sha_bytes(Path(path).read_bytes())
    except OSError as exc:
        raise MLBStep16BContractIntegrityError(
            f"Step 16B cannot read required deployment file: {path}"
        ) from exc


def _evidence_hash_surface(evidence: Mapping[str, Any]) -> dict[str, Any]:
    surface = deepcopy(dict(evidence))
    surface.pop("observed_at_utc", None)
    surface.pop("evidence_content_sha256", None)
    return surface


def load_step16b_evidence(path: str = EVIDENCE_PATH) -> dict[str, Any]:
    try:
        evidence = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MLBStep16BContractIntegrityError(
            "Step 16B cannot load packaging/lifecycle evidence"
        ) from exc
    if not isinstance(evidence, dict):
        raise MLBStep16BContractIntegrityError("Step 16B evidence must be an object")
    actual = _canonical_hash(_evidence_hash_surface(evidence))
    if evidence.get("evidence_content_sha256") != actual or actual != EVIDENCE_CONTENT_SHA256:
        raise MLBStep16BContractIntegrityError("Step 16B evidence content hash drift")
    return evidence


def _noncomment_assignment_exists(text: str, key: str) -> bool:
    pattern = re.compile(rf"^\s*{re.escape(key)}\s*=", re.MULTILINE)
    for match in pattern.finditer(text):
        line_start = text.rfind("\n", 0, match.start()) + 1
        prefix = text[line_start:match.start()].lstrip()
        if not prefix.startswith("#"):
            return True
    return False


def validate_step16b_packaging_files() -> dict[str, str]:
    observed = {path: git_blob_sha(path) for path in EXPECTED_BLOB_SHAS}
    if observed != EXPECTED_BLOB_SHAS:
        raise MLBStep16BContractIntegrityError("Step 16B deployment file blob drift")

    docker = Path(DOCKERFILE_PATH).read_text(encoding="utf-8")
    env_example = Path(ENV_EXAMPLE_PATH).read_text(encoding="utf-8")
    main = Path(MAIN_PATH).read_text(encoding="utf-8")
    persistence = Path(PERSISTENCE_REQUIREMENTS_PATH).read_text(encoding="utf-8").strip()

    required_docker = (
        "COPY sports_api/requirements-mlb-step14b-persistence.txt /app/sports_api/requirements-mlb-step14b-persistence.txt",
        "python -m pip install --no-cache-dir -r /app/sports_api/requirements-mlb-step14b-persistence.txt",
    )
    if any(fragment not in docker for fragment in required_docker):
        raise MLBStep16BContractIntegrityError("Step 16B Docker persistence packaging drift")
    if persistence != "psycopg[binary]>=3.2,<4":
        raise MLBStep16BContractIntegrityError("Step 16B psycopg requirement drift")

    if "Required secret-manager key: KYRE_DATABASE_URL" not in env_example:
        raise MLBStep16BContractIntegrityError("Step 16B database secret-manager contract missing")
    if _noncomment_assignment_exists(env_example, "KYRE_DATABASE_URL"):
        raise MLBStep16BContractIntegrityError("Step 16B refuses a committed KYRE_DATABASE_URL value")
    required_false = (
        "MLB_PRODUCTION_RUNTIME_ENABLED=false",
        "MLB_PRODUCTION_SCHEDULER_ENABLED=false",
        "MLB_ACTIONABLE_OUTPUT_ENABLED=false",
        "MLB_WAGERING_ENABLED=false",
        "MLB_SUPABASE_REST_WRITE_ENABLED=false",
        "MLB_STEP16B_DURABLE_LIFECYCLE_ENABLED=false",
    )
    if any(item not in env_example for item in required_false):
        raise MLBStep16BContractIntegrityError("Step 16B default-OFF deployment switches drift")

    if "from sports_api.mlb_step16b_production_lifecycle_v1 import step16b_lifespan" not in main:
        raise MLBStep16BContractIntegrityError("Step 16B main.py lifecycle import drift")
    if "lifespan=step16b_lifespan" not in main:
        raise MLBStep16BContractIntegrityError("Step 16B FastAPI lifespan binding drift")
    return observed


def validate_step16b_evidence(evidence: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(evidence, Mapping):
        raise MLBStep16BContractIntegrityError("Step 16B evidence must be an object")
    if evidence.get("data_type") != "mlb_step16b_production_packaging_lifecycle_evidence_v1":
        raise MLBStep16BContractIntegrityError("Step 16B evidence data_type drift")
    parent = evidence.get("frozen_parent")
    files = evidence.get("deployment_files")
    blockers = evidence.get("blocker_resolution")
    lc = evidence.get("lifecycle_contract")
    activation = evidence.get("activation_boundary")
    if not all(isinstance(x, Mapping) for x in (parent, files, blockers, lc, activation)):
        raise MLBStep16BContractIntegrityError("Step 16B evidence object shape drift")

    expected_parent = {
        "step16a_certified_main_sha": STEP16A_CERTIFIED_MAIN_SHA,
        "step16a_source_blob_sha": STEP16A_SOURCE_BLOB_SHA,
        "step16a_contract_id": STEP16A_CONTRACT_ID,
        "step16a_contract_content_sha256": STEP16A_CONTRACT_CONTENT_SHA256,
        "step15c_certified_main_sha": STEP15C_CERTIFIED_MAIN_SHA,
        "step15_release_id": STEP15_RELEASE_ID,
        "step15_release_manifest_sha256": STEP15_RELEASE_MANIFEST_SHA256,
    }
    if dict(parent) != expected_parent:
        raise MLBStep16BContractIntegrityError("Step 16B frozen parent lineage drift")
    if dict(files) != EXPECTED_BLOB_SHAS:
        raise MLBStep16BContractIntegrityError("Step 16B deployment file identity drift")

    true_blockers = (
        "all_step16a_packaging_lifecycle_blockers_closed",
        "docker_installs_mlb_persistence_requirements",
        "deployment_secret_manager_contract_declares_kyre_database_url",
        "mlb_activation_switches_declared_default_off",
        "fastapi_lifespan_binds_frozen_step13_step14_runtime",
    )
    if any(blockers.get(key) is not True for key in true_blockers):
        raise MLBStep16BContractIntegrityError("Step 16B blocker resolution drift")
    if blockers.get("kyre_database_url_value_committed") is not False:
        raise MLBStep16BContractIntegrityError("Step 16B secret-value boundary drift")

    true_lifecycle = (
        "explicit_gate_required", "psycopg3_packaged",
        "database_secret_required_only_when_enabled",
        "runtime_binding_bound_only_when_enabled", "frozen_step13_controls_bound",
        "frozen_step14c_persistence_bound", "step16c_live_canary_still_required",
    )
    if any(lc.get(key) is not True for key in true_lifecycle):
        raise MLBStep16BContractIntegrityError("Step 16B lifecycle capability drift")
    false_lifecycle = (
        "default_enabled", "database_connection_during_lifespan",
        "runtime_executed_during_lifespan", "background_worker_started",
        "background_thread_started", "background_task_started",
    )
    if any(lc.get(key) is not False for key in false_lifecycle):
        raise MLBStep16BContractIntegrityError("Step 16B lifecycle safety drift")
    if not activation or any(value is not False for value in activation.values()):
        raise MLBStep16BContractIntegrityError("Step 16B activation boundary drift")
    return deepcopy(dict(evidence))


def assert_step16b_integrity() -> dict[str, Any]:
    if step16a.FINAL_CERTIFICATION_MARKER != "MLB_STEP16A_PRODUCTION_ACTIVATION_CONTRACT_GREEN":
        raise MLBStep16BContractIntegrityError("Step 16A certification marker drift")
    if lifecycle.DEFAULT_ENABLED is not False:
        raise MLBStep16BContractIntegrityError("Step 16B lifecycle default-enable drift")
    if lifecycle.PRODUCTION_ACTIVATION_ALLOWED is not False or lifecycle.PRODUCTION_CANARY_ALLOWED is not False:
        raise MLBStep16BContractIntegrityError("Step 16B production safety drift")
    if lifecycle.DATABASE_CONNECTION_DURING_LIFESPAN_ALLOWED is not False:
        raise MLBStep16BContractIntegrityError("Step 16B lifespan DB connection drift")
    if lifecycle.get_step16b_runtime_binding({}) is not None:
        raise MLBStep16BContractIntegrityError("Step 16B default-off runtime binding drift")
    expected_modules = {
        "scheduler_tick": step13a.__name__,
        "runtime_supervision": step13b.__name__,
        "recovery_decision": step13c.__name__,
        "load_restart_context": step14c.__name__,
        "restart_inputs": step14c.__name__,
        "persist_checkpoint": step14c.__name__,
        "renew_lease": step14c.__name__,
        "release_lease": step14c.__name__,
    }
    binding = lifecycle._runtime_binding()
    if {name: fn.__module__ for name, fn in binding.items()} != expected_modules:
        raise MLBStep16BContractIntegrityError("Step 16B frozen runtime binding identity drift")
    if any(value is not False for value in SAFETY_CONTRACT.values()):
        raise MLBStep16BContractIntegrityError("Step 16B safety contract drift")
    if any(value is not False for value in PROTECTED_INVARIANTS.values()):
        raise MLBStep16BContractIntegrityError("Step 16B protected invariant drift")
    validate_step16b_packaging_files()
    return validate_step16b_evidence(load_step16b_evidence())


def build_step16b_contract_manifest(*, generated_at_utc: str | None = None) -> dict[str, Any]:
    evidence = assert_step16b_integrity()
    generated = generated_at_utc or datetime.now(timezone.utc).isoformat()
    result = {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "integration_version": INTEGRATION_VERSION,
        "contract_id": CONTRACT_ID,
        "branch": BRANCH,
        "runtime_mode": RUNTIME_MODE,
        "generated_at_utc": generated,
        "lineage": {
            "step16b_base_main_sha": STEP16B_BASE_MAIN_SHA,
            "step16a_certified_main_sha": STEP16A_CERTIFIED_MAIN_SHA,
            "step16a_source_blob_sha": STEP16A_SOURCE_BLOB_SHA,
            "step16a_contract_id": STEP16A_CONTRACT_ID,
            "step16a_contract_content_sha256": STEP16A_CONTRACT_CONTENT_SHA256,
            "step15c_certified_main_sha": STEP15C_CERTIFIED_MAIN_SHA,
            "step15_release_id": STEP15_RELEASE_ID,
            "step15_release_manifest_sha256": STEP15_RELEASE_MANIFEST_SHA256,
            "step16b_evidence_content_sha256": EVIDENCE_CONTENT_SHA256,
        },
        "blocker_resolution": deepcopy(dict(evidence["blocker_resolution"])),
        "packaging_contract": {
            "psycopg3_in_container": True,
            "base_requirements_preserved": True,
            "mlb_persistence_requirements_preserved": True,
            "database_url_secret_manager_reference": True,
            "database_url_value_in_git": False,
            "mlb_activation_switches_default_off": True,
            "fastapi_lifespan_bound": True,
            "frozen_step13_controls_bound": True,
            "frozen_step14c_persistence_bound": True,
        },
        "runtime_contract": {
            "lifecycle_default_enabled": False,
            "explicit_lifecycle_gate_required": True,
            "database_connection_on_app_startup": False,
            "scheduler_cycle_on_app_startup": False,
            "background_task_on_app_startup": False,
            "provider_calls_on_app_startup": 0,
            "sportsbook_calls_on_app_startup": 0,
            "production_activation_ready": False,
            "step16c_live_canary_required": True,
        },
        "safety_contract": deepcopy(SAFETY_CONTRACT),
        "phase_boundary": {
            "step16a_blockers_closed": True,
            "step16b_packaging_complete": True,
            "step16b_lifecycle_binding_complete": True,
            "step16b_complete": True,
            "step16c_live_postgresql_canary_required": True,
            "live_canary_not_started": True,
            "controlled_production_activation_not_started": True,
            "production_runtime_not_started": True,
            "production_scheduler_not_started": True,
            "global_persistence_autostart_not_started": True,
        },
    }
    surface = deepcopy(result)
    surface.pop("generated_at_utc", None)
    result["contract_content_sha256"] = _canonical_hash(surface)
    assert_step16b_integrity()
    return result


__all__ = [
    "DATA_TYPE", "SCHEMA_VERSION", "INTEGRATION_VERSION", "CONTRACT_ID",
    "FINAL_CERTIFICATION_MARKER", "RUNTIME_MODE", "BRANCH", "STEP16B_BASE_MAIN_SHA",
    "STEP16A_CERTIFIED_MAIN_SHA", "STEP16A_SOURCE_BLOB_SHA", "STEP16A_CONTRACT_ID",
    "STEP16A_CONTRACT_CONTENT_SHA256", "STEP15C_CERTIFIED_MAIN_SHA", "STEP15_RELEASE_ID",
    "STEP15_RELEASE_MANIFEST_SHA256", "EVIDENCE_PATH", "EVIDENCE_CONTENT_SHA256",
    "EXPECTED_BLOB_SHAS", "SAFETY_CONTRACT", "MLBStep16BContractIntegrityError",
    "git_blob_sha", "load_step16b_evidence", "validate_step16b_packaging_files",
    "validate_step16b_evidence", "assert_step16b_integrity", "build_step16b_contract_manifest",
]
