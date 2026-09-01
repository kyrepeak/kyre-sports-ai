from __future__ import annotations

import json
import os
from pathlib import Path

from sports_api import mlb_step16e_final_production_freeze_v1 as step16e

OUTPUT_PATH = Path("mlb-step16e-final-production-freeze-cert.json")


def certification_env() -> dict[str, str]:
    env = dict(os.environ)
    env[step16e.STEP16E_FINAL_PRODUCTION_FREEZE_ENABLED_ENV] = "true"
    for key in (
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
    ):
        env[key] = "false"
    env.pop("KYRE_DATABASE_URL", None)
    return env


def build_certification() -> dict:
    evidence = step16e.validate_step16e_final_evidence(
        step16e.load_step16e_final_evidence()
    )
    manifest = step16e.validate_step16_release_manifest(
        step16e.build_step16_release_manifest(env=certification_env())
    )
    return {
        "data_type": "mlb_step16e_final_production_freeze_certification_v1",
        "schema_version": 1,
        "certified": True,
        "branch": step16e.BRANCH,
        "release_id": step16e.RELEASE_ID,
        "final_certification_marker": step16e.FINAL_CERTIFICATION_MARKER,
        "release_content_sha256": manifest["release_content_sha256"],
        "final_evidence_content_sha256": step16e.FINAL_EVIDENCE_CONTENT_SHA256,
        "step16d_tested_head_sha": step16e.STEP16D_TESTED_HEAD_SHA,
        "step16d_main_merge_sha": step16e.STEP16D_MAIN_MERGE_SHA,
        "step16d_live_result_content_sha256": step16e.STEP16D_LIVE_RESULT_CONTENT_SHA256,
        "step16d_artifact_digest_sha256": step16e.STEP16D_ARTIFACT_DIGEST_SHA256,
        "step16d_github_run_id": step16e.STEP16D_GITHUB_RUN_ID,
        "step16d_github_job_id": step16e.STEP16D_GITHUB_JOB_ID,
        "step16d_artifact_id": step16e.STEP16D_ARTIFACT_ID,
        "direct_psycopg_live_connection_certified": True,
        "two_cycle_durable_restart_certified": True,
        "fenced_lease_certified": True,
        "checkpoint_cas_certified": True,
        "zero_residue_certified": True,
        "final_checkpoint_rows": evidence["final_live_state"]["checkpoint_rows"],
        "final_checkpoint_head_rows": evidence["final_live_state"]["checkpoint_head_rows"],
        "final_lease_rows": evidence["final_live_state"]["lease_rows"],
        "continuous_production_runtime_started": False,
        "production_scheduler_started": False,
        "hosted_always_on_service_certified": False,
        "provider_calls": 0,
        "sportsbook_calls": 0,
        "actionable_output_enabled": False,
        "wagering_enabled": False,
        "credential_value_exposed": False,
        "new_step16e_tests": 20,
        "expected_current_mlb_regression_tests": 3611,
        "expected_frozen_step16a_tests": 23,
        "expected_combined_guarded_tests": 3634,
        "phase_boundary": manifest["phase_boundary"],
        "safety_contract": manifest["safety_contract"],
    }


def main() -> None:
    cert = build_certification()
    OUTPUT_PATH.write_text(
        json.dumps(cert, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(cert, sort_keys=True))
    print(step16e.FINAL_CERTIFICATION_MARKER)


if __name__ == "__main__":
    main()
