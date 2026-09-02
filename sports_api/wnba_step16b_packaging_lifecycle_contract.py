"""WNBA Step 16B production packaging + lifecycle certification contract.

This module content-addresses the Step-16B deployment changes that close the
three blockers found by certified Step 16A. It deliberately does not authorize
or execute a live canary. Production remains fail-closed until Step 16C.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Mapping

from sports_api import wnba_step14c_durable_restart_lease as step14c
from sports_api import wnba_step16b_production_lifecycle as lifecycle

SOURCE = "Kyre Sports API WNBA Step 16B production packaging lifecycle certification contract"
SCHEMA_VERSION = "wnba_step_16b_production_packaging_lifecycle_contract_v1"
INTEGRATION_VERSION = "wnba_step16b_production_packaging_lifecycle_contract_v1"
CONTRACT_ID = "wnba_step16b_production_packaging_lifecycle_2026_regular_v1"
BRANCH = "wnba-step16b-production-packaging-lifecycle-20260828"
SEASON = 2026
SEASON_TYPE = "Regular Season"

STEP16A_CERTIFIED_SHA = "4ea88aa9a54f5110a03e9e4374219ed15ab30def"
STEP16A_CONTRACT_ID = "wnba_step16a_production_activation_readiness_2026_regular_v1"
STEP16A_CONTRACT_CONTENT_SHA256 = "2d8c373dded7eb971d6d6bf6b4a5c9bdfc7bd19de5ddcf1ef83158a0b7d2000e"
STEP15C_CERTIFIED_SHA = "5e24210d7aef90143ba016e368cd49d3ee1a7f19"
STEP15_RELEASE_ID = "wnba_step15_live_supabase_persistence_2026_regular_season_frozen_v1"
STEP15_RELEASE_CONTENT_SHA256 = "537df3ec10999071941597e71f4e6361e246db98b17c13a3a31a944f9b8e9a2b"

EVIDENCE_PATH = "sports_api/certification/wnba_step16b_production_packaging_lifecycle_evidence.json"
EVIDENCE_CONTENT_SHA256 = "4b8cc7e179725aab5a50c6e0edd3d7e3215d2f16be1d487bc28e9f20edab1fa1"
DOCKERFILE_PATH = "sports_api/Dockerfile"
ENV_EXAMPLE_PATH = "sports_api/production.env.example"
MAIN_PATH = "sports_api/main.py"
LIFECYCLE_PATH = "sports_api/wnba_step16b_production_lifecycle.py"
BASE_REQUIREMENTS_PATH = "sports_api/requirements.txt"
PERSISTENCE_REQUIREMENTS_PATH = "sports_api/requirements-persistence.txt"

EXPECTED_BLOB_SHAS = {
    DOCKERFILE_PATH: "324defd214f334c372f3b0b2dcafd958c962a6aa",
    MAIN_PATH: "fe0e9b8595db6712157c1ee114c9a805b789f6ed",
    ENV_EXAMPLE_PATH: "7a707d49f073836017f6560f6a741c47d24fd1db",
    PERSISTENCE_REQUIREMENTS_PATH: "46331822d0a55f5a4983d289c73a45ea9745ca89",
    BASE_REQUIREMENTS_PATH: "84e666d78549778a84f216e80d2bb979c1f6160a",
    LIFECYCLE_PATH: "265812f8a5cee31514f0cc13ca1d45c5a45836f8",
}

PRODUCTION_ACTIVATION_READY = False
STEP16C_LIVE_CANARY_REQUIRED = True
LIVE_CANARY_EXECUTED = False
PRODUCTION_RUNTIME_ENABLED = False
GLOBAL_PERSISTENCE_AUTOSTART_ENABLED = False
AUTOMATIC_RESTART_ACTIVATION_ENABLED = False
BACKGROUND_WORKER_ENABLED = False
PUBLIC_PERSISTENCE_API_ENABLED = False
SUPABASE_REST_WRITE_ENABLED = False
WAGERING_ENABLED = False
DATABASE_CONNECTION_EXECUTED = False
RUNTIME_RUNNER_EXECUTED = False

SAFETY_CONTRACT = {
    "production_activation_ready": False,
    "live_canary_executed": False,
    "production_runtime": False,
    "global_persistence_autostart": False,
    "automatic_restart_activation": False,
    "database_connection_executed": False,
    "runtime_runner_executed": False,
    "background_worker": False,
    "background_thread": False,
    "background_task": False,
    "public_persistence_api": False,
    "supabase_rest_write": False,
    "wager_action": False,
    "authentication": False,
    "cookies": False,
    "secret_value_committed": False,
    "basketball_model_change": False,
    "step8_distribution_change": False,
    "step9_ranking_change": False,
    "step9_qualification_change": False,
}


class WNBAStep16BContractIntegrityError(RuntimeError):
    """Raised when Step-16B evidence or deployment packaging drifts."""


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


def _git_blob_sha_bytes(raw: bytes) -> str:
    header = f"blob {len(raw)}\0".encode("ascii")
    return hashlib.sha1(header + raw).hexdigest()


def git_blob_sha(path: str) -> str:
    try:
        return _git_blob_sha_bytes(Path(path).read_bytes())
    except OSError as exc:
        raise WNBAStep16BContractIntegrityError(
            f"Step 16B cannot read required deployment file: {path}."
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
        raise WNBAStep16BContractIntegrityError(
            "Step 16B cannot load packaging/lifecycle evidence."
        ) from exc
    if not isinstance(evidence, dict):
        raise WNBAStep16BContractIntegrityError("Step 16B evidence must be a JSON object.")
    actual = _canonical_hash(_evidence_hash_surface(evidence))
    if evidence.get("evidence_content_sha256") != actual or actual != EVIDENCE_CONTENT_SHA256:
        raise WNBAStep16BContractIntegrityError("Step 16B evidence content hash drift.")
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
        raise WNBAStep16BContractIntegrityError("Step 16B deployment file blob drift.")

    docker = Path(DOCKERFILE_PATH).read_text(encoding="utf-8")
    env_example = Path(ENV_EXAMPLE_PATH).read_text(encoding="utf-8")
    main = Path(MAIN_PATH).read_text(encoding="utf-8")
    persistence_requirements = Path(PERSISTENCE_REQUIREMENTS_PATH).read_text(encoding="utf-8").strip()

    required_docker_fragments = (
        "COPY sports_api/requirements-persistence.txt /app/sports_api/requirements-persistence.txt",
        "python -m pip install --no-cache-dir -r /app/sports_api/requirements-persistence.txt",
    )
    if any(fragment not in docker for fragment in required_docker_fragments):
        raise WNBAStep16BContractIntegrityError("Step 16B Docker persistence packaging drift.")
    if persistence_requirements != "psycopg[binary]>=3.2,<4":
        raise WNBAStep16BContractIntegrityError("Step 16B psycopg requirement drift.")

    if "Required secret-manager key: KYRE_DATABASE_URL" not in env_example:
        raise WNBAStep16BContractIntegrityError("Step 16B KYRE_DATABASE_URL secret-manager contract missing.")
    if _noncomment_assignment_exists(env_example, "KYRE_DATABASE_URL"):
        raise WNBAStep16BContractIntegrityError("Step 16B refuses a committed KYRE_DATABASE_URL value.")
    if "WNBA_STEP16B_DURABLE_LIFECYCLE_ENABLED=false" not in env_example:
        raise WNBAStep16BContractIntegrityError("Step 16B default-OFF lifecycle env contract missing.")

    if "from sports_api.wnba_step16b_production_lifecycle import step16b_lifespan" not in main:
        raise WNBAStep16BContractIntegrityError("Step 16B main.py lifecycle import drift.")
    if "lifespan=step16b_lifespan" not in main:
        raise WNBAStep16BContractIntegrityError("Step 16B FastAPI lifespan binding drift.")

    return observed


def validate_step16b_evidence(evidence: Mapping[str, Any]) -> dict[str, Any]:
    if evidence.get("data_type") != "wnba_step16b_production_packaging_lifecycle_evidence":
        raise WNBAStep16BContractIntegrityError("Step 16B evidence data_type drift.")
    parent = evidence.get("frozen_parent")
    blockers = evidence.get("blocker_resolution")
    lifecycle_contract = evidence.get("lifecycle_contract")
    activation = evidence.get("activation_boundary")
    deployment_files = evidence.get("deployment_files")
    if not all(isinstance(x, Mapping) for x in (parent, blockers, lifecycle_contract, activation, deployment_files)):
        raise WNBAStep16BContractIntegrityError("Step 16B evidence object shape drift.")

    expected_parent = {
        "step16a_certified_sha": STEP16A_CERTIFIED_SHA,
        "step16a_contract_id": STEP16A_CONTRACT_ID,
        "step16a_contract_content_sha256": STEP16A_CONTRACT_CONTENT_SHA256,
        "step15c_certified_sha": STEP15C_CERTIFIED_SHA,
        "step15_release_id": STEP15_RELEASE_ID,
        "step15_release_content_sha256": STEP15_RELEASE_CONTENT_SHA256,
    }
    if dict(parent) != expected_parent:
        raise WNBAStep16BContractIntegrityError("Step 16B frozen parent lineage drift.")
    if dict(deployment_files) != EXPECTED_BLOB_SHAS:
        raise WNBAStep16BContractIntegrityError("Step 16B evidence deployment file identity drift.")

    required_blockers_true = (
        "all_step16a_packaging_lifecycle_blockers_closed",
        "deployment_secret_manager_contract_declares_kyre_database_url",
        "docker_installs_persistence_requirements",
        "fastapi_lifespan_binds_frozen_step14c_runner",
    )
    if any(blockers.get(key) is not True for key in required_blockers_true):
        raise WNBAStep16BContractIntegrityError("Step 16B blocker resolution drift.")
    if blockers.get("kyre_database_url_value_committed") is not False:
        raise WNBAStep16BContractIntegrityError("Step 16B secret-value boundary drift.")

    required_lifecycle_true = (
        "explicit_gate_required",
        "psycopg3_packaged",
        "database_secret_required_only_when_enabled",
        "runtime_runner_bound_only_when_enabled",
        "step16c_live_canary_still_required",
    )
    if any(lifecycle_contract.get(key) is not True for key in required_lifecycle_true):
        raise WNBAStep16BContractIntegrityError("Step 16B lifecycle capability evidence drift.")
    required_lifecycle_false = (
        "default_enabled",
        "database_connection_during_lifespan",
        "runtime_runner_executed_during_lifespan",
        "background_daemon_started",
        "background_task_started",
        "background_thread_started",
    )
    if any(lifecycle_contract.get(key) is not False for key in required_lifecycle_false):
        raise WNBAStep16BContractIntegrityError("Step 16B lifecycle safety evidence drift.")
    if not activation or any(value is not False for value in activation.values()):
        raise WNBAStep16BContractIntegrityError("Step 16B activation boundary drift.")
    return deepcopy(dict(evidence))


def assert_step16b_integrity() -> dict[str, Any]:
    if lifecycle.DEFAULT_ENABLED is not False:
        raise WNBAStep16BContractIntegrityError("Step 16B lifecycle default-enable drift.")
    if lifecycle.PRODUCTION_ACTIVATION_ALLOWED is not False or lifecycle.PRODUCTION_CANARY_ALLOWED is not False:
        raise WNBAStep16BContractIntegrityError("Step 16B production safety drift.")
    if lifecycle.DATABASE_CONNECTION_DURING_LIFESPAN_ALLOWED is not False:
        raise WNBAStep16BContractIntegrityError("Step 16B lifespan DB-connection boundary drift.")
    if lifecycle.get_step16b_runtime_binding({}) is not None:
        raise WNBAStep16BContractIntegrityError("Step 16B default-off runner binding drift.")
    if step14c.run_step14c_durable_restart_lease.__module__ != step14c.__name__:
        raise WNBAStep16BContractIntegrityError("Step 16B frozen Step-14C runner identity drift.")
    if any(value is not False for value in SAFETY_CONTRACT.values()):
        raise WNBAStep16BContractIntegrityError("Step 16B certification safety contract drift.")
    validate_step16b_packaging_files()
    return validate_step16b_evidence(load_step16b_evidence())


def build_step16b_contract_manifest(*, generated_at_utc: str | None = None) -> dict[str, Any]:
    """Build deterministic Step-16B certification manifest without a DB connection."""
    evidence = assert_step16b_integrity()
    generated = generated_at_utc or datetime.now(timezone.utc).isoformat()
    result = {
        "data_type": "wnba_step16b_production_packaging_lifecycle_contract",
        "schema_version": SCHEMA_VERSION,
        "integration_version": INTEGRATION_VERSION,
        "source": SOURCE,
        "contract_id": CONTRACT_ID,
        "branch": BRANCH,
        "generated_at_utc": generated,
        "season": SEASON,
        "season_type": SEASON_TYPE,
        "lineage": {
            "step16a_certified_sha": STEP16A_CERTIFIED_SHA,
            "step16a_contract_id": STEP16A_CONTRACT_ID,
            "step16a_contract_content_sha256": STEP16A_CONTRACT_CONTENT_SHA256,
            "step15c_certified_sha": STEP15C_CERTIFIED_SHA,
            "step15_release_id": STEP15_RELEASE_ID,
            "step15_release_content_sha256": STEP15_RELEASE_CONTENT_SHA256,
            "step16b_evidence_content_sha256": EVIDENCE_CONTENT_SHA256,
        },
        "blocker_resolution": deepcopy(dict(evidence["blocker_resolution"])),
        "packaging_contract": {
            "psycopg3_in_container": True,
            "base_requirements_preserved": True,
            "persistence_requirements_preserved": True,
            "database_url_secret_manager_reference": True,
            "database_url_value_in_git": False,
            "fastapi_lifespan_bound": True,
            "frozen_step14c_foreground_runner_bound": True,
        },
        "runtime_contract": {
            "lifecycle_default_enabled": False,
            "explicit_lifecycle_gate_required": True,
            "database_connection_on_app_startup": False,
            "scheduler_cycle_on_app_startup": False,
            "background_task_on_app_startup": False,
            "production_activation_ready": False,
            "step16c_live_canary_required": True,
        },
        "safety_contract": deepcopy(SAFETY_CONTRACT),
        "phase_boundary": {
            "step16a_blockers_closed": True,
            "step16b_packaging_complete": True,
            "step16b_lifecycle_binding_complete": True,
            "step16c_live_canary_not_started": True,
            "step16c_live_canary_required": True,
            "production_activation_not_started": True,
            "controlled_production_activation_not_authorized": True,
        },
    }
    surface = deepcopy(result)
    surface.pop("generated_at_utc", None)
    result["contract_content_sha256"] = _canonical_hash(surface)
    assert_step16b_integrity()
    return result


__all__ = [
    "BRANCH",
    "CONTRACT_ID",
    "EVIDENCE_CONTENT_SHA256",
    "EVIDENCE_PATH",
    "EXPECTED_BLOB_SHAS",
    "INTEGRATION_VERSION",
    "SAFETY_CONTRACT",
    "SCHEMA_VERSION",
    "SOURCE",
    "STEP16A_CERTIFIED_SHA",
    "STEP16A_CONTRACT_CONTENT_SHA256",
    "STEP16A_CONTRACT_ID",
    "STEP16C_LIVE_CANARY_REQUIRED",
    "WNBAStep16BContractIntegrityError",
    "assert_step16b_integrity",
    "build_step16b_contract_manifest",
    "git_blob_sha",
    "load_step16b_evidence",
    "validate_step16b_evidence",
    "validate_step16b_packaging_files",
]
