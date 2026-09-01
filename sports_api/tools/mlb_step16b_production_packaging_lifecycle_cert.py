"""Deterministic certification for MLB Step 16B packaging/lifecycle integration."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path

from sports_api import mlb_step16b_packaging_lifecycle_contract_v1 as s16b

CERT_FILE = "mlb-step16b-production-packaging-lifecycle-cert.json"


def main() -> None:
    evidence = s16b.validate_step16b_evidence(s16b.load_step16b_evidence())
    first = s16b.build_step16b_contract_manifest(
        generated_at_utc="2026-09-01T21:20:00+00:00"
    )
    second = s16b.build_step16b_contract_manifest(
        generated_at_utc="2026-09-02T01:20:00+00:00"
    )
    if first["contract_content_sha256"] != second["contract_content_sha256"]:
        raise SystemExit("Step 16B contract hash is not deterministic")
    if first["runtime_contract"]["production_activation_ready"] is not False:
        raise SystemExit("Step 16B must not mark production activation ready")
    if first["runtime_contract"]["step16c_live_canary_required"] is not True:
        raise SystemExit("Step 16B must require Step 16C live canary")
    if any(value is not False for value in first["safety_contract"].values()):
        raise SystemExit("Step 16B safety contract drift")

    artifact = {
        "data_type": "mlb_step16b_production_packaging_lifecycle_certification_v1",
        "schema_version": s16b.SCHEMA_VERSION,
        "integration_version": s16b.INTEGRATION_VERSION,
        "contract_id": s16b.CONTRACT_ID,
        "branch": s16b.BRANCH,
        "certified": True,
        "certified_at_utc": datetime.now(timezone.utc).isoformat(),
        "certified_head_sha": os.environ.get("GITHUB_SHA"),
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "new_step16b_tests": 25,
        "expected_full_mlb_regression_tests": 3595,
        "contract_content_sha256": first["contract_content_sha256"],
        "evidence_content_sha256": s16b.EVIDENCE_CONTENT_SHA256,
        "lineage": first["lineage"],
        "blocker_resolution": first["blocker_resolution"],
        "packaging_contract": first["packaging_contract"],
        "runtime_contract": first["runtime_contract"],
        "safety_contract": first["safety_contract"],
        "phase_boundary": first["phase_boundary"],
        "certification_transport": {
            "live_database_used": False,
            "database_credentials_required": False,
            "database_connection_executed": False,
            "runtime_executed": False,
            "provider_calls": 0,
            "sportsbook_calls": 0,
            "production_process_started": False,
            "background_worker_started": False,
            "secrets_written": False,
            "packaging_and_lifecycle_only": True,
        },
        "deployment_files": s16b.validate_step16b_packaging_files(),
        "evidence_observed_at_utc": evidence["observed_at_utc"],
        "final_certification_marker": s16b.FINAL_CERTIFICATION_MARKER,
    }
    Path(CERT_FILE).write_text(
        json.dumps(artifact, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(artifact, sort_keys=True))
    print(s16b.FINAL_CERTIFICATION_MARKER)


if __name__ == "__main__":
    main()
