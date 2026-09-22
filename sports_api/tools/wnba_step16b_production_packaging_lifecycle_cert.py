"""Deterministic certification artifact for WNBA Step 16B."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path

from sports_api import wnba_step16b_packaging_lifecycle_contract as contract
from sports_api import wnba_step16b_production_lifecycle as lifecycle

CERT_FILE = "step16b-production-packaging-lifecycle-cert.json"


def main() -> None:
    evidence = contract.assert_step16b_integrity()
    manifest = contract.build_step16b_contract_manifest(
        generated_at_utc="2026-08-28T20:00:00+00:00"
    )
    disabled_status = lifecycle.build_step16b_lifecycle_status({})
    artifact = {
        "data_type": "wnba_step16b_production_packaging_lifecycle_certification",
        "schema_version": contract.SCHEMA_VERSION,
        "integration_version": contract.INTEGRATION_VERSION,
        "contract_id": contract.CONTRACT_ID,
        "branch": contract.BRANCH,
        "certified": True,
        "certified_at_utc": datetime.now(timezone.utc).isoformat(),
        "certified_head_sha": os.environ.get("GITHUB_SHA"),
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "expected_regression_tests": 620,
        "new_step16b_tests": 20,
        "frozen_step16a_parent_tests": 20,
        "frozen_step15_through_step8_tests": 580,
        "contract_content_sha256": manifest["contract_content_sha256"],
        "evidence_content_sha256": contract.EVIDENCE_CONTENT_SHA256,
        "lineage": manifest["lineage"],
        "blocker_resolution": manifest["blocker_resolution"],
        "packaging_certification": {
            "psycopg3_packaged_in_container": True,
            "requirements_persistence_preserved": True,
            "kyre_database_url_secret_manager_contract": True,
            "kyre_database_url_value_committed": False,
            "fastapi_lifespan_bound": True,
            "frozen_step14c_runner_bound_only_when_explicitly_enabled": True,
        },
        "certification_transport": {
            "live_database_used": False,
            "database_credentials_required_in_ci": False,
            "database_connection_executed": False,
            "runtime_runner_executed": False,
            "scheduler_cycle_executed": False,
            "background_task_started": False,
            "production_canary_executed": False,
        },
        "disabled_lifecycle_status": disabled_status,
        "safety_contract": manifest["safety_contract"],
        "phase_boundary": manifest["phase_boundary"],
        "step16c_live_canary_required": True,
        "production_activation_ready": False,
        "production_activation_performed": False,
        "evidence_observed_at_utc": evidence["observed_at_utc"],
    }
    Path(CERT_FILE).write_text(
        json.dumps(artifact, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print("STEP16B_PRODUCTION_PACKAGING_LIFECYCLE_OK")
    print(json.dumps(artifact, sort_keys=True))


if __name__ == "__main__":
    main()
