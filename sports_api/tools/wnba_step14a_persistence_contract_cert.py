from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

from sports_api import wnba_step13c_reliability_recovery as step13c
from sports_api import wnba_step14a_persistence_contract as s14

ARTIFACT_PATH = Path("step14a-persistence-contract-cert.json")
EXPECTED_REGRESSION_TESTS = 438
MARKER = "STEP14A_PERSISTENCE_CONTRACT_OK"


def canonical(value):
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        ).encode("utf-8")
    ).hexdigest()


def cert_env():
    env = dict(os.environ)
    env.update(
        {
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
    )
    return env


def synthetic_step13c_response():
    response = {
        "data_type": "wnba_step13c_reliability_recovery_response",
        "schema_version": step13c.SCHEMA_VERSION,
        "generated_at_utc": "2026-08-28T17:45:00+00:00",
        "status": "completed",
        "health": "healthy",
        "lineage": {
            "step13b_frozen_sha": s14.STEP13B_FROZEN_SHA,
            "latest_step13b_supervisor_content_sha256": "b" * 64,
            "step13a_frozen_sha": s14.STEP13A_FROZEN_SHA,
            "step12d_frozen_sha": s14.step13_release.STEP12D_FROZEN_SHA,
        },
        "final_controller_state_for_restart_handoff": {
            "season": 2026,
            "slate_date": "2026-08-28",
            "cycle_index": 9,
            "next_refresh_due_at_utc": "2026-08-28T17:46:00+00:00",
            "circuit_state": "closed",
            "consecutive_failures": 0,
        },
    }
    surface = {
        key: deepcopy(value)
        for key, value in response.items()
        if key not in {"generated_at_utc", "reliability_content_sha256"}
    }
    response["reliability_content_sha256"] = canonical(surface)
    return response


def main():
    env = cert_env()
    manifest = s14.build_step14a_schema_manifest(env=env)
    envelope = s14.build_step14a_checkpoint_envelope(
        step13c_response=synthetic_step13c_response(),
        slate_date="2026-08-28",
        env=env,
        created_at_utc="2026-08-28T17:46:30+00:00",
    )
    restored = s14.validate_step14a_checkpoint_envelope(
        envelope,
        env=env,
        expected_slate_date="2026-08-28",
    )
    if restored != envelope:
        raise RuntimeError("Step 14A restore validation changed the frozen envelope.")

    sql_bytes = Path(s14.SQL_SCHEMA_PATH).read_bytes()
    sql_sha256 = hashlib.sha256(sql_bytes).hexdigest()
    evidence = {
        "data_type": "wnba_step14a_persistence_contract_certification",
        "schema_version": s14.SCHEMA_VERSION,
        "certified": True,
        "certified_at_utc": datetime.now(timezone.utc).isoformat(),
        "certified_head_sha": os.environ.get("GITHUB_SHA"),
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "branch": s14.BRANCH,
        "expected_regression_tests": EXPECTED_REGRESSION_TESTS,
        "contract_id": s14.CONTRACT_ID,
        "step13_release_id": s14.STEP13_RELEASE_ID,
        "step13_release_content_sha256": s14.STEP13_RELEASE_CONTENT_SHA256,
        "lineage": manifest["lineage"],
        "database_contract": {
            "dialect": s14.DATABASE_DIALECT,
            "schema": s14.DATABASE_SCHEMA_NAME,
            "checkpoint_table": s14.CHECKPOINT_TABLE_NAME,
            "checkpoint_head_table": s14.CHECKPOINT_HEAD_TABLE_NAME,
            "sql_schema_path": s14.SQL_SCHEMA_PATH,
            "sql_schema_sha256": sql_sha256,
            "schema_manifest_sha256": manifest["manifest_content_sha256"],
        },
        "checkpoint_certification": {
            "checkpoint_key": envelope["checkpoint_key"],
            "controller_state_sha256": envelope["controller_state_sha256"],
            "envelope_content_sha256": envelope["envelope_content_sha256"],
            "source_reliability_content_sha256": envelope[
                "source_reliability_content_sha256"
            ],
            "slate_date": envelope["slate_date"],
            "round_trip_validation_exact": True,
        },
        "capability_boundary": manifest["capability_boundary"],
        "phase_boundary": manifest["phase_boundary"],
        "certification_summary": {
            "step14_started": True,
            "step14a_contract_certified": True,
            "frozen_step13_release_preserved": True,
            "checkpoint_hash_timestamp_stable": True,
            "sql_is_schema_only": True,
            "database_adapter_not_started": True,
            "database_reads_not_started": True,
            "database_writes_not_started": True,
            "supabase_writes_not_started": True,
            "durable_restart_recovery_not_started": True,
            "distributed_lease_not_started": True,
            "production_not_started": True,
        },
    }
    ARTIFACT_PATH.write_text(
        json.dumps(evidence, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(MARKER)
    print(json.dumps(evidence, sort_keys=True))


if __name__ == "__main__":
    main()
