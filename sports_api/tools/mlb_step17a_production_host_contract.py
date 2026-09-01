from __future__ import annotations

import json
import os
from pathlib import Path

from sports_api import mlb_step17a_production_host_contract_v1 as step17a

OUTPUT_PATH = Path("mlb-step17a-production-host-contract-cert.json")


def build_certification() -> dict:
    report = step17a.validate_host_contract(
        os.environ,
        build_revision=step17a.STEP16E_FROZEN_SHA,
    )
    evidence = step17a.validate_step17a_evidence(step17a.load_step17a_evidence())
    inventory = evidence["render_inventory"]
    return {
        "data_type": "mlb_step17a_production_host_contract_certification_v1",
        "schema_version": 1,
        "certified": True,
        "branch": step17a.BRANCH,
        "contract_id": step17a.CONTRACT_ID,
        "final_certification_marker": step17a.FINAL_CERTIFICATION_MARKER,
        "status": report["status"],
        "frozen_step16e_sha": step17a.STEP16E_FROZEN_SHA,
        "frozen_step16e_tested_head_sha": step17a.STEP16E_TESTED_HEAD_SHA,
        "frozen_step16e_tree_sha": step17a.STEP16E_TREE_SHA,
        "frozen_step16e_release_content_sha256": step17a.STEP16E_RELEASE_CONTENT_SHA256,
        "frozen_step16e_evidence_content_sha256": step17a.STEP16E_FINAL_EVIDENCE_CONTENT_SHA256,
        "dockerfile_blob_sha": step17a.STEP16E_DOCKERFILE_BLOB_SHA,
        "main_blob_sha": step17a.STEP16E_MAIN_BLOB_SHA,
        "host_evidence_content_sha256": step17a.EVIDENCE_CONTENT_SHA256,
        "render_inventory_github_run_id": inventory["github_run_id"],
        "render_inventory_github_job_id": inventory["github_job_id"],
        "render_inventory_artifact_id": inventory["artifact_id"],
        "render_service_id": report["render_service_id"],
        "render_service_name": report["render_service_name"],
        "render_service_url": report["render_service_url"],
        "render_runtime": report["render_runtime"],
        "render_region": report["render_region"],
        "render_auto_deploy": report["render_auto_deploy"],
        "render_health_check_path": report["render_health_check_path"],
        "existing_shared_host_identified": True,
        "read_only_render_inventory_certified": True,
        "local_frozen_container_health_proof_required": True,
        "database_secret_configured": True,
        "database_connection_opened": False,
        "database_secret_exposed": False,
        "render_service_mutated": False,
        "render_deploy_triggered": False,
        "new_render_service_created": False,
        "production_runtime_started": False,
        "production_scheduler_started": False,
        "provider_calls": 0,
        "sportsbook_calls": 0,
        "actionable_output_enabled": False,
        "wagering_enabled": False,
        "step17b_required_for_hosted_activation": True,
        "safety_contract": report["safety_contract"],
    }


def main() -> None:
    cert = build_certification()
    OUTPUT_PATH.write_text(
        json.dumps(cert, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(cert, sort_keys=True))
    print(step17a.FINAL_CERTIFICATION_MARKER)


if __name__ == "__main__":
    main()
