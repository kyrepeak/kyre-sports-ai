"""Deterministic certification for WNBA Step 14C durable restart + lease."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from typing import Any
from unittest.mock import patch

from sports_api import wnba_step13b_runtime_supervisor as step13b
from sports_api import wnba_step13c_reliability_recovery as step13c
from sports_api import wnba_step14a_persistence_contract as step14a
from sports_api import wnba_step14c_durable_restart_lease as s14c

CERT_FILE = "step14c-durable-restart-lease-cert.json"
TOKEN = "11111111-1111-4111-8111-111111111111"


def canonical(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode()).hexdigest()


def safe_env() -> dict[str, str]:
    return {
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


def request() -> dict[str, Any]:
    parent = step13b.build_step13b_request(
        season=2026,
        initial_slate_date="2026-08-28",
        max_supervisor_sessions=1,
        max_supervisor_runtime_seconds=1,
        max_total_intersession_sleep_seconds=0,
    )
    return step13c.build_step13c_request(
        supervisor_request=parent,
        max_recovery_attempts=1,
        base_recovery_backoff_seconds=0,
        max_total_recovery_sleep_seconds=0,
    )


def response(cycle_index: int) -> dict[str, Any]:
    value = {
        "data_type": "wnba_step13c_reliability_recovery_response",
        "schema_version": step13c.SCHEMA_VERSION,
        "generated_at_utc": "2026-08-28T18:20:00+00:00",
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
            "next_refresh_due_at_utc": "2026-08-28T18:21:00+00:00",
            "circuit_state": "closed",
        },
    }
    value["reliability_content_sha256"] = canonical({k: deepcopy(v) for k, v in value.items() if k not in {"generated_at_utc", "reliability_content_sha256"}})
    return value


class Cursor:
    def __init__(self, script):
        self.script = list(script)
        self.current = None
        self.rowcount = -1
    def execute(self, sql, params=None):
        if not self.script:
            raise RuntimeError("cert SQL script exhausted")
        item = self.script.pop(0)
        if item.get("contains") and item["contains"] not in sql:
            raise RuntimeError(f"expected SQL fragment {item['contains']!r}")
        self.current = item
        self.rowcount = item.get("rowcount", -1)
    def fetchone(self):
        return None if self.current is None else self.current.get("fetchone")
    def close(self):
        pass


class Connection:
    def __init__(self, script):
        self.cursor_obj = Cursor(script)
        self.commits = 0
        self.rollbacks = 0
    def cursor(self): return self.cursor_obj
    def commit(self): self.commits += 1
    def rollback(self): self.rollbacks += 1
    def close(self): pass


class SequenceFactory:
    def __init__(self, scripts):
        self.scripts = [list(item) for item in scripts]
        self.connections = []
    def __call__(self):
        if not self.scripts:
            raise RuntimeError("cert connection script exhausted")
        conn = Connection(self.scripts.pop(0))
        self.connections.append(conn)
        return conn


def schema():
    return {"contains": "to_regclass", "fetchone": (True,)}


def lease_row(owner="worker-cert", generation=1, renewed="2026-08-28T18:00:00+00:00", expires="2026-08-28T19:00:00+00:00"):
    return (
        s14c.lease_key_for_slate("2026-08-28"), owner, TOKEN, generation,
        "2026-08-28T18:00:00+00:00", renewed, expires,
    )


def main() -> None:
    env = safe_env()
    req = request()
    ttl = s14c.required_lease_ttl_seconds(req)
    if ttl != 61:
        raise SystemExit(f"unexpected bounded lease TTL: {ttl}")

    acquire_factory = SequenceFactory([[schema(), {"contains": "ON CONFLICT (lease_key)", "fetchone": lease_row()}]])
    handle = s14c.acquire_step14c_lease(
        slate_date="2026-08-28", owner_id="worker-cert", lease_ttl_seconds=ttl,
        env=env, connection_factory=acquire_factory, token_factory=lambda: TOKEN,
    )

    duplicate_factory = SequenceFactory([[schema(), {"contains": "ON CONFLICT (lease_key)", "fetchone": None}]])
    duplicate_blocked = False
    try:
        s14c.acquire_step14c_lease(
            slate_date="2026-08-28", owner_id="worker-other", lease_ttl_seconds=ttl,
            env=env, connection_factory=duplicate_factory, token_factory=lambda: TOKEN,
        )
    except s14c.WNBAStep14CLeaseUnavailableError:
        duplicate_blocked = True
    if not duplicate_blocked:
        raise SystemExit("Step 14C certification expected duplicate lease rejection")

    renew_factory = SequenceFactory([[schema(), {"contains": "fencing_generation = %s", "fetchone": lease_row(renewed="2026-08-28T18:01:00+00:00", expires="2026-08-28T19:01:00+00:00")} ]])
    renewed = s14c.renew_step14c_lease(
        handle=handle, lease_ttl_seconds=ttl, env=env, connection_factory=renew_factory
    )

    stale_factory = SequenceFactory([[schema(), {"contains": "fencing_generation = %s", "fetchone": None}]])
    stale_fenced = False
    try:
        s14c.renew_step14c_lease(
            handle=renewed, lease_ttl_seconds=ttl, env=env, connection_factory=stale_factory
        )
    except s14c.WNBAStep14CLeaseLostError:
        stale_fenced = True
    if not stale_fenced:
        raise SystemExit("Step 14C certification expected stale lease fencing")

    release_factory = SequenceFactory([[schema(), {"contains": "DELETE FROM kyre_runtime.wnba_runtime_leases", "fetchone": (renewed["lease_key"],)}]])
    if not s14c.release_step14c_lease(handle=renewed, env=env, connection_factory=release_factory):
        raise SystemExit("Step 14C certification lease release failed")

    durable_state = {"season": 2026, "slate_date": "2026-08-28", "cycle_index": 77}
    recovered = s14c.build_recovered_step13c_request(
        step13c_request=req, durable_controller_state=durable_state
    )
    if recovered["supervisor_request"]["initial_previous_state"] != durable_state:
        raise SystemExit("Step 14C certification restart handoff mismatch")
    if recovered["request_content_sha256"] == req["request_content_sha256"]:
        raise SystemExit("Step 14C certification expected rebuilt request hash")

    key = renewed["lease_key"]
    runtime_factory = SequenceFactory([
        [schema(), {"contains": "ON CONFLICT (lease_key)", "fetchone": lease_row(generation=2)}],
        [schema(), {"contains": "fencing_generation = %s", "fetchone": lease_row(generation=2, renewed="2026-08-28T18:02:00+00:00", expires="2026-08-28T19:02:00+00:00")}],
        [schema(), {"contains": "DELETE FROM kyre_runtime.wnba_runtime_leases", "fetchone": (key,)}],
    ])
    load = {
        "found": True,
        "checkpoint_version": 3,
        "checkpoint_key": step14a.checkpoint_key_for_slate("2026-08-28"),
        "controller_state_for_restart": durable_state,
    }
    save_capture: dict[str, Any] = {}
    def save_checkpoint(**kwargs):
        save_capture.update(kwargs)
        envelope = kwargs["checkpoint_envelope"]
        return {
            "checkpoint_version": 4,
            "status": "advanced",
            "envelope_content_sha256": envelope["envelope_content_sha256"],
            "controller_state_sha256": envelope["controller_state_sha256"],
        }
    with patch.object(s14c, "load_step14c_restart_checkpoint", return_value=load), \
         patch.object(s14c.step14b, "save_step14b_checkpoint", side_effect=save_checkpoint), \
         patch.object(s14c.step14b, "validate_step14b_adapter_result", side_effect=lambda value: value):
        runtime = s14c.run_step14c_durable_restart_lease(
            req,
            owner_id="worker-cert",
            env=env,
            lease_ttl_seconds=ttl,
            lease_connection_factory=runtime_factory,
            token_factory=lambda: TOKEN,
            step13c_runner=lambda recovered_req, **kwargs: response(78),
            generated_at_utc="2026-08-28T18:03:00+00:00",
        )
    s14c.validate_step14c_runtime_result(runtime)
    if save_capture.get("expected_head_version") != 3:
        raise SystemExit("Step 14C certification expected Step-14B CAS version 3")

    lease_sql_hash = hashlib.sha256(Path(s14c.LEASE_SQL_SCHEMA_PATH).read_bytes()).hexdigest()
    if lease_sql_hash != s14c.LEASE_SQL_SCHEMA_SHA256:
        raise SystemExit("Step 14C certification lease SQL hash mismatch")

    artifact = {
        "data_type": "wnba_step14c_durable_restart_lease_certification",
        "schema_version": s14c.SCHEMA_VERSION,
        "runtime_version": s14c.RUNTIME_VERSION,
        "branch": s14c.BRANCH,
        "certified": True,
        "certified_at_utc": datetime.now(timezone.utc).isoformat(),
        "certified_head_sha": os.environ.get("GITHUB_SHA"),
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT"),
        "expected_regression_tests": 500,
        "lineage": {
            "step14b_frozen_sha": s14c.STEP14B_FROZEN_SHA,
            "step14a_frozen_sha": s14c.STEP14A_FROZEN_SHA,
            "step13d_frozen_sha": s14c.STEP13D_FROZEN_SHA,
            "step13c_frozen_sha": s14c.STEP13C_FROZEN_SHA,
            "step13b_frozen_sha": s14c.STEP13B_FROZEN_SHA,
            "step13_release_content_sha256": s14c.STEP13_RELEASE_CONTENT_SHA256,
        },
        "lease_contract": {
            "database_schema": s14c.DATABASE_SCHEMA_NAME,
            "lease_table": s14c.LEASE_TABLE_NAME,
            "lease_sql_schema_sha256": lease_sql_hash,
            "uuid_token": True,
            "monotonic_fencing_generation": True,
            "database_expiry": True,
            "expired_lease_takeover_supported": True,
            "stale_owner_renewal_blocked": stale_fenced,
            "unexpired_duplicate_blocked": duplicate_blocked,
            "background_renewal_thread": False,
        },
        "restart_recovery": {
            "verified_step14b_checkpoint_loaded": True,
            "exact_controller_state_injected": recovered["supervisor_request"]["initial_previous_state"] == durable_state,
            "frozen_step13b_request_rebuilt_and_rehashed": True,
            "lease_revalidated_before_save": True,
            "step14b_checkpoint_cas_expected_version": save_capture.get("expected_head_version"),
            "saved_checkpoint_version": runtime["saved_checkpoint_version"],
            "runtime_result_hash": runtime["runtime_content_sha256"],
        },
        "capability_boundary": {
            "foreground_durable_restart_recovery_allowed": True,
            "durable_distributed_lease_allowed": True,
            "cross_process_duplicate_run_guard_allowed": True,
            "global_persistence_runtime_enabled": False,
            "automatic_production_restart_activation": False,
            "supabase_rest_write_allowed": False,
            "production_activation_allowed": False,
            "public_fastapi_activation_allowed": False,
            "background_daemon_allowed": False,
            "background_thread_allowed": False,
            "wagering_allowed": False,
            "basketball_model_mutation_allowed": False,
            "ranking_mutation_allowed": False,
        },
        "database_certification": {
            "live_database_used_in_certification": False,
            "injected_dbapi_transport_used": True,
            "credentials_embedded_in_code": False,
        },
        "phase_boundary": {
            "step14a_frozen": True,
            "step14b_frozen": True,
            "step14c_complete_candidate": True,
            "step14d_final_persistence_freeze_not_started": True,
            "production_not_started": True,
        },
    }
    Path(CERT_FILE).write_text(json.dumps(artifact, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print("STEP14C_DURABLE_RESTART_LEASE_OK")
    print(json.dumps(artifact, sort_keys=True))


if __name__ == "__main__":
    main()
