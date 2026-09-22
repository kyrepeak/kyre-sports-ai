"""Deterministic certification for WNBA Step 15C final live persistence freeze."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path

from sports_api import wnba_step15_live_persistence_release_freeze as s15c

CERT_FILE = "step15c-final-live-persistence-freeze-cert.json"


def safe_env() -> dict[str, str]:
    env = {
        "WNBA_STEP15C_FINAL_LIVE_PERSISTENCE_FREEZE_ENABLED": "true",
        "WNBA_STEP15B_LIVE_ADAPTER_SMOKE_ENABLED": "true",
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
    }
    for key in (
        "WNBA_PRODUCTION_RUNTIME_ENABLED",
        "WNBA_BOARD_SCHEDULER_ENABLED",
        "WNBA_PERSISTENCE_ENABLED",
        "WNBA_SUPABASE_WRITE_ENABLED",
        "WNBA_WAGERING_ENABLED",
        "WNBA_PUBLIC_STEP11E_FASTAPI_ENABLED",
        "WNBA_STEP12_SCHEDULER_ENABLED",
    ):
        env[key] = "false"
    return env


def main() -> None:
    evidence = s15c.validate_step15c_final_live_evidence(s15c.load_step15c_final_live_evidence())
    manifest = s15c.build_step15c_release_manifest(
        env=safe_env(),
        generated_at_utc="2026-08-28T19:35:00+00:00",
    )
    artifact = {
        "data_type": "wnba_step15c_final_live_persistence_freeze_certification",
        "schema_version": s15c.SCHEMA_VERSION,
        "integration_version": s15c.INTEGRATION_VERSION,
        "release_id": s15c.RELEASE_ID,
        "branch": s15c.BRANCH,
        "certified": True,
        "certified_at_utc": datetime.now(timezone.utc).isoformat(),
        "certified_head_sha": os.environ.get("GITHUB_SHA"),
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "expected_regression_tests": 580,
        "new_step15c_tests": 20,
        "release_content_sha256": manifest["release_content_sha256"],
        "final_live_evidence_content_sha256": s15c.FINAL_LIVE_EVIDENCE_CONTENT_SHA256,
        "lineage": manifest["lineage"],
        "live_database_certification": {
            "live_schema_deployed": True,
            "live_transaction_semantics_certified": True,
            "final_tables_empty": all(value == 0 for value in evidence["live_final_state"]["row_counts"].values()),
            "migration_present": evidence["live_final_state"]["migration_present"],
            "project_status_at_freeze": evidence["supabase_project"]["status"],
            "live_database_used_inside_github_actions": False,
            "direct_psycopg_live_connection_certified": False,
        },
        "persistence_contract": manifest["persistence_contract"],
        "access_contract": manifest["access_contract"],
        "out_of_scope_contract": manifest["out_of_scope_contract"],
        "activation_contract": manifest["activation_contract"],
        "safety_contract": manifest["safety_contract"],
        "phase_boundary": manifest["phase_boundary"],
    }
    Path(CERT_FILE).write_text(json.dumps(artifact, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print("STEP15C_FINAL_LIVE_PERSISTENCE_FREEZE_OK")
    print(json.dumps(artifact, sort_keys=True))


if __name__ == "__main__":
    main()
