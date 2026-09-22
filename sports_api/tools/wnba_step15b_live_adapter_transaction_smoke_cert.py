"""Deterministic certification artifact for WNBA Step 15B."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path

from sports_api import wnba_step15b_live_adapter_transaction_smoke as s15b

CERT_FILE = "step15b-live-adapter-transaction-smoke-cert.json"


def safe_env() -> dict[str, str]:
    return {
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
        "WNBA_PRODUCTION_RUNTIME_ENABLED": "false",
        "WNBA_BOARD_SCHEDULER_ENABLED": "false",
        "WNBA_PERSISTENCE_ENABLED": "false",
        "WNBA_SUPABASE_WRITE_ENABLED": "false",
        "WNBA_WAGERING_ENABLED": "false",
        "WNBA_PUBLIC_STEP11E_FASTAPI_ENABLED": "false",
        "WNBA_STEP12_SCHEDULER_ENABLED": "false",
    }


def main() -> None:
    evidence = s15b.validate_step15b_live_evidence(s15b.load_step15b_live_evidence())
    sql_fingerprints = s15b.validate_frozen_sql_fingerprints()
    manifest = s15b.build_step15b_live_smoke_manifest(
        env=safe_env(),
        generated_at_utc="2026-08-28T19:30:00+00:00",
    )
    artifact = {
        "data_type": "wnba_step15b_live_adapter_transaction_smoke_certification",
        "schema_version": s15b.SCHEMA_VERSION,
        "integration_version": s15b.INTEGRATION_VERSION,
        "branch": s15b.BRANCH,
        "certified": True,
        "certified_at_utc": datetime.now(timezone.utc).isoformat(),
        "certified_head_sha": os.environ.get("GITHUB_SHA"),
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "expected_regression_tests": 560,
        "new_step15b_tests": 20,
        "smoke_content_sha256": manifest["smoke_content_sha256"],
        "live_evidence_content_sha256": s15b.LIVE_EVIDENCE_CONTENT_SHA256,
        "lineage": manifest["lineage"],
        "sql_fingerprints": sql_fingerprints,
        "live_transaction_certification": {
            "live_database_used": evidence["execution_boundary"]["live_database_used"],
            "frozen_adapter_sql_semantics_executed_live": evidence["execution_boundary"]["frozen_adapter_sql_semantics_executed_live"],
            "direct_psycopg_live_connection_certified": s15b.DIRECT_PSYCOG_LIVE_CONNECTION_CERTIFIED,
            "checkpoint_v1_create_and_load": True,
            "checkpoint_idempotency": True,
            "checkpoint_v2_advance": True,
            "checkpoint_stale_cas_rollback": True,
            "lease_contention": True,
            "lease_renew": True,
            "lease_expiry_takeover": True,
            "lease_fencing_generation_1_to_2": True,
            "stale_owner_release_blocked": True,
            "current_owner_release": True,
            "live_tables_empty_after_cleanup": evidence["cleanup"]["live_step14_tables_returned_to_empty_state"],
        },
        "activation_boundary": manifest["activation_contract"],
        "safety_contract": manifest["safety_contract"],
        "phase_boundary": manifest["phase_boundary"],
    }
    Path(CERT_FILE).write_text(
        json.dumps(artifact, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print("STEP15B_LIVE_ADAPTER_TRANSACTION_SMOKE_OK")
    print(json.dumps(artifact, sort_keys=True))


if __name__ == "__main__":
    main()
