from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from devsystem.execution_heartbeat_deadman_recovery_v1 import (
    consume_recovery_receipt,
    contract_self_test,
    heartbeat_worker,
    inspect_dead_man,
    issue_recovery_receipt,
    new_state,
    register_worker,
)

ROOT = Path(__file__).resolve().parents[1]
PACKET = "a" * 64


def _registered(ttl: int = 60):
    state = new_state("kyrepeak/kyre-sports-ai")
    out = register_worker(
        state,
        workstream_id="monster-v5-step4",
        owner_id="worker:a",
        scope_lease_id="scope:a",
        continuation_packet_hash=PACKET,
        authoritative_run_id=444,
        now_utc="2026-10-01T00:00:00Z",
        expected_revision=state["revision"],
        expected_state_hash=state["state_hash"],
        heartbeat_ttl_seconds=ttl,
    )
    assert out["result"]["allowed"] is True
    return out["state"]


def test_contract_self_test_green():
    result = contract_self_test()
    assert result["status"] == "GREEN"
    assert result["heartbeat_liveness"] is True
    assert result["running_job_blocks_takeover"] is True
    assert result["dead_worker_terminal_run_recoverable"] is True
    assert result["takeover_never_grants_mutation"] is True
    assert result["step_2a_remains_mandatory"] is True
    assert result["scope_lease_remains_mandatory"] is True
    assert result["recovery_receipt_one_shot"] is True
    assert result["product_runtime_mutation"] is False


def test_live_worker_cannot_be_taken_over():
    state = _registered()
    decision = inspect_dead_man(
        state,
        workstream_id="monster-v5-step4",
        continuation_packet_hash=PACKET,
        now_utc="2026-10-01T00:00:30Z",
        observed_run_state="failure",
    )
    assert decision["decision"] == "WORKER_HEARTBEAT_LIVE"
    assert decision["recovery_allowed"] is False


def test_expired_heartbeat_does_not_override_still_running_job():
    state = _registered()
    decision = inspect_dead_man(
        state,
        workstream_id="monster-v5-step4",
        continuation_packet_hash=PACKET,
        now_utc="2026-10-01T00:01:01Z",
        observed_run_state="in_progress",
    )
    assert decision["decision"] == "AUTHORITATIVE_RUN_STILL_ACTIVE"
    assert decision["recovery_allowed"] is False


def test_unknown_run_state_fails_closed():
    state = _registered()
    decision = inspect_dead_man(
        state,
        workstream_id="monster-v5-step4",
        continuation_packet_hash=PACKET,
        now_utc="2026-10-01T00:01:01Z",
        observed_run_state="mystery",
    )
    assert decision["decision"] == "RUN_STATE_UNKNOWN_FAIL_CLOSED"
    assert decision["recovery_allowed"] is False


def test_continuation_drift_blocks_recovery():
    state = _registered()
    decision = inspect_dead_man(
        state,
        workstream_id="monster-v5-step4",
        continuation_packet_hash="b" * 64,
        now_utc="2026-10-01T00:01:01Z",
        observed_run_state="failure",
    )
    assert decision["decision"] == "CONTINUATION_DRIFT_BLOCKED"


def test_recovery_requires_new_owner_and_new_scope_lease():
    state = _registered()
    blocked = issue_recovery_receipt(
        state,
        workstream_id="monster-v5-step4",
        continuation_packet_hash=PACKET,
        now_utc="2026-10-01T00:01:01Z",
        observed_run_state="failure",
        new_owner_id="worker:b",
        new_scope_lease_id="scope:a",
        expected_revision=state["revision"],
        expected_state_hash=state["state_hash"],
    )
    assert blocked["result"]["decision"] == "RECOVERY_REQUIRES_NEW_OWNER_AND_LEASE"
    assert blocked["result"]["allowed"] is False


def test_takeover_receipt_is_one_shot_and_has_no_mutation_authority():
    state = _registered()
    takeover = issue_recovery_receipt(
        state,
        workstream_id="monster-v5-step4",
        continuation_packet_hash=PACKET,
        now_utc="2026-10-01T00:01:01Z",
        observed_run_state="failure",
        new_owner_id="worker:b",
        new_scope_lease_id="scope:b",
        expected_revision=state["revision"],
        expected_state_hash=state["state_hash"],
    )
    assert takeover["result"]["grants_mutation_authority"] is False
    assert takeover["result"]["requires_step_2a"] is True
    assert takeover["result"]["requires_scope_lease"] is True

    recovered = takeover["state"]
    first = consume_recovery_receipt(
        recovered,
        receipt_id=takeover["result"]["receipt_id"],
        receipt_hash=takeover["result"]["receipt_hash"],
        workstream_id="monster-v5-step4",
        continuation_packet_hash=PACKET,
        expected_revision=recovered["revision"],
        expected_state_hash=recovered["state_hash"],
    )
    assert first["result"]["decision"] == "RECOVERY_RECEIPT_CONSUMED"
    assert first["result"]["mutation_authority"] is False

    replay_state = first["state"]
    replay = consume_recovery_receipt(
        replay_state,
        receipt_id=takeover["result"]["receipt_id"],
        receipt_hash=takeover["result"]["receipt_hash"],
        workstream_id="monster-v5-step4",
        continuation_packet_hash=PACKET,
        expected_revision=replay_state["revision"],
        expected_state_hash=replay_state["state_hash"],
    )
    assert replay["result"]["decision"] == "RECOVERY_RECEIPT_REPLAY_BLOCKED"


def test_stale_cas_fails_closed():
    state = _registered()
    result = heartbeat_worker(
        state,
        workstream_id="monster-v5-step4",
        owner_id="worker:a",
        scope_lease_id="scope:a",
        continuation_packet_hash=PACKET,
        now_utc="2026-10-01T00:00:30Z",
        expected_revision=0,
        expected_state_hash="0" * 64,
    )
    assert result["result"]["decision"] == "HEARTBEAT_STATE_STALE_CAS_CONTINUE"


def test_permanent_gate_and_ci_enforce_step4():
    permanent = (ROOT / "devsystem/permanent_gate_v1.py").read_text(encoding="utf-8")
    workflow = (ROOT / ".github/workflows/devsystem-targeted-ci.yml").read_text(encoding="utf-8")
    assert "devsystem/execution_heartbeat_deadman_recovery_v1.py" in permanent
    assert "tests/test_devsystem_execution_heartbeat_deadman_recovery_v1.py" in permanent
    assert "MONSTER_V5_EXECUTION_HEARTBEAT_DEADMAN_RECOVERY_GREEN" in permanent
    assert "python devsystem/execution_heartbeat_deadman_recovery_v1.py" in workflow
    assert "tests/test_devsystem_execution_heartbeat_deadman_recovery_v1.py" in workflow


def test_direct_script_execution_green():
    completed = subprocess.run(
        [sys.executable, str(ROOT / "devsystem/execution_heartbeat_deadman_recovery_v1.py")],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "MONSTER_V5_EXECUTION_HEARTBEAT_DEADMAN_RECOVERY_GREEN" in completed.stdout
