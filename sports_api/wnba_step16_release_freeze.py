"""WNBA Step 16E: final controlled-production certification freeze.

This module adds zero runtime behavior. It freezes the certified Step-16D
production Docker -> psycopg -> live PostgreSQL controlled activation on top of
Steps 16A-16C and the previously frozen Step 8-15 chain.

The release certifies controlled one-shot production-shaped activation,
durable restart recovery, and zero canary residue. It deliberately does NOT
start continuous production runtime or claim a Render-hosted service activation.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

from sports_api import wnba_step16d_controlled_production_activation as step16d

SOURCE = "Kyre Sports API WNBA Step 16 final production certification freeze"
SCHEMA_VERSION = "wnba_step_16e_final_production_freeze_v1"
RELEASE_ID = "wnba_step16_controlled_production_activation_2026_regular_season_frozen_v1"
BRANCH = "wnba-step16e-final-production-freeze-20260828"
SEASON = 2026
SEASON_TYPE = "Regular Season"

STEP16D_CERTIFIED_SHA = "b13307e6a89a456edfd0fc4f4ddbb5244ae91a60"
STEP16D_CONTRACT_ID = "wnba_step16d_controlled_production_activation_2026_regular_v1"
STEP16D_CONTRACT_CONTENT_SHA256 = "18e1ef2c13489d1f5f1c7ee7fe6a3c13ea81c505871648a089731fd3a5957677"
STEP16D_LIVE_RESULT_CONTENT_SHA256 = "3521db6ffb5302f0cb3c26a313c21222bc23cbbecb2aed190f4a9999982edc30"
STEP16D_ARTIFACT_DIGEST_SHA256 = "0f6b128d87faf22c62743e15ea62920cb4911442dfcf63cbb363000d74eb4fad"
STEP16C_CERTIFIED_SHA = "1de22beb83cad2f0c3bae3bc6ab845b5f3d2a4e3"
STEP16B_CERTIFIED_SHA = "f898ca410c10db59f635888166d1666a952d8bd7"
STEP16A_CERTIFIED_SHA = "4ea88aa9a54f5110a03e9e4374219ed15ab30def"
STEP15C_CERTIFIED_SHA = "5e24210d7aef90143ba016e368cd49d3ee1a7f19"

FINAL_EVIDENCE_PATH = "sports_api/certification/wnba_step16e_final_production_freeze_evidence.json"
FINAL_EVIDENCE_CONTENT_SHA256 = "0a604f48017fbe2eb7d8284432937b89f48cc853dde91318bcae2e63382f4426"
EXPECTED_SUPABASE_PROJECT_REF = "jqajcdckalsfizbvngiu"
EXPECTED_MIGRATION_VERSION = "20260828191445"
EXPECTED_MIGRATION_NAME = "wnba_step15a_install_frozen_step14_persistence_schema"

STEP16E_FINAL_PRODUCTION_FREEZE_ENABLED_ENV = "WNBA_STEP16E_FINAL_PRODUCTION_FREEZE_ENABLED"
DEFAULT_ENABLED = False
CONTROLLED_PRODUCTION_ACTIVATION_CERTIFIED = True
PRODUCTION_DOCKER_IMAGE_EXECUTION_CERTIFIED = True
DIRECT_PSYCOG_LIVE_CONNECTION_CERTIFIED = True
TWO_CYCLE_DURABLE_RESTART_CERTIFIED = True
ZERO_RESIDUE_CERTIFIED = True

CONTINUOUS_PRODUCTION_RUNTIME_ALLOWED = False
RENDER_HOSTED_SERVICE_ACTIVATION_CERTIFIED = False
GLOBAL_PERSISTENCE_AUTOSTART_ALLOWED = False
AUTOMATIC_RESTART_AUTOSTART_ALLOWED = False
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
SECRETS_IN_OUTPUT_ALLOWED = False

_FORBIDDEN_TRUE_ENV_KEYS = (
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_PERSISTENCE_ENABLED",
    "WNBA_SUPABASE_WRITE_ENABLED",
    "WNBA_WAGERING_ENABLED",
    "WNBA_STEP12_SCHEDULER_ENABLED",
)

SAFETY_CONTRACT = {
    "continuous_production_runtime": False,
    "render_hosted_service_activation_certified": False,
    "global_persistence_autostart": False,
    "automatic_restart_autostart": False,
    "background_daemon": False,
    "background_thread": False,
    "background_task": False,
    "public_persistence_api": False,
    "supabase_rest_write": False,
    "wager_action": False,
    "authentication": False,
    "cookies": False,
    "secrets_in_output": False,
    "basketball_model_change": False,
    "step8_distribution_change": False,
    "step9_ranking_change": False,
    "step9_qualification_change": False,
}


class WNBAStep16ReleaseDisabledError(RuntimeError):
    pass


class WNBAStep16ReleaseIntegrityError(RuntimeError):
    pass


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() not in {"", "0", "false", "no", "off", "disabled"}


def _canonical_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def step16e_freeze_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(STEP16E_FINAL_PRODUCTION_FREEZE_ENABLED_ENV))


def _evidence_hash_surface(evidence: Mapping[str, Any]) -> dict[str, Any]:
    surface = deepcopy(dict(evidence))
    surface.pop("observed_at_utc", None)
    surface.pop("evidence_content_sha256", None)
    return surface


def load_step16e_final_evidence(path: str = FINAL_EVIDENCE_PATH) -> dict[str, Any]:
    try:
        evidence = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WNBAStep16ReleaseIntegrityError("Step 16E cannot load final evidence.") from exc
    if not isinstance(evidence, dict):
        raise WNBAStep16ReleaseIntegrityError("Step 16E evidence must be an object.")
    observed = str(evidence.get("evidence_content_sha256") or "").lower()
    expected = _canonical_hash(_evidence_hash_surface(evidence))
    if observed != expected or expected != FINAL_EVIDENCE_CONTENT_SHA256:
        raise WNBAStep16ReleaseIntegrityError("Step 16E evidence content hash drift.")
    return evidence


def validate_step16e_final_evidence(evidence: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(evidence, Mapping):
        raise WNBAStep16ReleaseIntegrityError("Step 16E evidence must be an object.")
    if evidence.get("data_type") != "wnba_step16e_final_production_freeze_evidence":
        raise WNBAStep16ReleaseIntegrityError("Step 16E evidence type drift.")
    project = evidence.get("supabase_project")
    parent = evidence.get("step16d_certification")
    live = evidence.get("final_live_state")
    cleanup = evidence.get("out_of_release_cleanup")
    phase = evidence.get("phase_boundary")
    safety = evidence.get("safety")
    if not all(isinstance(v, Mapping) for v in (project, parent, live, cleanup, phase, safety)):
        raise WNBAStep16ReleaseIntegrityError("Step 16E evidence object shape drift.")
    if project.get("ref") != EXPECTED_SUPABASE_PROJECT_REF or project.get("status") != "ACTIVE_HEALTHY" or str(project.get("postgres_engine")) != "17":
        raise WNBAStep16ReleaseIntegrityError("Step 16E Supabase identity/health drift.")
    expected_parent = {
        "certified_head_sha": STEP16D_CERTIFIED_SHA,
        "contract_id": STEP16D_CONTRACT_ID,
        "contract_content_sha256": STEP16D_CONTRACT_CONTENT_SHA256,
        "live_result_content_sha256": STEP16D_LIVE_RESULT_CONTENT_SHA256,
        "artifact_digest_sha256": STEP16D_ARTIFACT_DIGEST_SHA256,
        "expected_total_regression_tests": 660,
        "direct_psycopg_live_connection_certified": True,
        "production_docker_image_execution_certified": True,
        "two_cycle_durable_restart_certified": True,
        "canary_cleanup_zero_residue_certified": True,
        "credential_value_exposed": False,
        "render_hosted_service_activation_certified": False,
        "continuous_production_runtime_started": False,
    }
    for key, expected in expected_parent.items():
        if parent.get(key) != expected:
            raise WNBAStep16ReleaseIntegrityError(f"Step 16E Step-16D evidence drift: {key}.")
    for key in ("checkpoint_rows", "checkpoint_head_rows", "lease_rows"):
        if live.get(key) != 0:
            raise WNBAStep16ReleaseIntegrityError(f"Step 16E live residue drift: {key}.")
    for key in ("checkpoints_present", "heads_present", "leases_present", "postgres_schema_usage"):
        if live.get(key) is not True:
            raise WNBAStep16ReleaseIntegrityError(f"Step 16E live schema drift: {key}.")
    for key in ("anon_schema_usage", "authenticated_schema_usage", "service_role_schema_usage"):
        if live.get(key) is not False:
            raise WNBAStep16ReleaseIntegrityError(f"Step 16E client privilege drift: {key}.")
    if live.get("migration_version") != EXPECTED_MIGRATION_VERSION or live.get("migration_name") != EXPECTED_MIGRATION_NAME:
        raise WNBAStep16ReleaseIntegrityError("Step 16E migration identity drift.")
    if live.get("kyre_runtime_security_advisor_findings") != 0:
        raise WNBAStep16ReleaseIntegrityError("Step 16E kyre_runtime security findings are not zero.")
    if cleanup.get("slug") != "noop-do-not-deploy" or cleanup.get("verify_jwt") is not True or cleanup.get("excluded_from_step16_release") is not True or cleanup.get("cleanup_pending") is not True:
        raise WNBAStep16ReleaseIntegrityError("Step 16E out-of-release cleanup disclosure drift.")
    if cleanup.get("persistence_access_certified") is not False:
        raise WNBAStep16ReleaseIntegrityError("Step 16E no-op Edge Function scope drift.")
    required_phase_true = ("step16a_complete", "step16b_complete", "step16c_complete", "step16d_controlled_activation_complete", "step16e_final_freeze_candidate", "continuous_production_runtime_not_started", "render_hosted_service_activation_not_certified")
    if any(phase.get(key) is not True for key in required_phase_true):
        raise WNBAStep16ReleaseIntegrityError("Step 16E phase boundary drift.")
    if any(value is not False for value in safety.values()):
        raise WNBAStep16ReleaseIntegrityError("Step 16E safety evidence drift.")
    return deepcopy(dict(evidence))


def _assert_release_integrity(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    source = dict(os.environ if env is None else env)
    if not step16e_freeze_enabled(source):
        raise WNBAStep16ReleaseDisabledError(f"Step 16E requires {STEP16E_FINAL_PRODUCTION_FREEZE_ENABLED_ENV}=true.")
    bad = [key for key in _FORBIDDEN_TRUE_ENV_KEYS if _truthy(source.get(key))]
    if bad:
        raise WNBAStep16ReleaseDisabledError("Step 16E refuses unsafe runtime switches: " + ", ".join(bad))
    if step16d.CONTRACT_ID != STEP16D_CONTRACT_ID or step16d.STEP16C_CERTIFIED_SHA != STEP16C_CERTIFIED_SHA or step16d.STEP16B_CERTIFIED_SHA != STEP16B_CERTIFIED_SHA or step16d.STEP15C_CERTIFIED_SHA != STEP15C_CERTIFIED_SHA:
        raise WNBAStep16ReleaseIntegrityError("Step 16E frozen Step-16D lineage drift.")
    required_true = (CONTROLLED_PRODUCTION_ACTIVATION_CERTIFIED, PRODUCTION_DOCKER_IMAGE_EXECUTION_CERTIFIED, DIRECT_PSYCOG_LIVE_CONNECTION_CERTIFIED, TWO_CYCLE_DURABLE_RESTART_CERTIFIED, ZERO_RESIDUE_CERTIFIED)
    if any(value is not True for value in required_true):
        raise WNBAStep16ReleaseIntegrityError("Step 16E certification constant drift.")
    forbidden = (DEFAULT_ENABLED, CONTINUOUS_PRODUCTION_RUNTIME_ALLOWED, RENDER_HOSTED_SERVICE_ACTIVATION_CERTIFIED, GLOBAL_PERSISTENCE_AUTOSTART_ALLOWED, AUTOMATIC_RESTART_AUTOSTART_ALLOWED, BACKGROUND_DAEMON_ALLOWED, BACKGROUND_THREAD_ALLOWED, BACKGROUND_TASK_ALLOWED, PUBLIC_PERSISTENCE_API_ALLOWED, SUPABASE_REST_WRITE_ALLOWED, WAGERING_ALLOWED, AUTHENTICATION_ALLOWED, COOKIES_ALLOWED, BASKETBALL_MODEL_MUTATION_ALLOWED, RANKING_MUTATION_ALLOWED, SECRETS_IN_OUTPUT_ALLOWED)
    if any(value is not False for value in forbidden) or any(SAFETY_CONTRACT.values()):
        raise WNBAStep16ReleaseIntegrityError("Step 16E safety constant drift.")
    return validate_step16e_final_evidence(load_step16e_final_evidence())


def _release_hash_surface(manifest: Mapping[str, Any]) -> dict[str, Any]:
    return {key: deepcopy(value) for key, value in manifest.items() if key not in {"generated_at_utc", "release_content_sha256"}}


def build_step16_release_manifest(*, env: Mapping[str, str] | None = None, generated_at_utc: str | None = None) -> dict[str, Any]:
    evidence = _assert_release_integrity(env)
    generated = datetime.now(timezone.utc) if generated_at_utc is None else datetime.fromisoformat(str(generated_at_utc).replace("Z", "+00:00"))
    parent = evidence["step16d_certification"]
    live = evidence["final_live_state"]
    cleanup = evidence["out_of_release_cleanup"]
    manifest = {
        "data_type": "wnba_step16e_final_production_release",
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        "release_id": RELEASE_ID,
        "season": SEASON,
        "season_type": SEASON_TYPE,
        "status": "frozen",
        "lineage": {
            "step16d_certified_sha": STEP16D_CERTIFIED_SHA,
            "step16c_certified_sha": STEP16C_CERTIFIED_SHA,
            "step16b_certified_sha": STEP16B_CERTIFIED_SHA,
            "step16a_certified_sha": STEP16A_CERTIFIED_SHA,
            "step15c_certified_sha": STEP15C_CERTIFIED_SHA,
            "step16d_contract_id": STEP16D_CONTRACT_ID,
            "step16d_contract_content_sha256": STEP16D_CONTRACT_CONTENT_SHA256,
            "step16d_live_result_content_sha256": STEP16D_LIVE_RESULT_CONTENT_SHA256,
            "step16d_artifact_digest_sha256": STEP16D_ARTIFACT_DIGEST_SHA256,
            "final_evidence_content_sha256": FINAL_EVIDENCE_CONTENT_SHA256,
        },
        "certification": {
            "controlled_production_activation": True,
            "production_docker_image_execution": True,
            "direct_psycopg_live_connection": True,
            "two_cycle_durable_restart_recovery": True,
            "zero_canary_residue": True,
            "protected_database_secret_used": True,
            "credential_value_exposed": False,
            "parent_regression_tests": int(parent["expected_total_regression_tests"]),
        },
        "final_live_state": {
            "project_ref": evidence["supabase_project"]["ref"],
            "project_status": evidence["supabase_project"]["status"],
            "postgres_version": evidence["supabase_project"]["observed_postgres_version"],
            "checkpoint_rows": live["checkpoint_rows"],
            "checkpoint_head_rows": live["checkpoint_head_rows"],
            "lease_rows": live["lease_rows"],
            "kyre_runtime_security_advisor_findings": live["kyre_runtime_security_advisor_findings"],
        },
        "scope_boundary": {
            "continuous_production_runtime_started": False,
            "render_hosted_service_activation_certified": False,
            "global_persistence_autostart_started": False,
            "public_persistence_api_exposed": False,
            "out_of_release_edge_function_cleanup_pending": bool(cleanup["cleanup_pending"]),
            "out_of_release_edge_function_slug": cleanup["slug"],
        },
        "safety_contract": deepcopy(SAFETY_CONTRACT),
        "phase_boundary": {
            "step16_complete": True,
            "final_release_frozen": True,
            "controlled_activation_certified": True,
            "continuous_hosted_runtime_intentionally_not_activated": True,
        },
        "generated_at_utc": generated.astimezone(timezone.utc).isoformat(),
    }
    manifest["release_content_sha256"] = _canonical_hash(_release_hash_surface(manifest))
    return manifest


def validate_step16_release_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(manifest, Mapping):
        raise WNBAStep16ReleaseIntegrityError("Step 16 release manifest must be an object.")
    if manifest.get("release_id") != RELEASE_ID or manifest.get("status") != "frozen":
        raise WNBAStep16ReleaseIntegrityError("Step 16 release identity drift.")
    observed = str(manifest.get("release_content_sha256") or "").lower()
    if observed != _canonical_hash(_release_hash_surface(manifest)):
        raise WNBAStep16ReleaseIntegrityError("Step 16 release content hash mismatch.")
    certification = manifest.get("certification")
    scope = manifest.get("scope_boundary")
    safety = manifest.get("safety_contract")
    phase = manifest.get("phase_boundary")
    if not all(isinstance(v, Mapping) for v in (certification, scope, safety, phase)):
        raise WNBAStep16ReleaseIntegrityError("Step 16 release object shape drift.")
    for key in ("controlled_production_activation", "production_docker_image_execution", "direct_psycopg_live_connection", "two_cycle_durable_restart_recovery", "zero_canary_residue", "protected_database_secret_used"):
        if certification.get(key) is not True:
            raise WNBAStep16ReleaseIntegrityError(f"Step 16 release certification drift: {key}.")
    if certification.get("credential_value_exposed") is not False:
        raise WNBAStep16ReleaseIntegrityError("Step 16 credential safety drift.")
    if scope.get("continuous_production_runtime_started") is not False or scope.get("render_hosted_service_activation_certified") is not False:
        raise WNBAStep16ReleaseIntegrityError("Step 16 hosted/continuous scope drift.")
    if any(value is not False for value in safety.values()):
        raise WNBAStep16ReleaseIntegrityError("Step 16 release safety drift.")
    if phase.get("step16_complete") is not True or phase.get("final_release_frozen") is not True:
        raise WNBAStep16ReleaseIntegrityError("Step 16 final phase drift.")
    return deepcopy(dict(manifest))


__all__ = [
    "BRANCH", "DEFAULT_ENABLED", "FINAL_EVIDENCE_CONTENT_SHA256", "FINAL_EVIDENCE_PATH",
    "RELEASE_ID", "SAFETY_CONTRACT", "SCHEMA_VERSION", "SOURCE",
    "STEP16D_ARTIFACT_DIGEST_SHA256", "STEP16D_CERTIFIED_SHA", "STEP16D_CONTRACT_CONTENT_SHA256",
    "STEP16D_CONTRACT_ID", "STEP16D_LIVE_RESULT_CONTENT_SHA256",
    "STEP16E_FINAL_PRODUCTION_FREEZE_ENABLED_ENV", "WNBAStep16ReleaseDisabledError",
    "WNBAStep16ReleaseIntegrityError", "build_step16_release_manifest",
    "load_step16e_final_evidence", "step16e_freeze_enabled", "validate_step16_release_manifest",
    "validate_step16e_final_evidence",
]
