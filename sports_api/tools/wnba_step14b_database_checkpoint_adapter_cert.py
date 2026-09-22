"""Deterministic certification for WNBA Step 14B database checkpoint adapter."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any

from sports_api import wnba_step13c_reliability_recovery as step13c
from sports_api import wnba_step14a_persistence_contract as step14a
from sports_api import wnba_step14b_database_checkpoint_adapter as s14b

CERT_FILE = "step14b-database-checkpoint-adapter-cert.json"


def canonical(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=str,
        ).encode("utf-8")
    ).hexdigest()


def safe_env() -> dict[str, str]:
    return {
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


def source_response(cycle_index: int) -> dict[str, Any]:
    response = {
        "data_type": "wnba_step13c_reliability_recovery_response",
        "schema_version": step13c.SCHEMA_VERSION,
        "generated_at_utc": "2026-08-28T18:00:00+00:00",
        "status": "completed",
        "health": "healthy",
        "lineage": {
            "step13b_frozen_sha": step14a.STEP13B_FROZEN_SHA,
            "latest_step13b_supervisor_content_sha256": "a" * 64,
            "step13a_frozen_sha": step14a.STEP13A_FROZEN_SHA,
            "step12d_frozen_sha": step14a.step13_release.STEP12D_FROZEN_SHA,
        },
        "final_controller_state_for_restart_handoff": {
            "season": 2026,
            "slate_date": "2026-08-28",
            "cycle_index": cycle_index,
            "next_refresh_due_at_utc": f"2026-08-28T18:{cycle_index:02d}:00+00:00",
            "circuit_state": "closed",
        },
    }
    surface = {
        k: deepcopy(v)
        for k, v in response.items()
        if k not in {"generated_at_utc", "reliability_content_sha256"}
    }
    response["reliability_content_sha256"] = canonical(surface)
    return response


def make_envelope(cycle_index: int, created: str) -> dict[str, Any]:
    return step14a.build_step14a_checkpoint_envelope(
        step13c_response=source_response(cycle_index),
        slate_date="2026-08-28",
        env=safe_env(),
        created_at_utc=created,
    )


def head_row(envelope: dict[str, Any], version: int) -> tuple[Any, ...]:
    cid = s14b.checkpoint_id_for_envelope(envelope)
    return (
        version,
        cid,
        envelope["envelope_content_sha256"],
        version,
        cid,
        envelope["checkpoint_key"],
        envelope["slate_date"],
        envelope["step13d_frozen_sha"],
        envelope["step13_release_id"],
        envelope["step13_release_content_sha256"],
        envelope["source_step13c_frozen_sha"],
        envelope["source_reliability_content_sha256"],
        envelope["controller_state_sha256"],
        envelope["envelope_content_sha256"],
        deepcopy(envelope),
    )


class ScriptCursor:
    def __init__(self, script):
        self.script = list(script)
        self.current = None
        self.rowcount = -1
        self.closed = False

    def execute(self, sql, params=None):
        if not self.script:
            raise RuntimeError("certification SQL script exhausted")
        step = self.script.pop(0)
        fragment = step.get("contains")
        if fragment and fragment not in sql:
            raise RuntimeError(f"unexpected SQL; required fragment {fragment!r}")
        if "raise" in step:
            raise step["raise"]
        self.current = step
        self.rowcount = step.get("rowcount", -1)

    def fetchone(self):
        return self.current.get("fetchone") if self.current is not None else None

    def close(self):
        self.closed = True


class ScriptConnection:
    def __init__(self, script):
        self.cursor_obj = ScriptCursor(script)
        self.commits = 0
        self.rollbacks = 0
        self.closed = False

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1

    def close(self):
        self.closed = True


def factory(script):
    box = {}

    def create():
        conn = ScriptConnection(script)
        box["connection"] = conn
        return conn

    return create, box


def schema_step():
    return {"contains": "to_regclass", "fetchone": (True, True)}


def main() -> None:
    env = safe_env()
    envelope_v1 = make_envelope(7, "2026-08-28T18:00:00+00:00")
    envelope_v2 = make_envelope(8, "2026-08-28T18:01:00+00:00")
    envelope_v3 = make_envelope(9, "2026-08-28T18:02:00+00:00")

    create_factory, create_box = factory(
        [
            schema_step(),
            {"contains": "FOR UPDATE OF h", "fetchone": None},
            {"contains": "INSERT INTO kyre_runtime.wnba_runtime_checkpoints", "rowcount": 1},
            {"contains": "INSERT INTO kyre_runtime.wnba_runtime_checkpoint_heads", "rowcount": 1},
        ]
    )
    save_v1 = s14b.save_step14b_checkpoint(
        checkpoint_envelope=envelope_v1,
        expected_head_version=0,
        env=env,
        connection_factory=create_factory,
        generated_at_utc="2026-08-28T18:00:30+00:00",
    )
    s14b.validate_step14b_adapter_result(save_v1)

    load_factory, load_box = factory(
        [schema_step(), {"contains": "JOIN kyre_runtime.wnba_runtime_checkpoints", "fetchone": head_row(envelope_v1, 1)}]
    )
    load_v1 = s14b.load_step14b_checkpoint(
        slate_date="2026-08-28",
        env=env,
        connection_factory=load_factory,
        generated_at_utc="2026-08-28T18:00:40+00:00",
    )
    s14b.validate_step14b_adapter_result(load_v1)

    advance_factory, advance_box = factory(
        [
            schema_step(),
            {"contains": "FOR UPDATE OF h", "fetchone": head_row(envelope_v1, 1)},
            {"contains": "INSERT INTO kyre_runtime.wnba_runtime_checkpoints", "rowcount": 1},
            {"contains": "UPDATE kyre_runtime.wnba_runtime_checkpoint_heads", "rowcount": 1},
        ]
    )
    save_v2 = s14b.save_step14b_checkpoint(
        checkpoint_envelope=envelope_v2,
        expected_head_version=1,
        env=env,
        connection_factory=advance_factory,
        generated_at_utc="2026-08-28T18:01:30+00:00",
    )
    s14b.validate_step14b_adapter_result(save_v2)

    idempotent_factory, idempotent_box = factory(
        [schema_step(), {"contains": "FOR UPDATE OF h", "fetchone": head_row(envelope_v2, 2)}]
    )
    idempotent_v2 = s14b.save_step14b_checkpoint(
        checkpoint_envelope=envelope_v2,
        expected_head_version=0,
        env=env,
        connection_factory=idempotent_factory,
        generated_at_utc="2026-08-28T18:01:40+00:00",
    )
    s14b.validate_step14b_adapter_result(idempotent_v2)

    conflict_factory, conflict_box = factory(
        [schema_step(), {"contains": "FOR UPDATE OF h", "fetchone": head_row(envelope_v2, 2)}]
    )
    conflict_detected = False
    try:
        s14b.save_step14b_checkpoint(
            checkpoint_envelope=envelope_v3,
            expected_head_version=1,
            env=env,
            connection_factory=conflict_factory,
            generated_at_utc="2026-08-28T18:02:30+00:00",
        )
    except s14b.WNBAStep14DatabaseConflictError:
        conflict_detected = True
    if not conflict_detected:
        raise SystemExit("Step 14B certification expected stale-writer CAS conflict")

    schema_factory, schema_box = factory([schema_step()])
    schema_check = s14b.verify_step14b_database_schema(
        env=env,
        connection_factory=schema_factory,
        generated_at_utc="2026-08-28T18:03:00+00:00",
    )

    req_text = Path("sports_api/requirements-persistence.txt").read_text(encoding="utf-8")
    if "psycopg[binary]" not in req_text:
        raise SystemExit("Step 14B persistence requirements missing psycopg 3")

    artifact = {
        "data_type": "wnba_step14b_database_checkpoint_adapter_certification",
        "schema_version": s14b.SCHEMA_VERSION,
        "adapter_version": s14b.ADAPTER_VERSION,
        "branch": s14b.BRANCH,
        "certified": True,
        "certified_at_utc": datetime.now(timezone.utc).isoformat(),
        "certified_head_sha": os.environ.get("GITHUB_SHA"),
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "expected_regression_tests": 465,
        "lineage": {
            "step14a_frozen_sha": s14b.STEP14A_FROZEN_SHA,
            "step14a_contract_id": s14b.STEP14A_CONTRACT_ID,
            "step14a_manifest_content_sha256": s14b.STEP14A_MANIFEST_CONTENT_SHA256,
            "step14a_sql_schema_sha256": s14b.STEP14A_SQL_SCHEMA_SHA256,
            "step13_release_content_sha256": s14b.STEP13_RELEASE_CONTENT_SHA256,
        },
        "database_contract": {
            "dialect": "postgresql",
            "schema": s14b.DATABASE_SCHEMA_NAME,
            "checkpoint_table": s14b.CHECKPOINT_TABLE_NAME,
            "checkpoint_head_table": s14b.CHECKPOINT_HEAD_TABLE_NAME,
            "append_only_history": True,
            "head_compare_and_swap": True,
            "deterministic_checkpoint_uuid_v5": True,
            "supabase_postgres_compatible": True,
            "live_database_used_in_certification": False,
            "injected_dbapi_transport_used": True,
        },
        "operation_certification": {
            "create_status": save_v1["status"],
            "create_version": save_v1["checkpoint_version"],
            "create_result_hash": save_v1["adapter_content_sha256"],
            "load_status": load_v1["status"],
            "load_round_trip_exact": load_v1["checkpoint_envelope"] == envelope_v1,
            "advance_status": save_v2["status"],
            "advance_version": save_v2["checkpoint_version"],
            "advance_result_hash": save_v2["adapter_content_sha256"],
            "idempotent_status": idempotent_v2["status"],
            "idempotent_appended_no_history": len(idempotent_box["connection"].cursor_obj.script) == 0,
            "stale_writer_conflict_detected": conflict_detected,
            "conflict_rollback_count": conflict_box["connection"].rollbacks,
            "schema_check_hash": schema_check["schema_check_content_sha256"],
        },
        "checkpoint_identity": {
            "checkpoint_key": envelope_v1["checkpoint_key"],
            "v1_checkpoint_id": save_v1["checkpoint_id"],
            "v2_checkpoint_id": save_v2["checkpoint_id"],
            "v1_envelope_hash": envelope_v1["envelope_content_sha256"],
            "v2_envelope_hash": envelope_v2["envelope_content_sha256"],
        },
        "transaction_evidence": {
            "create_commits": create_box["connection"].commits,
            "load_rollbacks": load_box["connection"].rollbacks,
            "advance_commits": advance_box["connection"].commits,
            "idempotent_commits": idempotent_box["connection"].commits,
            "schema_check_rollbacks": schema_box["connection"].rollbacks,
        },
        "capability_boundary": {
            "database_read_adapter_certified": True,
            "database_write_adapter_certified": True,
            "persistence_runtime_enabled": False,
            "durable_restart_recovery_allowed": False,
            "distributed_lease_allowed": False,
            "cross_process_duplicate_run_guard_allowed": False,
            "supabase_rest_write_allowed": False,
            "production_activation_allowed": False,
            "public_fastapi_activation_allowed": False,
            "wagering_allowed": False,
        },
        "phase_boundary": {
            "step14a_contract_frozen": True,
            "step14b_database_adapter_complete_candidate": True,
            "step14c_restart_recovery_not_started": True,
            "step14c_distributed_lease_not_started": True,
            "production_not_started": True,
        },
    }
    Path(CERT_FILE).write_text(
        json.dumps(artifact, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print("STEP14B_DATABASE_CHECKPOINT_ADAPTER_OK")
    print(json.dumps(artifact, sort_keys=True))


if __name__ == "__main__":
    main()
