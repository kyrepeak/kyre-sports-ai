from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from devsystem.mandatory_2a_action_gate_v1 import (
    Mandatory2AActionGateFailure,
    authorize_action,
    contract_self_test,
    require_authorized,
)
from devsystem.action_ledger_v2 import build_receipt
from devsystem.forward_motion_v2 import fingerprint_action
from devsystem.persistent_execution_brain_v1 import BrainStateInput, build_state
from devsystem.automatic_loop_kill_v1 import fingerprint_control_cycle


def _brain(*, waiting: bool = False):
    return build_state(BrainStateInput(
        program_id="test",
        program_title="2A mandatory gate",
        total_steps=2,
        current_step=1,
        step_title="Mandatory Action Gate",
        execution_state="WAITING_ON_ASYNC" if waiting else "ACTIVE",
        repository="owner/repo",
        main_sha="1" * 40,
        work_branch="gate",
        observed_head_sha="2" * 40,
        next_legal_action="Continue safely.",
        completed_steps=(),
        frozen_steps=(),
        remaining_steps=(2,),
        authoritative_run_id=9001 if waiting else None,
        authoritative_job_id=7001 if waiting else None,
        async_state="IN_PROGRESS" if waiting else "NONE",
        updated_at_utc="2026-09-30T03:20:00Z",
    ))


def _action(action_type="merge", target="github:pr/1"):
    return {
        "task_id": "test",
        "checkpoint_id": "1",
        "action_type": action_type,
        "target": target,
        "inputs": {"head": "2" * 40},
    }


def _forward(action):
    return {
        "decision": "AUTHORIZED",
        "receipt": build_receipt({
            "policy_version": 2,
            "task_id": action["task_id"],
            "checkpoint_id": action["checkpoint_id"],
            "action_fingerprint": fingerprint_action(action),
            "root_cause_fingerprint": "r" * 64,
            "evidence_fingerprint": "e" * 64,
            "relevant_input_fingerprint": "i" * 64,
            "decision": "AUTHORIZED",
            "previous_chain_hash": "0" * 64,
            "event_nonce": "test-gate",
            "override_event_id": None,
        }),
    }


def test_non_async_mutation_without_authorization_fails_closed():
    result = authorize_action(_brain(), _action("merge"), [])
    assert result["decision"] == "TWO_A_AUTHORIZATION_REQUIRED"
    assert result["allowed"] is False
    assert result["two_a_enforced"] is True


def test_matching_forward_motion_receipt_authorizes_exact_action():
    action = _action("update_branch", "github:branch/gate")
    result = authorize_action(_brain(), action, [], forward_decision=_forward(action))
    assert result["decision"] == "TWO_A_AUTHORIZED"
    assert result["allowed"] is True
    assert result["authorization_source"] == "forward_motion_v2"
    assert result["forward_receipt_hash"]


def test_receipt_for_different_action_cannot_be_reused():
    original = _action("merge", "github:pr/1")
    changed = _action("merge", "github:pr/2")
    result = authorize_action(_brain(), changed, [], forward_decision=_forward(original))
    assert result["allowed"] is False
    assert "exact action" in result["reason"]


def test_live_async_mutation_is_blocked_by_step2a():
    result = authorize_action(_brain(waiting=True), _action("patch", "github:mutation"), [])
    assert result["allowed"] is False
    assert result["source_decision"] == "ASYNC_LOCKED"
    assert result["authorization_source"] == "automatic_loop_kill_v1"


def test_first_async_observation_is_allowed_once():
    action = {
        "task_id": "test",
        "checkpoint_id": "1",
        "action_type": "observe_async",
        "target": "github:run/9001",
        "authoritative_run_id": 9001,
        "authoritative_job_id": 7001,
        "observed_async_state": "IN_PROGRESS",
        "evidence": {"run_id": 9001, "job_id": 7001, "state": "IN_PROGRESS"},
    }
    first = authorize_action(_brain(waiting=True), action, [])
    assert first["allowed"] is True
    assert first["source_decision"] == "AUTHORIZED_OBSERVE"


def test_duplicate_async_observation_is_skipped_without_user_intervention():
    action = {
        "task_id": "test",
        "checkpoint_id": "1",
        "action_type": "observe_async",
        "target": "github:run/9001",
        "authoritative_run_id": 9001,
        "authoritative_job_id": 7001,
        "observed_async_state": "IN_PROGRESS",
        "evidence": {"run_id": 9001, "job_id": 7001, "state": "IN_PROGRESS"},
    }
    history = [{"control_cycle_fingerprint": fingerprint_control_cycle(action)}]
    result = authorize_action(_brain(waiting=True), action, history)
    assert result["allowed"] is False
    assert result["source_decision"] == "LOOP_SKIPPED_CONTINUE"
    assert result["skipped"] is True
    assert result["requires_user_intervention"] is False
    assert result["next_legal_action"] == "CONTINUE_NON_CONFLICTING_WORK"


def test_unknown_action_type_fails_closed():
    result = authorize_action(_brain(), _action("invented_future_mutation"), [])
    assert result["decision"] == "TWO_A_UNKNOWN_ACTION_BLOCKED"
    assert result["allowed"] is False


def test_async_poll_without_live_async_run_is_blocked():
    action = _action("poll_status", "github:run/9001")
    result = authorize_action(_brain(), action, [])
    assert result["decision"] == "TWO_A_NO_LIVE_ASYNC_BLOCKED"
    assert result["allowed"] is False


def test_require_authorized_is_execution_tripwire():
    action = _action("create_pr", "github:pr/new")
    denied = authorize_action(_brain(), action, [])
    with pytest.raises(Mandatory2AActionGateFailure):
        require_authorized(denied)

    allowed = authorize_action(_brain(), action, [], forward_decision=_forward(action))
    assert require_authorized(allowed)["allowed"] is True


def test_contract_self_test_is_green():
    result = contract_self_test()
    assert result["status"] == "GREEN"
    assert result["mandatory_gate"] is True
    assert result["missing_authorization_fails_closed"] is True
    assert result["matching_forward_receipt_authorizes"] is True
    assert result["receipt_action_mismatch_blocked"] is True
    assert result["live_async_mutation_blocked"] is True
    assert result["duplicate_poll_autonomously_skipped"] is True
    assert result["unknown_action_fails_closed"] is True
    assert result["product_runtime_mutation"] is False


def test_direct_script_execution_is_green():
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, str(root / "devsystem" / "mandatory_2a_action_gate_v1.py")],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "MONSTER_2A_MANDATORY_ACTION_GATE_V1_GREEN" in completed.stdout
