"""MLB Step 16E — final controlled-production certification freeze.

This module adds zero runtime behavior. It freezes the exact Step 16D
foreground two-cycle PostgreSQL activation proof, the Step 16A-16C lineage,
and the final zero-residue database state into one immutable release manifest.

The freeze certifies controlled one-shot production-shaped persistence and
restart behavior. It deliberately does NOT start or certify a continuous MLB
runtime, production scheduler, hosted always-on service, provider/sportsbook
networking, actionable output, or wagering.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping

from sports_api import mlb_step16d_controlled_production_activation_v1 as step16d
from sports_api.mlb_step9_final_freeze_v1 import PROTECTED_INVARIANTS

DATA_TYPE = "mlb_step16e_final_production_freeze_v1"
SCHEMA_VERSION = 1
RELEASE_ID = "mlb_step16_controlled_production_activation_2026_regular_season_frozen_v1"
RUNTIME_MODE = "SHADOW_ONLY"
BRANCH = "mlb-step16e-final-production-freeze"
FINAL_CERTIFICATION_MARKER = "MLB_STEP16E_FINAL_PRODUCTION_FREEZE_GREEN"

STEP16D_TESTED_HEAD_SHA = "b325ddeb1df0d23fcdebf7b1d498ef473a0054f5"
STEP16D_MAIN_MERGE_SHA = "4261c872cc94c55a466b7e1bb9d80e62abdc95c8"
STEP16D_CONTRACT_ID = "mlb_step16d_controlled_production_activation_2026_regular_v1"
STEP16D_FINAL_MARKER = "MLB_STEP16D_CONTROLLED_PRODUCTION_ACTIVATION_GREEN"
STEP16D_LIVE_RESULT_CONTENT_SHA256 = "c60af03a55dfeac968170b05e11ad3036b05372132bb85f0805f20c83ce82280"
STEP16D_ARTIFACT_DIGEST_SHA256 = "2ae3f960e170c9b00d47df9648365805feff2deb8ef6be2499889952c1149936"
STEP16D_GITHUB_RUN_ID = 33564715670
STEP16D_GITHUB_JOB_ID = 100045137919
STEP16D_ARTIFACT_ID = 9822652235

STEP16C_MAIN_MERGE_SHA = "435a12fa4ccb2aac47ea109e27da3b6e94856427"
STEP16B_MAIN_MERGE_SHA = "eb0ea430caea02f90b6367b8bc0ea28f698246bf"
STEP16A_CERTIFIED_SHA = "c5ad6047224aaf014cec13f5efa6e5cd650da939"
STEP15C_CERTIFIED_MAIN_SHA = "a67d415e5e1d8614d632fd34cfa09d551792a71f"
STEP15_RELEASE_ID = "mlb_step15_live_supabase_persistence_2026_regular_season_frozen_v1"
STEP15_RELEASE_MANIFEST_SHA256 = "d5c184988de8db66af6ef2c4e158dd8016a3403f968d42296f41dfa69bf83ada"

FINAL_EVIDENCE_PATH = "sports_api/certification/mlb_step16e_final_production_freeze_evidence.json"
FINAL_EVIDENCE_CONTENT_SHA256 = "5987ae2e98b72031007757c631772f26fac0134a2f6ca3a19e496bfc26e0d7a0"

STEP16E_FINAL_PRODUCTION_FREEZE_ENABLED_ENV = "MLB_STEP16E_FINAL_PRODUCTION_FREEZE_ENABLED"
DEFAULT_ENABLED = False
CONTROLLED_PRODUCTION_ACTIVATION_CERTIFIED = True
DIRECT_PSYCOG_LIVE_CONNECTION_CERTIFIED = True
TWO_CYCLE_DURABLE_RESTART_CERTIFIED = True
FENCED_LEASE_CERTIFIED = True
CHECKPOINT_CAS_CERTIFIED = True
ZERO_RESIDUE_CERTIFIED = True

CONTINUOUS_PRODUCTION_RUNTIME_ALLOWED = False
PRODUCTION_SCHEDULER_ALLOWED = False
HOSTED_ALWAYS_ON_SERVICE_CERTIFIED = False
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

_FORBIDDEN_TRUE_ENV_KEYS = (
    "MLB_PRODUCTION_RUNTIME_ENABLED",
    "MLB_PRODUCTION_SCHEDULER_ENABLED",
    "MLB_ACTIONABLE_OUTPUT_ENABLED",
    "MLB_WAGERING_ENABLED",
    "MLB_SUPABASE_REST_WRITE_ENABLED",
    "MLB_STEP16B_DURABLE_LIFECYCLE_ENABLED",
    "MLB_STEP16C_LIVE_POSTGRESQL_CANARY_ENABLED",
    "MLB_STEP16D_CONTROLLED_PRODUCTION_ACTIVATION_ENABLED",
    "MLB_STEP14C_DURABLE_RESTART_LEASE_ENABLED",
    "MLB_STEP14B_DATABASE_CHECKPOINT_ADAPTER_ENABLED",
    "MLB_STEP14B_DATABASE_READ_ENABLED",
    "MLB_STEP14B_DATABASE_WRITE_ENABLED",
)

SAFETY_CONTRACT = {
    "continuous_production_runtime": False,
    "production_scheduler": False,
    "hosted_always_on_service_certified": False,
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


class MLBStep16EFreezeDisabledError(RuntimeError):
    """Raised unless the non-live Step 16E certification gate is explicit."""


class MLBStep16EFreezeIntegrityError(RuntimeError):
    """Raised when frozen lineage, evidence, or safety boundaries drift."""


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


def step16e_freeze_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return _truthy(source.get(STEP16E_FINAL_PRODUCTION_FREEZE_ENABLED_ENV))


def _evidence_hash_surface(evidence: Mapping[str, Any]) -> dict[str, Any]:
    surface = deepcopy(dict(evidence))
    surface.pop("evidence_content_sha256", None)
    return surface


def _release_hash_surface(manifest: Mapping[str, Any]) -> dict[str, Any]:
    surface = deepcopy(dict(manifest))
    surface.pop("generated_at_utc", None)
    surface.pop("release_content_sha256", None)
    return surface


def load_step16e_final_evidence(path: str = FINAL_EVIDENCE_PATH) -> dict[str, Any]:
    try:
        evidence = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MLBStep16EFreezeIntegrityError("Step 16E cannot load final evidence") from exc
    if not isinstance(evidence, dict):
        raise MLBStep16EFreezeIntegrityError("Step 16E evidence must be an object")
    observed = str(evidence.get("evidence_content_sha256") or "").lower()
    expected = _canonical_hash(_evidence_hash_surface(evidence))
    if observed != expected or expected != FINAL_EVIDENCE_CONTENT_SHA256:
        raise MLBStep16EFreezeIntegrityError("Step 16E evidence content hash drift")
    return evidence


def _assert_step16d_identity() -> None:
    checks = {
        "contract_id": step16d.CONTRACT_ID == STEP16D_CONTRACT_ID,
        "marker": step16d.FINAL_CERTIFICATION_MARKER == STEP16D_FINAL_MARKER,
        "runtime_mode": step16d.RUNTIME_MODE == RUNTIME_MODE,
        "continuous": step16d.CONTINUOUS_PRODUCTION_ALLOWED is False,
        "runtime": step16d.PRODUCTION_RUNTIME_ALLOWED is False,
        "scheduler": step16d.PRODUCTION_SCHEDULER_ALLOWED is False,
        "providers": step16d.PROVIDER_CALLS_ALLOWED is False,
        "sportsbooks": step16d.SPORTSBOOK_CALLS_ALLOWED is False,
        "wagering": step16d.WAGERING_ALLOWED is False,
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise MLBStep16EFreezeIntegrityError(
            "Step 16D frozen identity drift: " + ", ".join(failed)
        )
    if any(value is not False for value in PROTECTED_INVARIANTS.values()):
        raise MLBStep16EFreezeIntegrityError("protected MLB invariant drift")


def validate_step16e_final_evidence(evidence: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(evidence, Mapping):
        raise MLBStep16EFreezeIntegrityError("Step 16E evidence must be a mapping")
    value = dict(evidence)
    if value.get("data_type") != "mlb_step16e_final_production_freeze_evidence_v1":
        raise MLBStep16EFreezeIntegrityError("Step 16E evidence type drift")
    if value.get("schema_version") != 1:
        raise MLBStep16EFreezeIntegrityError("Step 16E evidence schema drift")

    live = value.get("final_live_state")
    parent = value.get("step16d_certification")
    lineage = value.get("lineage")
    phase = value.get("phase_boundary")
    safety = value.get("safety")
    if not all(isinstance(item, Mapping) for item in (live, parent, lineage, phase, safety)):
        raise MLBStep16EFreezeIntegrityError("Step 16E evidence shape drift")

    if not all(live.get(key) is True for key in (
        "checkpoints_present", "heads_present", "leases_present", "postgres_schema_usage"
    )):
        raise MLBStep16EFreezeIntegrityError("Step 16E PostgreSQL schema presence drift")
    if (live.get("checkpoint_rows"), live.get("checkpoint_head_rows"), live.get("lease_rows")) != (0, 0, 0):
        raise MLBStep16EFreezeIntegrityError("Step 16E final PostgreSQL residue is non-zero")
    if any(live.get(key) is not False for key in (
        "anon_schema_usage", "authenticated_schema_usage", "service_role_schema_usage"
    )):
        raise MLBStep16EFreezeIntegrityError("Step 16E client-role schema privilege drift")
    if live.get("database_name") != "postgres" or live.get("database_role") != "postgres":
        raise MLBStep16EFreezeIntegrityError("Step 16E PostgreSQL identity drift")
    if live.get("postgres_version") != "17.6":
        raise MLBStep16EFreezeIntegrityError("Step 16E PostgreSQL version drift")

    expected_parent = {
        "tested_head_sha": STEP16D_TESTED_HEAD_SHA,
        "main_merge_sha": STEP16D_MAIN_MERGE_SHA,
        "contract_id": STEP16D_CONTRACT_ID,
        "final_marker": STEP16D_FINAL_MARKER,
        "live_result_content_sha256": STEP16D_LIVE_RESULT_CONTENT_SHA256,
        "artifact_digest_sha256": STEP16D_ARTIFACT_DIGEST_SHA256,
        "github_run_id": STEP16D_GITHUB_RUN_ID,
        "github_job_id": STEP16D_GITHUB_JOB_ID,
        "artifact_id": STEP16D_ARTIFACT_ID,
        "targeted_step16d_tests": 7,
        "step16c_guard_tests": 12,
        "step16b_guard_tests": 25,
        "current_mlb_regression_tests": 3591,
        "cycle_count": 2,
        "cycle_1_saved_version": 1,
        "cycle_2_recovered_version": 1,
        "cycle_2_saved_version": 2,
        "checkpoint_history_rows_before_cleanup": 2,
        "checkpoint_head_rows_before_cleanup": 1,
        "lease_rows_before_cleanup": 0,
        "checkpoint_rows_after_cleanup": 0,
        "checkpoint_head_rows_after_cleanup": 0,
        "lease_rows_after_cleanup": 0,
        "direct_psycopg_live_connection_certified": True,
        "two_cycle_durable_restart_certified": True,
        "fenced_lease_certified": True,
        "checkpoint_cas_certified": True,
        "zero_residue_certified": True,
    }
    if dict(parent) != expected_parent:
        raise MLBStep16EFreezeIntegrityError("Step 16D certification evidence drift")

    expected_lineage = {
        "step16c_main_merge_sha": STEP16C_MAIN_MERGE_SHA,
        "step16b_main_merge_sha": STEP16B_MAIN_MERGE_SHA,
        "step16a_certified_sha": STEP16A_CERTIFIED_SHA,
        "step15c_certified_main_sha": STEP15C_CERTIFIED_MAIN_SHA,
        "step15_release_id": STEP15_RELEASE_ID,
        "step15_release_manifest_sha256": STEP15_RELEASE_MANIFEST_SHA256,
    }
    if dict(lineage) != expected_lineage:
        raise MLBStep16EFreezeIntegrityError("Step 16 lineage evidence drift")

    if not all(phase.get(key) is True for key in (
        "step16a_complete", "step16b_complete", "step16c_complete",
        "step16d_controlled_activation_complete", "step16e_final_freeze_candidate",
        "continuous_production_runtime_not_started", "continuous_scheduler_not_started",
        "hosted_always_on_service_not_certified",
    )):
        raise MLBStep16EFreezeIntegrityError("Step 16E phase boundary drift")

    false_safety = (
        "production_runtime_started", "production_scheduler_started",
        "continuous_production_started", "background_worker_started",
        "background_thread_started", "background_task_started",
        "public_persistence_api_exposed", "supabase_rest_write_enabled",
        "actionable_output_enabled", "wagering_enabled", "auth_mutated",
        "cookies_mutated", "model_mutated", "ranking_mutated",
        "credential_value_exposed",
    )
    if any(safety.get(key) is not False for key in false_safety):
        raise MLBStep16EFreezeIntegrityError("Step 16E safety evidence drift")
    if safety.get("provider_calls") != 0 or safety.get("sportsbook_calls") != 0:
        raise MLBStep16EFreezeIntegrityError("Step 16E network-call evidence drift")

    expected_hash = _canonical_hash(_evidence_hash_surface(value))
    if value.get("evidence_content_sha256") != expected_hash:
        raise MLBStep16EFreezeIntegrityError("Step 16E evidence hash mismatch")
    _assert_step16d_identity()
    return deepcopy(value)


def _validated_freeze_env(env: Mapping[str, str] | None = None) -> dict[str, str]:
    source = dict(os.environ if env is None else env)
    if not step16e_freeze_enabled(source):
        raise MLBStep16EFreezeDisabledError(
            f"Step 16E requires {STEP16E_FINAL_PRODUCTION_FREEZE_ENABLED_ENV}=true"
        )
    bad = [key for key in _FORBIDDEN_TRUE_ENV_KEYS if _truthy(source.get(key))]
    if bad:
        raise MLBStep16EFreezeDisabledError(
            "Step 16E refuses live/runtime switches: " + ", ".join(bad)
        )
    if str(source.get("KYRE_DATABASE_URL") or "").strip():
        raise MLBStep16EFreezeDisabledError(
            "Step 16E certification is static and refuses KYRE_DATABASE_URL"
        )
    if any(value is not False for value in SAFETY_CONTRACT.values()):
        raise MLBStep16EFreezeIntegrityError("Step 16E safety contract drift")
    _assert_step16d_identity()
    return source


def build_step16_release_manifest(
    *,
    env: Mapping[str, str] | None = None,
    generated_at_utc: str | None = None,
) -> dict[str, Any]:
    _validated_freeze_env(env)
    evidence = validate_step16e_final_evidence(load_step16e_final_evidence())
    generated = generated_at_utc or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    manifest: dict[str, Any] = {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "release_id": RELEASE_ID,
        "runtime_mode": RUNTIME_MODE,
        "branch": BRANCH,
        "final_certification_marker": FINAL_CERTIFICATION_MARKER,
        "generated_at_utc": generated,
        "lineage": {
            "step16d_tested_head_sha": STEP16D_TESTED_HEAD_SHA,
            "step16d_main_merge_sha": STEP16D_MAIN_MERGE_SHA,
            "step16c_main_merge_sha": STEP16C_MAIN_MERGE_SHA,
            "step16b_main_merge_sha": STEP16B_MAIN_MERGE_SHA,
            "step16a_certified_sha": STEP16A_CERTIFIED_SHA,
            "step15c_certified_main_sha": STEP15C_CERTIFIED_MAIN_SHA,
            "step15_release_id": STEP15_RELEASE_ID,
            "step15_release_manifest_sha256": STEP15_RELEASE_MANIFEST_SHA256,
        },
        "certification": {
            "controlled_production_activation": True,
            "direct_psycopg_live_connection": True,
            "two_cycle_durable_restart": True,
            "fenced_lease": True,
            "checkpoint_cas": True,
            "zero_residue": True,
            "final_live_database_state_zero": True,
            "step16d_live_result_content_sha256": STEP16D_LIVE_RESULT_CONTENT_SHA256,
            "step16d_artifact_digest_sha256": STEP16D_ARTIFACT_DIGEST_SHA256,
        },
        "final_live_state": deepcopy(evidence["final_live_state"]),
        "safety_contract": deepcopy(SAFETY_CONTRACT),
        "scope_boundary": {
            "continuous_production_runtime_started": False,
            "production_scheduler_started": False,
            "hosted_always_on_service_certified": False,
            "provider_calls_authorized": False,
            "sportsbook_calls_authorized": False,
            "actionable_output_authorized": False,
            "wagering_authorized": False,
        },
        "phase_boundary": {
            "step16_complete": True,
            "final_controlled_production_freeze": True,
            "continuous_hosted_runtime_intentionally_not_activated": True,
            "future_hosted_always_on_step_required": True,
        },
        "final_evidence_content_sha256": FINAL_EVIDENCE_CONTENT_SHA256,
    }
    manifest["release_content_sha256"] = _canonical_hash(_release_hash_surface(manifest))
    return manifest


def validate_step16_release_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(manifest, Mapping):
        raise MLBStep16EFreezeIntegrityError("Step 16E manifest must be a mapping")
    value = dict(manifest)
    exact = {
        "data_type": value.get("data_type") == DATA_TYPE,
        "schema_version": value.get("schema_version") == SCHEMA_VERSION,
        "release_id": value.get("release_id") == RELEASE_ID,
        "runtime_mode": value.get("runtime_mode") == RUNTIME_MODE,
        "branch": value.get("branch") == BRANCH,
        "marker": value.get("final_certification_marker") == FINAL_CERTIFICATION_MARKER,
        "evidence": value.get("final_evidence_content_sha256") == FINAL_EVIDENCE_CONTENT_SHA256,
    }
    failed = [name for name, ok in exact.items() if not ok]
    if failed:
        raise MLBStep16EFreezeIntegrityError(
            "Step 16E manifest identity drift: " + ", ".join(failed)
        )
    if value.get("safety_contract") != SAFETY_CONTRACT:
        raise MLBStep16EFreezeIntegrityError("Step 16E manifest safety drift")
    if any(value.get("scope_boundary", {}).get(key) is not False for key in (
        "continuous_production_runtime_started", "production_scheduler_started",
        "hosted_always_on_service_certified", "provider_calls_authorized",
        "sportsbook_calls_authorized", "actionable_output_authorized",
        "wagering_authorized",
    )):
        raise MLBStep16EFreezeIntegrityError("Step 16E scope boundary drift")
    if value.get("phase_boundary", {}).get("step16_complete") is not True:
        raise MLBStep16EFreezeIntegrityError("Step 16E completion boundary drift")
    digest = value.get("release_content_sha256")
    if not isinstance(digest, str) or len(digest) != 64:
        raise MLBStep16EFreezeIntegrityError("Step 16E release hash invalid")
    if digest != _canonical_hash(_release_hash_surface(value)):
        raise MLBStep16EFreezeIntegrityError("Step 16E release content hash mismatch")
    validate_step16e_final_evidence(load_step16e_final_evidence())
    _assert_step16d_identity()
    return deepcopy(value)


__all__ = [
    "DATA_TYPE", "SCHEMA_VERSION", "RELEASE_ID", "RUNTIME_MODE", "BRANCH",
    "FINAL_CERTIFICATION_MARKER", "STEP16D_TESTED_HEAD_SHA", "STEP16D_MAIN_MERGE_SHA",
    "STEP16D_CONTRACT_ID", "STEP16D_FINAL_MARKER", "STEP16D_LIVE_RESULT_CONTENT_SHA256",
    "STEP16D_ARTIFACT_DIGEST_SHA256", "STEP16D_GITHUB_RUN_ID", "STEP16D_GITHUB_JOB_ID",
    "STEP16D_ARTIFACT_ID", "STEP16C_MAIN_MERGE_SHA", "STEP16B_MAIN_MERGE_SHA",
    "STEP16A_CERTIFIED_SHA", "STEP15C_CERTIFIED_MAIN_SHA", "STEP15_RELEASE_ID",
    "STEP15_RELEASE_MANIFEST_SHA256", "FINAL_EVIDENCE_PATH", "FINAL_EVIDENCE_CONTENT_SHA256",
    "STEP16E_FINAL_PRODUCTION_FREEZE_ENABLED_ENV", "DEFAULT_ENABLED", "SAFETY_CONTRACT",
    "CONTROLLED_PRODUCTION_ACTIVATION_CERTIFIED", "DIRECT_PSYCOG_LIVE_CONNECTION_CERTIFIED",
    "TWO_CYCLE_DURABLE_RESTART_CERTIFIED", "FENCED_LEASE_CERTIFIED",
    "CHECKPOINT_CAS_CERTIFIED", "ZERO_RESIDUE_CERTIFIED",
    "CONTINUOUS_PRODUCTION_RUNTIME_ALLOWED", "PRODUCTION_SCHEDULER_ALLOWED",
    "HOSTED_ALWAYS_ON_SERVICE_CERTIFIED", "MLBStep16EFreezeDisabledError",
    "MLBStep16EFreezeIntegrityError", "step16e_freeze_enabled", "load_step16e_final_evidence",
    "validate_step16e_final_evidence", "build_step16_release_manifest",
    "validate_step16_release_manifest",
]
