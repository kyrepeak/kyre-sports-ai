"""Deterministic certification for WNBA Step 15A live PostgreSQL preflight."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path

from sports_api import wnba_step15a_live_postgres_preflight as s15a

CERT_FILE = "step15a-live-postgres-preflight-cert.json"


def safe_env() -> dict[str, str]:
    return {
        "WNBA_STEP15A_LIVE_POSTGRES_PREFLIGHT_ENABLED": "true",
        "WNBA_STEP14D_FINAL_PERSISTENCE_FREEZE_ENABLED": "true",
        "WNBA_STEP14C_DURABLE_RESTART_LEASE_ENABLED": "true",
        "WNBA_STEP14B_DATABASE_CHECKPOINT_ADAPTER_ENABLED": "true",
        "WNBA_STEP14B_DATABASE_READ_ENABLED": "true",
        "WNBA_STEP14B_DATABASE_WRITE_ENABLED": "true",
        "WNBA_STEP14A_PERSISTENCE_CONTRACT_ENABLED": "true",
        "WNBA_STEP13D_FINAL_SCHEDULER_FREEZE_ENABLED": "true",
        "WNBA_STEP13C_RELIABILITY_RECOVERY_ENABLED": "true",
        "WNBA_STEP13B_RUNTIME_SUPERVISOR_ENABLED": "true",
        "WNBA_STEP13A_BOUNDED_SCHEDULER_ENABLED": "true",
        "WNBA_STEP12D_FINAL_RUNTIME_FREEZE_ENABLED": "true",
        "WNBA_STEP12C_LIVE_BOARD_RUNTIME_ENABLED": "true",
        "WNBA_STEP12B_LIVE_RUNTIME_ASSEMBLY_ENABLED": "true",
        "WNBA_STEP12A_SHADOW_RUNNER_ENABLED": "true",
        "WNBA_STEP11E_CONTROLLED_AUTOMATION_ENABLED": "true",
        "WNBA_PRODUCTION_RUNTIME_ENABLED": "false",
        "WNBA_BOARD_SCHEDULER_ENABLED": "false",
        "WNBA_PERSISTENCE_ENABLED": "false",
        "WNBA_SUPABASE_WRITE_ENABLED": "false",
        "WNBA_WAGERING_ENABLED": "false",
        "WNBA_PUBLIC_STEP11E_FASTAPI_ENABLED": "false",
        "WNBA_STEP12_SCHEDULER_ENABLED": "false",
    }


def main() -> None:
    env = safe_env()
    evidence = s15a.validate_step15a_live_evidence(s15a.load_step15a_live_evidence())
    manifest = s15a.build_step15a_live_preflight_manifest(
        env=env,
        generated_at_utc="2026-08-28T19:20:00+00:00",
    )
    artifact = {
        "data_type": "wnba_step15a_live_postgres_preflight_certification",
        "schema_version": s15a.SCHEMA_VERSION,
        "integration_version": s15a.INTEGRATION_VERSION,
        "branch": s15a.BRANCH,
        "certified": True,
        "certified_at_utc": datetime.now(timezone.utc).isoformat(),
        "certified_head_sha": os.environ.get("GITHUB_SHA"),
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "expected_regression_tests": 540,
        "new_step15a_tests": 20,
        "preflight_content_sha256": manifest["preflight_content_sha256"],
        "live_evidence_content_sha256": s15a.LIVE_EVIDENCE_CONTENT_SHA256,
        "lineage": manifest["lineage"],
        "live_database_certification": {
            "live_database_used_during_step15a_preflight": True,
            "live_database_used_inside_github_actions": False,
            "supabase_project_ref": evidence["supabase_project"]["ref"],
            "supabase_project_status": evidence["supabase_project"]["status"],
            "postgres_engine": evidence["supabase_project"]["postgres_engine"],
            "migration_version": evidence["migration"]["version"],
            "migration_name": evidence["migration"]["name"],
            "schema_name": evidence["live_schema"]["schema_name"],
            "all_three_tables_present": len(evidence["live_schema"]["tables"]) == 3,
            "all_tables_empty_at_certification": evidence["live_schema"]["all_tables_empty_at_certification"],
            "frozen_step14_ddl_reused_without_modification": True,
        },
        "access_boundary": manifest["access_contract"],
        "activation_boundary": manifest["activation_contract"],
        "safety_contract": manifest["safety_contract"],
        "phase_boundary": manifest["phase_boundary"],
    }
    Path(CERT_FILE).write_text(
        json.dumps(artifact, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print("STEP15A_LIVE_POSTGRES_PREFLIGHT_OK")
    print(json.dumps(artifact, sort_keys=True))


if __name__ == "__main__":
    main()
