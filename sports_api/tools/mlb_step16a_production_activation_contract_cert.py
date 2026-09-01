"""Deterministic certification for MLB Step 16A production readiness."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path

from sports_api import mlb_step16a_production_activation_contract_v1 as s16a

CERT_FILE = "mlb-step16a-production-activation-contract-cert.json"


def safe_env() -> dict[str, str]:
    return {
        s16a.STEP16A_PRODUCTION_ACTIVATION_CONTRACT_ENABLED_ENV: "true",
        "MLB_STEP15C_FINAL_LIVE_PERSISTENCE_FREEZE_ENABLED": "true",
        "MLB_STEP15B_LIVE_ADAPTER_SMOKE_ENABLED": "true",
        "MLB_PRODUCTION_RUNTIME_ENABLED": "false",
        "MLB_PRODUCTION_SCHEDULER_ENABLED": "false",
        "MLB_ACTIONABLE_OUTPUT_ENABLED": "false",
        "MLB_WAGERING_ENABLED": "false",
        "MLB_SUPABASE_REST_WRITE_ENABLED": "false",
    }


def main() -> None:
    env = safe_env()
    evidence = s16a.validate_step16a_readiness_evidence(
        s16a.load_step16a_readiness_evidence()
    )
    first = s16a.build_step16a_production_activation_contract(
        env=env,
        generated_at_utc="2026-09-01T21:07:00+00:00",
    )
    second = s16a.build_step16a_production_activation_contract(
        env=env,
        generated_at_utc="2026-09-02T03:07:00+00:00",
    )
    if first["contract_content_sha256"] != second["contract_content_sha256"]:
        raise SystemExit("MLB Step 16A contract hash is not deterministic")
    if first["readiness"]["production_activation_ready"] is not False:
        raise SystemExit("MLB Step 16A unexpectedly reports production ready")
    if first["readiness"]["blocker_count"] != 4:
        raise SystemExit("MLB Step 16A blocker count drift")
    if any(value is not False for value in first["safety_contract"].values()):
        raise SystemExit("MLB Step 16A safety contract drift")

    artifact = {
        "data_type": "mlb_step16a_production_activation_readiness_certification_v1",
        "schema_version": s16a.SCHEMA_VERSION,
        "integration_version": s16a.INTEGRATION_VERSION,
        "contract_id": s16a.CONTRACT_ID,
        "branch": s16a.BRANCH,
        "certified": True,
        "certified_at_utc": datetime.now(timezone.utc).isoformat(),
        "certified_head_sha": os.environ.get("GITHUB_SHA"),
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "expected_full_mlb_regression_tests": 3570,
        "new_step16a_tests": 23,
        "contract_content_sha256": first["contract_content_sha256"],
        "readiness_evidence_content_sha256": s16a.EVIDENCE_CONTENT_SHA256,
        "lineage": first["lineage"],
        "readiness_certification": {
            "step15_live_schema_certified": True,
            "step15_live_transactions_certified": True,
            "step15_release_frozen": True,
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
            "runtime_cycle_executed": False,
            "provider_calls": 0,
            "sportsbook_calls": 0,
            "secrets_written": False,
            "inspection_only": True,
        },
        "evidence_observed_at_utc": evidence["observed_at_utc"],
        "final_certification_marker": s16a.FINAL_CERTIFICATION_MARKER,
    }
    Path(CERT_FILE).write_text(
        json.dumps(artifact, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(artifact, sort_keys=True))
    print(s16a.FINAL_CERTIFICATION_MARKER)


if __name__ == "__main__":
    main()
