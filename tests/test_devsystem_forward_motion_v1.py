from __future__ import annotations

import pytest

from devsystem.forward_motion_v1 import ForwardMotionFailure, decide, fingerprint_action


def _ledger(*, status: str = "ACTIVE") -> dict:
    checkpoints = [
        {"id": "1", "state": "DONE", "entry_condition": "approved", "exit_condition": "locked", "evidence": {"ok": True}},
        {"id": "2", "state": "ACTIVE", "entry_condition": "locked", "exit_condition": "controller green", "evidence": {}},
        {"id": "3", "state": "PENDING", "entry_condition": "controller green", "exit_condition": "merged", "evidence": {}},
    ]
    if status == "DONE":
        for checkpoint in checkpoints:
            checkpoint["state"] = "DONE"
            checkpoint["evidence"] = {"verified": True}
    return {
        "task_id": "monster-forward-motion-v1",
        "title": "Monster Forward Motion V1",
        "mode": "strict_auto_continue",
        "status": status,
        "current_checkpoint": None if status == "DONE" else "2",
        "total_checkpoints": 3,
        "completed_checkpoints": 3 if status == "DONE" else 1,
        "remaining_checkpoints": 0 if status == "DONE" else 2,
        "exit_conditions": ["controller green", "merged"],
        "active_blocker": None,
        "deferred_findings": [],
        "evidence_fingerprints": [],
        "action_history": [],
        "checkpoints": checkpoints,
    }


def _action(**overrides) -> dict:
    action = {
        "task_id": "monster-forward-motion-v1",
        "checkpoint_id": "2",
        "action_type": "production_proof",
        "target": "render:/health",
        "inputs": {"commit": "abc123", "deployment": "dep-1"},
        "evidence_class": "production_identity",
        "scope_relation": "in_scope",
        "retry": False,
        "failure_class": None,
        "new_hypothesis": False,
        "requires_user": False,
        "resolvable_with_available_tools": True,
    }
    action.update(overrides)
    return action


def test_action_fingerprint_is_stable_for_equivalent_input_order():
    left = _action(inputs={"commit": "abc123", "deployment": "dep-1"})
    right = _action(inputs={"deployment": "dep-1", "commit": "abc123"})
    assert fingerprint_action(left) == fingerprint_action(right)


def test_duplicate_successful_proof_is_rejected_when_inputs_are_unchanged():
    action = _action()
    history = [{"fingerprint": fingerprint_action(action), "result": "success"}]
    result = decide(_ledger(), action, history)
    assert result["decision"] == "REJECT_DUPLICATE_PROOF"


def test_changed_input_revision_allows_forward_motion():
    old = _action(inputs={"commit": "abc123", "deployment": "dep-1"})
    new = _action(inputs={"commit": "def456", "deployment": "dep-2"})
    history = [{"fingerprint": fingerprint_action(old), "result": "success"}]
    result = decide(_ledger(), new, history)
    assert result["decision"] == "ALLOW_ADVANCE"


def test_deterministic_failure_gets_zero_unchanged_retries():
    action = _action(retry=True, failure_class="deterministic-regression")
    history = [{"fingerprint": fingerprint_action(action), "result": "failure", "failure_class": "deterministic-regression"}]
    result = decide(_ledger(), action, history)
    assert result["decision"] == "REJECT_DUPLICATE_PROOF"
    assert result["retry_budget_remaining"] == 0


def test_transient_failure_gets_exactly_one_controlled_retry():
    action = _action(retry=True, failure_class="transient-capable")
    fingerprint = fingerprint_action(action)

    first_retry = decide(
        _ledger(),
        action,
        [{"fingerprint": fingerprint, "result": "failure", "failure_class": "transient-capable"}],
    )
    assert first_retry["decision"] == "ALLOW_CONTROLLED_RETRY"
    assert first_retry["retry_budget_remaining"] == 0

    second_retry = decide(
        _ledger(),
        action,
        [
            {"fingerprint": fingerprint, "result": "failure", "failure_class": "transient-capable"},
            {"fingerprint": fingerprint, "result": "failure", "failure_class": "transient-capable", "controlled_retry": True},
        ],
    )
    assert second_retry["decision"] == "REJECT_DUPLICATE_PROOF"
    assert second_retry["retry_budget_remaining"] == 0


def test_unknown_failure_gets_one_evidence_gathering_action_only():
    action = _action(
        action_type="gather_failure_evidence",
        target="github:job-log",
        retry=True,
        failure_class="unknown",
        new_hypothesis=True,
        inputs={"run_id": 77, "attempt": 1},
    )
    fingerprint = fingerprint_action(action)

    first = decide(_ledger(), action, [])
    assert first["decision"] == "ALLOW_NEW_HYPOTHESIS"

    second = decide(
        _ledger(),
        action,
        [{"fingerprint": fingerprint, "result": "evidence_collected"}],
    )
    assert second["decision"] == "REJECT_DUPLICATE_PROOF"


def test_unrelated_finding_is_deferred_instead_of_becoming_a_side_quest():
    result = decide(_ledger(), _action(scope_relation="unrelated"), [])
    assert result["decision"] == "DEFER_SIDE_QUEST"


def test_second_blocker_is_deferred_while_one_blocker_is_active():
    ledger = _ledger()
    ledger["active_blocker"] = {
        "blocker_id": "production-identity",
        "checkpoint_id": "2",
        "root_cause_class": "production_identity",
    }
    action = _action(
        action_type="open_blocker",
        target="posthog:event-proof",
        inputs={"blocker_id": "telemetry-proof"},
        evidence_class="telemetry",
    )
    result = decide(ledger, action, [])
    assert result["decision"] == "DEFER_SIDE_QUEST"
    assert "active blocker" in result["reason"]


def test_evidence_for_existing_active_blocker_is_allowed():
    ledger = _ledger()
    ledger["active_blocker"] = {
        "blocker_id": "production-identity",
        "checkpoint_id": "2",
        "root_cause_class": "production_identity",
    }
    action = _action(
        action_type="attach_blocker_evidence",
        target="production-identity",
        inputs={"blocker_id": "production-identity", "new_sha": "def456"},
    )
    result = decide(ledger, action, [])
    assert result["decision"] == "ALLOW_ADVANCE"


def test_unresolvable_external_blocker_stops_with_single_user_action():
    action = _action(
        action_type="external_blocker",
        requires_user=True,
        resolvable_with_available_tools=False,
        user_action="Restart the Streamlit app once.",
    )
    result = decide(_ledger(), action, [])
    assert result["decision"] == "STOP_EXTERNAL_BLOCKER"
    assert result["user_action"] == "Restart the Streamlit app once."


def test_external_blocker_without_one_concrete_user_action_fails_closed():
    action = _action(
        action_type="external_blocker",
        requires_user=True,
        resolvable_with_available_tools=False,
        user_action="",
    )
    with pytest.raises(ForwardMotionFailure, match="single concrete user_action"):
        decide(_ledger(), action, [])


def test_done_task_is_terminal_and_cannot_spawn_more_work():
    result = decide(_ledger(status="DONE"), _action(), [])
    assert result["decision"] == "TASK_COMPLETE"


def test_closed_checkpoint_reopen_is_rejected_without_contradictory_evidence():
    action = _action(checkpoint_id="1", action_type="reopen_checkpoint")
    result = decide(_ledger(), action, [])
    assert result["decision"] == "REJECT_CLOSED_CHECKPOINT_REOPEN"


def test_closed_checkpoint_can_reopen_only_with_new_contradictory_evidence():
    action = _action(
        checkpoint_id="1",
        action_type="reopen_checkpoint",
        contradictory_evidence=True,
        inputs={"evidence_hash": "new-contradiction"},
    )
    result = decide(_ledger(), action, [])
    assert result["decision"] == "ALLOW_NEW_HYPOTHESIS"
