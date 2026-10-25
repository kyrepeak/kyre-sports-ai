from __future__ import annotations

from devsystem.action_ledger_v2 import build_receipt
from devsystem.forward_motion_v2 import fingerprint_action
from devsystem.mandatory_2a_action_gate_v1 import authorize_action
from devsystem.persistent_execution_brain_v1 import BrainStateInput, build_state


def _brain(*, waiting: bool = False):
    return build_state(BrainStateInput(
        program_id="step2b-integration-test",
        program_title="Step 2B + Step 2A integration",
        total_steps=1,
        current_step=1,
        step_title="Reliability gate",
        execution_state="WAITING_ON_ASYNC" if waiting else "ACTIVE",
        repository="owner/repo",
        main_sha="1" * 40,
        work_branch="step2b-integration",
        observed_head_sha="2" * 40,
        next_legal_action="Continue safely.",
        completed_steps=(),
        frozen_steps=(),
        remaining_steps=(),
        authoritative_run_id=9001 if waiting else None,
        authoritative_job_id=7001 if waiting else None,
        async_state="IN_PROGRESS" if waiting else "NONE",
        updated_at_utc="2026-10-24T23:25:00Z",
    ))


def _preflight():
    return {
        "finished_state": "Exact implementation works in production.",
        "current_state_inspected": True,
        "root_cause_proven": True,
        "authoritative_path": {
            "repository": "owner/repo",
            "branch": "step2b-integration",
            "target": "github:mutation",
            "proof_path": "production",
        },
        "acceptance_criteria": [{
            "id": "ac1",
            "requirement": "Implementation path is verified",
            "source": "control-plane",
            "verification": "integration test",
            "expected_result": "authorized",
        }],
        "dependency_checks": [],
    }


def _patch(*, preflight=None, history=None):
    action = {
        "task_id": "step2b-integration-test",
        "checkpoint_id": "1",
        "action_type": "patch",
        "target": "github:mutation",
    }
    if preflight is not None:
        action["reliability_preflight"] = preflight
    if history is not None:
        action["implementation_attempt_history"] = history
    return action


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
            "event_nonce": "step2b-integration",
            "override_event_id": None,
        }),
    }


def test_step2a_blocks_patch_even_with_forward_receipt_when_step2b_is_missing():
    action = _patch()
    result = authorize_action(_brain(), action, [], forward_decision=_forward(action))
    assert result["allowed"] is False
    assert result["decision"] == "TWO_A_TWO_B_BLOCKED"
    assert result["reliability_decision"] == "TWO_B_PREFLIGHT_REQUIRED"
    assert result["two_b_enforced"] is True


def test_step2a_authorizes_patch_only_after_step2b_and_forward_motion_both_pass():
    action = _patch(preflight=_preflight(), history=[])
    result = authorize_action(_brain(), action, [], forward_decision=_forward(action))
    assert result["allowed"] is True
    assert result["decision"] == "TWO_A_AUTHORIZED"
    assert result["two_b_enforced"] is True
    assert result["reliability_decision"] == "TWO_B_ATTEMPT_1_AUTHORIZED"
    assert result["implementation_attempt"] == 1
    assert result["reliability_receipt_hash"]
    assert result["forward_receipt_hash"]


def test_two_failed_attempts_handoff_to_step2c_autonomous_diagnosis_before_patch():
    action = _patch(
        preflight=_preflight(),
        history=[
            {"attempt": 1, "outcome": "FAILED", "evidence_fingerprint": "e1"},
            {"attempt": 2, "outcome": "FAILED", "evidence_fingerprint": "e2"},
        ],
    )
    result = authorize_action(_brain(), action, [], forward_decision=_forward(action))
    assert result["allowed"] is False
    assert result["decision"] == "TWO_A_TWO_B_BLOCKED"
    assert result["reliability_decision"] == "TWO_B_TWO_C_RECOVERY_REQUIRED"
    assert result["anti_loop_handoff"] is True
    assert result["next_legal_action"] == "GATHER_EVIDENCE_NEW_SOURCE"


def test_live_async_lock_still_precedes_step2b_and_blocks_competing_patch():
    action = _patch(preflight=_preflight(), history=[])
    result = authorize_action(_brain(waiting=True), action, [])
    assert result["allowed"] is False
    assert result["source_decision"] == "ASYNC_LOCKED"
    assert result["authorization_source"] == "automatic_loop_kill_v1"
