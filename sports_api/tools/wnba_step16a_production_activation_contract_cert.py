"""Deterministic certification for WNBA Step 16A production readiness."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path

from sports_api import wnba_step16a_production_activation_contract as s16a

CERT_FILE = "step16a-production-activation-contract-cert.json"


def safe_env() -> dict[str, str]:
    return {
        s16a.STEP16A_PRODUCTION_ACTIVATION_CONTRACT_ENABLED_ENV: "true",
        "WNBA_PRODUCTION_RUNTIME_ENABLED": "false",
        "WNBA_BOARD_SCHEDULER_ENABLED": "false",
        "WNBA_PERSISTENCE_ENABLED": "false",
        "WNBA_SUPABASE_WRITE_ENABLED": "false",
        "WNBA_WAGERING_ENABLED": "false",
        "WNBA_STEP12_SCHEDULER_ENABLED": "false",
    }


def main() -> None:
    env = safe_env()
    evidence = s16a.validate_step16a_readiness_evidence(
        s16a.load_step16a_readiness_evidence()
    )
    first = s16a.build_step16a_production_activation_contract(
        env=env,
        generated_at_utc="2026-08-28T19:50:00+00:00",
    )
    second = s16a.build_step16a_production_activation_contract(
        env=env,
        generated_at_utc="2026-08-29T01:50:00+00:00",
    )
    if first["contract_content_sha256"] != second["contract_content_sha256"]:
        raise SystemExit("Step 16A contract hash is not deterministic")

    artifact = {
        "data_type": "wnba_step16a_production_activation_readiness_certification",
        "schema_version": s16a.SCHEMA_VERSION,
        "integration_version": s16a.INTEGRATION_VERSION,
        "contract_id": s16a.CONTRACT_ID,
        "branch": s16a.BRANCH,
        "certified": True,
        "certified_at_utc": datetime.now(timezone.utc).isoformat(),
        "certified_head_sha": os.environ.get("GITHUB_SHA"),
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "expected_regression_tests": 600,
        "new_step16a_tests": 20,
        "contract_content_sha256": first["contract_content_sha256"],
        "readiness_evidence_content_sha256": s16a.EVIDENCE_CONTENT_SHA256,
        "lineage": first["lineage"],
        "readiness_certification": {
            "step15_live_schema_certified": True,
            "step15_live_transactions_certified": True,
            "production_activation_ready": False,
            "blocking_requirements": list(s16a.BLOCKING_REQUIREMENTS),
            "blocker_count": len(s16a.BLOCKING_REQUIREMENTS),
        },
        "deployment_surface": s16a.inspect_current_deployment_surface(),
        "activation_boundary": first["activation_contract"],
        "safety_contract": first["safety_contract"],
        "phase_boundary": first["phase_boundary"],
        "certification_transport": {
            "live_database_used": False,
            "database_credentials_required": False,
            "external_host_deployed": False,
            "production_process_started": False,
            "secrets_written": False,
            "inspection_only": True,
        },
        "evidence_observed_at_utc": evidence["observed_at_utc"],
    }
    Path(CERT_FILE).write_text(
        json.dumps(artifact, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print("STEP16A_PRODUCTION_ACTIVATION_READINESS_CONTRACT_OK")
    print(json.dumps(artifact, sort_keys=True))


if __name__ == "__main__":
    main()
