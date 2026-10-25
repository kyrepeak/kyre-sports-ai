from __future__ import annotations

from devsystem.action_ledger_v2 import build_receipt
from devsystem.forward_motion_v2 import fingerprint_action
from devsystem.mandatory_2a_action_gate_v1 import authorize_action
from devsystem.mandatory_2b_reliability_gate_v1 import authorize_implementation
from devsystem.persistent_execution_brain_v1 import BrainStateInput, build_state


def _path():
    return {
        "repository": "kyrepeak/kyre-sports-ai",
        "branch": "monster-step2c-autonomous-recovery-v1",
        "target": "github:mutation",
        "proof_path": "runless-v2",
    }


def _preflight():
    return {
        "finished_state": "Recovery generation converges without repeating a failed repair.",
        "current_state_inspected": True,
        "root_cause_proven": True,
        "authoritative_path": _path(),
        "acceptance_criteria": [{
            "id": "ac1",
            "requirement": "new diagnosis generation is evidence-bound",
            "source": "control-plane",
            "verification": "integration test",
            "expected_result": "authorized",
        }],
        "dependency_checks": [],
    }


def _failed_attempts():
    return [
        {"attempt": 1, "outcome": "FAILED", "evidence_fingerprint": "attempt-e1"},
        {"attempt": 2, "outcome": "FAILED", "evidence_fingerprint": "attempt-e2"},
    ]


def _recovery_context(*, human_blocker=None, wrong_path=False):
    path = _path()
    if wrong_path:
        path = {**path, "branch": "wrong-branch"}
    context = {
        "task_id": "step2c-integration",
        "checkpoint_id": "2C",
        "authoritative_path": path,
        "failed_generation": 1,
        "failed_attempts": _failed_attempts(),
        "diagnostic_history": [],
        "evidence_candidates": [],
        "root_cause": {
            "proven": True,
            "classification": "configuration/environment",
            "failed_assumption": "the proof runner has the required test dependency",
            "evidence_fingerprint": "materially-new-root-cause",
            "repair_summary": "install the required dependency before the proof suite",
        },
    }
    if human_blocker is not None:
        context.pop("root_cause", None)
        context["human_blocker"] = human_blocker
    return context


def _patch(*, recovery_context=None):
    action = {
        "task_id": "step2c-integration",
        "checkpoint_id": "2C",
        "action_type": "patch",
        "target": "github:mutation",
        "reliability_preflight": _preflight(),
        "implementation_attempt_history": _failed_attempts(),
    }
    if recovery_context is not None:
        action["autonomous_recovery_context"] = recovery_context
    return action


def _brain(*, waiting=False):
    return build_state(BrainStateInput(
        program_id="step2c-integration",
        program_title="Step 2C integration",
        total_steps=1,
        current_step=1,
        step_title="Autonomous recovery",
        execution_state="WAITING_ON_ASYNC" if waiting else "ACTIVE",
        repository="kyrepeak/kyre-sports-ai",
        main_sha="1" * 40,
        work_branch="monster-step2c-autonomous-recovery-v1",
        observed_head_sha="2" * 40,
        next_legal_action="Continue through the control plane.",
        completed_steps=(),
        frozen_steps=(),
        remaining_steps=(),
        authoritative_run_id=9001 if waiting else None,
        authoritative_job_id=7001 if waiting else None,
        async_state="IN_PROGRESS" if waiting else "NONE",
        updated_at_utc="2026-10-25T00:30:00Z",
    ))


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
            "event_nonce": "step2c-integration",
            "override_event_id": None,
        }),
    }


def test_two_failed_attempts_handoff_to_step2c_instead_of_blind_attempt_three():
    result = authorize_implementation(_patch())

    assert result["allowed"] is False
    assert result["decision"] == "TWO_B_TWO_C_RECOVERY_REQUIRED"
    assert result["anti_loop_handoff"] is True
    assert result["two_c_enforced"] is True
    assert result["requires_user_intervention"] is False
    assert result["next_legal_action"] == "GATHER_EVIDENCE_NEW_SOURCE"


def test_materially_new_root_cause_opens_new_recovery_generation():
    action = _patch(recovery_context=_recovery_context())
    result = authorize_implementation(action)

    assert result["allowed"] is True
    assert result["decision"] == "TWO_B_RECOVERY_ATTEMPT_AUTHORIZED"
    assert result["implementation_attempt"] == 1
    assert result["recovery_generation"] == 2
    assert result["two_c_enforced"] is True
    assert result["recovery_decision"] == "TWO_C_RECOVERY_AUTHORIZED"
    assert result["recovery_receipt_hash"]


def test_mismatched_recovery_path_fails_closed():
    action = _patch(recovery_context=_recovery_context(wrong_path=True))
    result = authorize_implementation(action)

    assert result["allowed"] is False
    assert result["decision"] == "TWO_B_TWO_C_RECOVERY_REQUIRED"
    assert result["two_c_enforced"] is True
    assert result["recovery_decision"] == "TWO_C_RECOVERY_RECEIPT_INVALID"


def test_step2a_authorizes_only_after_step2b_enforces_step2c_and_forward_motion():
    action = _patch(recovery_context=_recovery_context())
    reliability = authorize_implementation(action)
    result = authorize_action(_brain(), action, [], forward_decision=_forward(action))

    assert reliability["allowed"] is True
    assert reliability["decision"] == "TWO_B_RECOVERY_ATTEMPT_AUTHORIZED"
    assert reliability["two_c_enforced"] is True
    assert reliability["recovery_decision"] == "TWO_C_RECOVERY_AUTHORIZED"
    assert reliability["recovery_generation"] == 2
    assert reliability["recovery_receipt_hash"]
    assert reliability["reliability_receipt_hash"]

    assert result["allowed"] is True
    assert result["decision"] == "TWO_A_AUTHORIZED"
    assert result["two_b_enforced"] is True
    assert result["reliability_decision"] == "TWO_B_RECOVERY_ATTEMPT_AUTHORIZED"
    assert result["implementation_attempt"] == 1


def test_live_async_anti_loop_still_blocks_before_step2c_recovery_mutation():
    action = _patch(recovery_context=_recovery_context())
    result = authorize_action(_brain(waiting=True), action, [])

    assert result["allowed"] is False
    assert result["authorization_source"] == "automatic_loop_kill_v1"
    assert result["source_decision"] == "ASYNC_LOCKED"


def test_verified_human_only_blocker_is_the_only_recovery_stop():
    action = _patch(recovery_context=_recovery_context(human_blocker={
        "verified": True,
        "type": "missing_credentials",
        "evidence": "required provider credential is not configured",
    }))
    reliability = authorize_implementation(action)
    result = authorize_action(_brain(), action, [], forward_decision=_forward(action))

    assert reliability["allowed"] is False
    assert reliability["decision"] == "TWO_B_TWO_C_RECOVERY_REQUIRED"
    assert reliability["two_c_enforced"] is True
    assert reliability["recovery_decision"] == "TWO_C_HUMAN_BLOCKER"
    assert reliability["requires_user_intervention"] is True

    assert result["allowed"] is False
    assert result["decision"] == "TWO_A_TWO_B_BLOCKED"
    assert result["reliability_decision"] == "TWO_B_TWO_C_RECOVERY_REQUIRED"
    assert result["next_legal_action"] == "REQUEST_EXACT_HUMAN_INPUT"
