"""Deterministic certification artifact for WNBA Step 14D final persistence freeze."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from sports_api import wnba_step14a_persistence_contract as step14a
from sports_api import wnba_step14c_durable_restart_lease as step14c
from sports_api import wnba_step14_release_freeze as step14d

CERT_FILE = "step14d-final-persistence-freeze-cert.json"


def safe_env() -> dict[str, str]:
    true_keys = (
        "WNBA_STEP14D_FINAL_PERSISTENCE_FREEZE_ENABLED",
        "WNBA_STEP14C_DURABLE_RESTART_LEASE_ENABLED",
        "WNBA_STEP14B_DATABASE_CHECKPOINT_ADAPTER_ENABLED",
        "WNBA_STEP14B_DATABASE_READ_ENABLED",
        "WNBA_STEP14B_DATABASE_WRITE_ENABLED",
        "WNBA_STEP14A_PERSISTENCE_CONTRACT_ENABLED",
        "WNBA_STEP13D_FINAL_SCHEDULER_FREEZE_ENABLED",
        "WNBA_STEP13C_RELIABILITY_RECOVERY_ENABLED",
        "WNBA_STEP13B_RUNTIME_SUPERVISOR_ENABLED",
        "WNBA_STEP13A_BOUNDED_SCHEDULER_ENABLED",
        "WNBA_STEP12D_FINAL_RUNTIME_FREEZE_ENABLED",
        "WNBA_STEP12C_LIVE_BOARD_RUNTIME_ENABLED",
        "WNBA_STEP12B_LIVE_RUNTIME_ASSEMBLY_ENABLED",
        "WNBA_STEP12A_SHADOW_RUNNER_ENABLED",
        "WNBA_STEP11E_CONTROLLED_AUTOMATION_ENABLED",
    )
    false_keys = (
        "WNBA_PRODUCTION_RUNTIME_ENABLED",
        "WNBA_BOARD_SCHEDULER_ENABLED",
        "WNBA_KYRE_DIRECT_SYNC_ENABLED",
        "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
        "WNBA_STEP6J_CANARY_ENABLED",
        "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED",
        "WNBA_PERSISTENCE_ENABLED",
        "WNBA_SUPABASE_WRITE_ENABLED",
        "WNBA_WAGERING_ENABLED",
        "WNBA_PUBLIC_STEP11E_FASTAPI_ENABLED",
        "WNBA_STEP12_SCHEDULER_ENABLED",
    )
    env = {key: "true" for key in true_keys}
    env.update({key: "false" for key in false_keys})
    return env


def file_sha256(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def main() -> None:
    env = safe_env()
    first = step14d.build_step14d_release_manifest(
        env=env, generated_at_utc="2026-08-28T18:58:00+00:00"
    )
    second = step14d.build_step14d_release_manifest(
        env=env, generated_at_utc="2026-08-29T02:58:00+00:00"
    )

    require(first["release_content_sha256"] == second["release_content_sha256"],
            "Step 14D release hash changed with generation time")
    require(first["release_id"] == step14d.RELEASE_ID, "Step 14D release identity mismatch")
    require(all(value is False for value in first["safety_contract"].values()),
            "Step 14D safety contract contains an enabled unsafe capability")
    require(first["phase_boundary"]["step14_complete"] is True,
            "Step 14D phase boundary did not close Step 14")
    require(first["phase_boundary"]["production_activation_not_started"] is True,
            "Step 14D unexpectedly activated production")
    require(first["persistence_contract"]["durable_restart_recovery"] is True,
            "Step 14D restart recovery not certified")
    require(first["persistence_contract"]["durable_distributed_lease"] is True,
            "Step 14D distributed lease not certified")
    require(first["persistence_contract"]["monotonic_fencing_generation"] is True,
            "Step 14D fencing generation not certified")
    require(first["persistence_contract"]["checkpoint_head_compare_and_swap"] is True,
            "Step 14D checkpoint CAS not certified")
    require(first["activation_contract"]["explicit_foreground_invocation_required"] is True,
            "Step 14D explicit foreground boundary missing")
    require(first["activation_contract"]["global_persistence_runtime_enabled"] is False,
            "Step 14D global persistence runtime unexpectedly enabled")

    step14a_sql_hash = file_sha256(step14a.SQL_SCHEMA_PATH)
    step14c_sql_hash = file_sha256(step14c.LEASE_SQL_SCHEMA_PATH)
    require(step14a_sql_hash == step14d.STEP14A_SQL_SCHEMA_SHA256,
            "Step 14D frozen Step-14A SQL hash mismatch")
    require(step14c_sql_hash == step14d.STEP14C_LEASE_SQL_SCHEMA_SHA256,
            "Step 14D frozen Step-14C lease SQL hash mismatch")

    artifact: dict[str, Any] = {
        "data_type": "wnba_step14d_final_persistence_freeze_certification",
        "schema_version": step14d.SCHEMA_VERSION,
        "integration_version": step14d.INTEGRATION_VERSION,
        "release_id": step14d.RELEASE_ID,
        "release_content_sha256": first["release_content_sha256"],
        "branch": step14d.BRANCH,
        "certified": True,
        "certified_at_utc": datetime.now(timezone.utc).isoformat(),
        "certified_head_sha": os.environ.get("GITHUB_SHA"),
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "expected_regression_tests": 520,
        "new_step14d_tests": 20,
        "lineage": first["lineage"],
        "schema_evidence": {
            "step14a_sql_schema_sha256": step14a_sql_hash,
            "step14c_lease_sql_schema_sha256": step14c_sql_hash,
            "step14a_manifest_content_sha256": step14d.STEP14A_MANIFEST_CONTENT_SHA256,
        },
        "persistence_certification": first["persistence_contract"],
        "activation_boundary": first["activation_contract"],
        "safety_contract": first["safety_contract"],
        "phase_boundary": first["phase_boundary"],
        "certification_transport": {
            "live_database_used": False,
            "database_credentials_required": False,
            "release_manifest_is_read_only": True,
            "runtime_executed": False,
        },
    }
    Path(CERT_FILE).write_text(
        json.dumps(artifact, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )
    print("STEP14D_FINAL_PERSISTENCE_FREEZE_OK")
    print(json.dumps(artifact, sort_keys=True))


if __name__ == "__main__":
    main()
