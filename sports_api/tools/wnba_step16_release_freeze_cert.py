from __future__ import annotations

import json
import os
from pathlib import Path

from sports_api import wnba_step16_release_freeze as s16

OUTPUT_PATH = Path("step16-final-production-freeze-cert.json")


def certification_env() -> dict[str, str]:
    env = dict(os.environ)
    env[s16.STEP16E_FINAL_PRODUCTION_FREEZE_ENABLED_ENV] = "true"
    for key in (
        "WNBA_PRODUCTION_RUNTIME_ENABLED",
        "WNBA_BOARD_SCHEDULER_ENABLED",
        "WNBA_PERSISTENCE_ENABLED",
        "WNBA_SUPABASE_WRITE_ENABLED",
        "WNBA_WAGERING_ENABLED",
        "WNBA_STEP12_SCHEDULER_ENABLED",
    ):
        env[key] = "false"
    env.pop("KYRE_DATABASE_URL", None)
    return env


def build_certification() -> dict:
    env = certification_env()
    evidence = s16.validate_step16e_final_evidence(s16.load_step16e_final_evidence())
    manifest = s16.validate_step16_release_manifest(
        s16.build_step16_release_manifest(env=env)
    )
    parent = evidence["step16d_certification"]
    cleanup = evidence["out_of_release_cleanup"]
    return {
        "data_type": "wnba_step16e_final_production_freeze_certification",
        "schema_version": "wnba_step_16e_final_production_freeze_certification_v1",
        "certified": True,
        "branch": s16.BRANCH,
        "release_id": s16.RELEASE_ID,
        "release_content_sha256": manifest["release_content_sha256"],
        "final_evidence_content_sha256": s16.FINAL_EVIDENCE_CONTENT_SHA256,
        "step16d_certified_sha": s16.STEP16D_CERTIFIED_SHA,
        "step16d_contract_content_sha256": s16.STEP16D_CONTRACT_CONTENT_SHA256,
        "step16d_live_result_content_sha256": s16.STEP16D_LIVE_RESULT_CONTENT_SHA256,
        "step16d_artifact_digest_sha256": s16.STEP16D_ARTIFACT_DIGEST_SHA256,
        "step16d_github_run_id": parent["github_run_id"],
        "step16d_github_job_id": parent["github_job_id"],
        "step16d_artifact_id": parent["artifact_id"],
        "direct_psycopg_live_connection_certified": True,
        "production_docker_image_execution_certified": True,
        "two_cycle_durable_restart_certified": True,
        "zero_residue_certified": True,
        "continuous_production_runtime_started": False,
        "render_hosted_service_activation_certified": False,
        "credential_value_exposed": False,
        "out_of_release_edge_function_cleanup_pending": cleanup["cleanup_pending"],
        "out_of_release_edge_function_slug": cleanup["slug"],
        "new_step16e_tests": 20,
        "expected_total_regression_tests": 680,
        "phase_boundary": manifest["phase_boundary"],
        "safety_contract": manifest["safety_contract"],
    }


def main() -> None:
    cert = build_certification()
    OUTPUT_PATH.write_text(json.dumps(cert, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(cert, sort_keys=True))


if __name__ == "__main__":
    main()
