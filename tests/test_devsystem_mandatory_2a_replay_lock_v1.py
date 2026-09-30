from __future__ import annotations

from devsystem.action_ledger_v2 import build_receipt
from devsystem.forward_motion_v2 import fingerprint_action
from devsystem.mandatory_2a_receipt_v1 import (
    authorize_action_with_receipt,
    new_consumption_ledger,
)
from devsystem.mandatory_2a_replay_lock_v1 import (
    claim_execution_slot,
    contract_self_test,
    new_replay_ledger,
    preflight_replay_lock,
    validate_replay_ledger,
)
from devsystem.persistent_execution_brain_v1 import BrainStateInput, build_state


def _brain(*, waiting=False, updated_at="2026-09-30T03:37:00Z"):
    return build_state(BrainStateInput(
        program_id="test",
        program_title="2A Step 3 replay lock",
        total_steps=2,
        current_step=1,
        step_title="Replay + Loop Lock",
        execution_state="WAITING_ON_ASYNC" if waiting else "ACTIVE",
        repository="owner/repo",
        main_sha="1" * 40,
        work_branch="step3",
        observed_head_sha="2" * 40,
        next_legal_action="Continue safely.",
        completed_steps=(),
        frozen_steps=(),
        remaining_steps=(2,),
        authoritative_run_id=9001 if waiting else None,
        authoritative_job_id=7001 if waiting else None,
        async_state="IN_PROGRESS" if waiting else "NONE",
        updated_at_utc=updated_at,
    ))


def _action(target="github:pr/1"):
    return {
        "task_id": "test",
        "checkpoint_id": "1",
        "action_type": "merge",
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
            "event_nonce": "step3-test",
            "override_event_id": None,
        }),
    }


def _authorized(brain, action):
    return authorize_action_with_receipt(
        brain,
        action,
        [],
        forward_decision=_forward(action),
    )


def test_first_execution_claim_is_allowed_and_reserves_all_replay_keys():
    brain = _brain()
    action = _action()
    claim = claim_execution_slot(
        _authorized(brain, action),
        brain,
        action,
        new_replay_ledger(),
        new_consumption_ledger(),
    )
    assert claim["result"]["decision"] == "EXECUTION_SLOT_CLAIMED"
    assert claim["result"]["allowed"] is True
    assert claim["result"]["slot_claimed"] is True
    state = validate_replay_ledger(claim["replay_ledger"])
    assert state["claimed_actions"] == 1
    assert state["claimed_receipts"] == 1
    assert state["claimed_sources"] == 1


def test_exact_same_authorization_cannot_execute_twice():
    brain = _brain()
    action = _action()
    auth = _authorized(brain, action)
    first = claim_execution_slot(
        auth, brain, action, new_replay_ledger(), new_consumption_ledger()
    )
    second = claim_execution_slot(
        auth,
        brain,
        action,
        first["replay_ledger"],
        first["consumption_ledger"],
    )
    assert second["result"]["decision"] == "LOOP_SKIPPED_CONTINUE"
    assert second["result"]["allowed"] is False
    assert second["result"]["autonomous_skip"] is True
    assert second["result"]["requires_user_intervention"] is False


def test_new_receipt_for_same_action_fingerprint_is_still_skipped():
    brain1 = _brain(updated_at="2026-09-30T03:37:00Z")
    brain2 = _brain(updated_at="2026-09-30T03:38:00Z")
    action = _action()
    first = claim_execution_slot(
        _authorized(brain1, action),
        brain1,
        action,
        new_replay_ledger(),
        new_consumption_ledger(),
    )
    second_auth = _authorized(brain2, action)
    assert second_auth["execution_receipt_hash"] != first["result"]["receipt_hash"]
    replay = preflight_replay_lock(
        second_auth,
        brain2,
        action,
        first["replay_ledger"],
    )
    assert replay["decision"] == "LOOP_SKIPPED_CONTINUE"
    assert "action fingerprint" in replay["reason"]


def test_same_async_cycle_cannot_be_replayed():
    brain = _brain(waiting=True)
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
    auth = authorize_action_with_receipt(brain, action, [])
    first = claim_execution_slot(
        auth, brain, action, new_replay_ledger(), new_consumption_ledger()
    )
    replay = preflight_replay_lock(
        auth, brain, action, first["replay_ledger"]
    )
    assert replay["decision"] == "LOOP_SKIPPED_CONTINUE"
    assert replay["requires_user_intervention"] is False


def test_genuinely_different_action_remains_legal():
    brain = _brain()
    first_action = _action("github:pr/1")
    first = claim_execution_slot(
        _authorized(brain, first_action),
        brain,
        first_action,
        new_replay_ledger(),
        new_consumption_ledger(),
    )
    next_action = _action("github:pr/2")
    result = preflight_replay_lock(
        _authorized(brain, next_action),
        brain,
        next_action,
        first["replay_ledger"],
    )
    assert result["decision"] == "EXECUTION_SLOT_AVAILABLE"
    assert result["allowed"] is True


def test_upstream_loop_skip_is_preserved_not_reopened():
    result = preflight_replay_lock(
        {
            "allowed": False,
            "decision": "TWO_A_LOOP_SKIPPED_CONTINUE",
            "source_decision": "LOOP_SKIPPED_CONTINUE",
            "next_legal_action": "CONTINUE_NON_CONFLICTING_WORK",
        },
        _brain(),
        _action(),
        new_replay_ledger(),
    )
    assert result["decision"] == "LOOP_SKIPPED_CONTINUE"
    assert result["allowed"] is False
    assert result["requires_user_intervention"] is False


def test_contract_self_test_is_green():
    result = contract_self_test()
    assert result["status"] == "GREEN"
    assert result["execution_slot_claim_before_action"] is True
    assert result["exact_receipt_replay_skipped"] is True
    assert result["new_receipt_same_action_skipped"] is True
    assert result["async_cycle_replay_skipped"] is True
    assert result["autonomous_skip_no_user"] is True
    assert result["genuinely_new_action_allowed"] is True
    assert result["step2_single_use_preserved"] is True
    assert result["step1_gate_preserved"] is True
    assert result["product_runtime_mutation"] is False


def test_direct_script_execution_is_green():
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, str(root / "devsystem" / "mandatory_2a_replay_lock_v1.py")],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "MONSTER_2A_REPLAY_LOOP_LOCK_V1_GREEN" in completed.stdout
