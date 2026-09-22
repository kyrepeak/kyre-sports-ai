from __future__ import annotations

import json
from pathlib import Path

import pytest

from devsystem.action_ledger_v2 import GENESIS_CHAIN_HASH
from devsystem.forward_motion_v2 import (
    ForwardMotionV2Failure,
    decide,
    fingerprint_action,
    fingerprint_evidence,
    fingerprint_relevant_inputs,
    fingerprint_root_cause,
    load_policy,
)

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "devsystem" / "forward_motion_policy_v2.json"


def test_v2_policy_has_exact_retry_and_stagnation_budgets():
    payload = json.loads(POLICY.read_text(encoding="utf-8"))
    assert payload["version"] == 2
    assert payload["mode"] == "strict_auto_continue_v2"
    assert payload["retry_budgets"] == {
        "deterministic-regression": 0,
        "transient-capable": 1,
        "unknown_evidence_actions": 1,
    }
    assert payload["stagnation"]["max_no_progress_actions"] == 3
    assert payload["proof_rules"]["max_active_blockers"] == 1
    assert payload["proof_rules"]["terminal_task_is_authoritative"] is True


def test_v2_policy_override_is_single_use_user_explicit_only():
    payload = json.loads(POLICY.read_text(encoding="utf-8"))
    assert payload["override_rules"] == {
        "allowed_source": "user_explicit",
        "single_use": True,
        "exact_action_only": True,
        "cannot_disable_policy": True,
        "cryptographic_human_identity_claim": False,
    }


def test_v2_bootstrap_self_expires_after_activation():
    payload = json.loads(POLICY.read_text(encoding="utf-8"))
    assert payload["bootstrap_rules"]["allowed_only_when_base_lacks_v2_policy"] is True
    assert payload["bootstrap_rules"]["single_activation"] is True


def _active_ledger() -> dict:
    return {
        "version": 2,
        "task_id": "fm-v2-test",
        "status": "ACTIVE",
        "current_checkpoint": "2",
        "total_checkpoints": 2,
        "completed_checkpoints": 1,
        "remaining_checkpoints": 1,
        "active_blocker": None,
        "resolved_root_causes": [],
        "action_log": {
            "head_chain_hash": GENESIS_CHAIN_HASH,
            "events": [],
            "consumed_receipts": [],
        },
        "transition_history": [],
        "override_events": [],
        "checkpoints": [
            {"id": "1", "state": "DONE", "evidence": {"proof": "green"}},
            {"id": "2", "state": "ACTIVE", "evidence": {}},
        ],
    }


def _done_ledger() -> dict:
    ledger = _active_ledger()
    ledger["status"] = "DONE"
    ledger["current_checkpoint"] = None
    ledger["completed_checkpoints"] = 2
    ledger["remaining_checkpoints"] = 0
    ledger["checkpoints"][1] = {"id": "2", "state": "DONE", "evidence": {"proof": "green-2"}}
    return ledger


def _action(**overrides) -> dict:
    action = {
        "task_id": "fm-v2-test",
        "checkpoint_id": "2",
        "action_type": "production_proof",
        "target": "render:/health",
        "inputs": {"commit": "abc123", "deployment": "dep-1"},
        "evidence": {"signal": "health-red"},
        "failure": {
            "job": "production",
            "layer": "render",
            "evidence_signal": "identity-mismatch",
            "error_family": "deployment-identity",
            "message": "expected commit mismatch",
        },
        "scope_relation": "in_scope",
        "retry": False,
        "failure_class": None,
        "new_hypothesis": False,
        "requires_user": False,
        "resolvable_with_available_tools": True,
        "evidence_inspected": False,
    }
    action.update(overrides)
    return action


def _history(action: dict, **overrides) -> dict:
    item = {
        "action_fingerprint": fingerprint_action(action),
        "root_cause_fingerprint": fingerprint_root_cause(action),
        "evidence_fingerprint": fingerprint_evidence(action),
        "relevant_input_fingerprint": fingerprint_relevant_inputs(action),
        "result": "failure",
        "failure_class": action.get("failure_class"),
        "controlled_retry": False,
        "evidence_action": False,
        "progress_class": "no_progress",
    }
    item.update(overrides)
    return item


def test_load_policy_rejects_mode_drift(tmp_path):
    path = tmp_path / "policy.json"
    payload = json.loads(POLICY.read_text(encoding="utf-8"))
    payload["mode"] = "weak"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ForwardMotionV2Failure, match="mode drift"):
        load_policy(path)


def test_root_cause_fingerprint_ignores_run_ids_timestamps_and_command_metadata():
    first = _action(
        failure={
            "job": "browser-qa",
            "layer": "ui-browser",
            "evidence_signal": "browser-selector-race",
            "error_family": "timeout",
            "message": "TimeoutError waiting for combobox",
            "run_id": "100",
            "timestamp": "2026-09-15T10:00:00Z",
        },
        command=["pytest", "--foo", "--bar"],
    )
    second = _action(
        failure={
            "job": "browser-qa",
            "layer": "ui-browser",
            "evidence_signal": "browser-selector-race",
            "error_family": "timeout",
            "message": "TimeoutError waiting for combobox",
            "run_id": "999",
            "timestamp": "2026-09-15T11:00:00Z",
        },
        command=["pytest", "--bar", "--foo"],
    )
    assert fingerprint_root_cause(first) == fingerprint_root_cause(second)


def test_exact_duplicate_action_is_denied_without_receipt():
    action = _action()
    result = decide(_active_ledger(), action, [_history(action)])
    assert result["decision"] == "DENIED_LOOP"
    assert "receipt" not in result


def test_deterministic_unchanged_retry_is_denied():
    action = _action(retry=True, failure_class="deterministic-regression")
    result = decide(_active_ledger(), action, [_history(action)])
    assert result["decision"] == "DENIED_STALE_FAILURE"
    assert result["retry_budget_remaining"] == 0
    assert "receipt" not in result


def test_first_inspected_transient_retry_is_authorized_then_second_denied():
    action = _action(retry=True, failure_class="transient-capable", evidence_inspected=True)
    first_history = [_history(action, failure_class="transient-capable")]
    first = decide(_active_ledger(), action, first_history)
    assert first["decision"] == "AUTHORIZED_CONTROLLED_RETRY"
    assert "receipt" in first
    second_history = first_history + [
        _history(action, failure_class="transient-capable", controlled_retry=True)
    ]
    second = decide(_active_ledger(), action, second_history)
    assert second["decision"] == "DENIED_STALE_FAILURE"
    assert second["retry_budget_remaining"] == 0


def test_uninspected_transient_retry_is_denied():
    action = _action(retry=True, failure_class="transient-capable", evidence_inspected=False)
    result = decide(_active_ledger(), action, [_history(action)])
    assert result["decision"] == "DENIED_STALE_FAILURE"


def test_unknown_failure_gets_one_evidence_action_only():
    action = _action(action_type="gather_evidence", retry=True, failure_class="unknown")
    first = decide(_active_ledger(), action, [])
    assert first["decision"] == "AUTHORIZED"
    history = [_history(action, evidence_action=True, failure_class="unknown")]
    second = decide(_active_ledger(), action, history)
    assert second["decision"] in {"DENIED_LOOP", "DENIED_STALE_FAILURE"}


def test_unrelated_action_and_second_blocker_are_deferred():
    unrelated = decide(_active_ledger(), _action(scope_relation="unrelated"), [])
    assert unrelated["decision"] == "DEFER_SIDE_QUEST"

    ledger = _active_ledger()
    ledger["active_blocker"] = {"blocker_id": "prod", "checkpoint_id": "2"}
    second = _action(
        action_type="open_blocker",
        inputs={"blocker_id": "telemetry"},
        target="posthog:event",
    )
    result = decide(ledger, second, [])
    assert result["decision"] == "DEFER_SIDE_QUEST"


def test_terminal_task_returns_task_complete_without_receipt():
    result = decide(_done_ledger(), _action(), [])
    assert result["decision"] == "TASK_COMPLETE"
    assert "receipt" not in result


def test_new_hypothesis_gets_authorization_receipt():
    old = _action()
    action = _action(
        action_type="diagnostic_probe",
        target="render:/ready",
        evidence={"signal": "new-trace"},
        new_hypothesis=True,
    )
    result = decide(_active_ledger(), action, [_history(old)])
    assert result["decision"] == "AUTHORIZED_NEW_HYPOTHESIS"
    assert result["receipt"]["payload"]["decision"] == "AUTHORIZED_NEW_HYPOTHESIS"


def test_three_same_path_no_progress_actions_trigger_stagnation_lock():
    action = _action(root_cause_hint="ROOT-X")
    history = [
        _history(action, progress_class="no_progress"),
        _history(action, progress_class="no_progress"),
        _history(action, progress_class="no_progress"),
    ]
    proposed = _action(root_cause_hint="ROOT-X", action_type="different_probe", evidence={"signal": "different"})
    result = decide(_active_ledger(), proposed, history)
    assert result["decision"] == "DENIED_STAGNATION"
    assert "receipt" not in result


def test_changed_relevant_input_breaks_stagnation_path_and_allows_fresh_action():
    old = _action(root_cause_hint="ROOT-X", inputs={"commit": "old"})
    history = [
        _history(old, progress_class="no_progress"),
        _history(old, progress_class="no_progress"),
        _history(old, progress_class="no_progress"),
    ]
    proposed = _action(root_cause_hint="ROOT-X", inputs={"commit": "new"}, action_type="fresh_proof")
    result = decide(_active_ledger(), proposed, history)
    assert result["decision"] == "AUTHORIZED"
    assert "receipt" in result


def test_resolved_root_cause_stays_closed_without_contradictory_evidence():
    action = _action(root_cause_hint="CLOSED-X")
    ledger = _active_ledger()
    ledger["resolved_root_causes"] = [{
        "root_cause_fingerprint": fingerprint_root_cause(action),
        "closing_evidence_fingerprint": "f" * 64,
        "closed_by_event_id": "ACT-CLOSED",
    }]
    result = decide(ledger, action, [])
    assert result["decision"] == "DENIED_STALE_FAILURE"


def test_new_contradictory_evidence_can_reopen_resolved_root_cause_as_new_hypothesis():
    old = _action(root_cause_hint="CLOSED-X", evidence={"signal": "old"})
    ledger = _active_ledger()
    ledger["resolved_root_causes"] = [{
        "root_cause_fingerprint": fingerprint_root_cause(old),
        "closing_evidence_fingerprint": fingerprint_evidence(old),
        "closed_by_event_id": "ACT-CLOSED",
    }]
    proposed = _action(
        root_cause_hint="CLOSED-X",
        evidence={"signal": "new-contradiction"},
        contradictory_evidence=True,
        action_type="reopen_root_cause",
    )
    result = decide(ledger, proposed, [])
    assert result["decision"] == "AUTHORIZED_NEW_HYPOTHESIS"
    assert "receipt" in result


def _override_for(ledger: dict, action: dict, denial: dict, **overrides) -> dict:
    event = {
        "event_id": "OVR-EXACT-1",
        "source": "user_explicit",
        "task_id": ledger["task_id"],
        "checkpoint_id": action["checkpoint_id"],
        "blocked_action_fingerprint": denial["action_fingerprint"],
        "denial_fingerprint": denial["denial_fingerprint"],
        "reason": "User explicitly authorizes this exact exception.",
        "consumed": False,
    }
    event.update(overrides)
    return event


def _denied_deterministic(ledger: dict | None = None, action: dict | None = None):
    ledger = ledger or _active_ledger()
    action = action or _action(retry=True, failure_class="deterministic-regression")
    denial = decide(ledger, action, [_history(action)])
    assert denial["decision"] == "DENIED_STALE_FAILURE"
    assert "denial_fingerprint" in denial
    return ledger, action, denial


@pytest.mark.parametrize(
    "override_changes",
    [
        {"source": "agent_self_declared"},
        {"task_id": "wrong-task"},
        {"checkpoint_id": "1"},
        {"blocked_action_fingerprint": "0" * 64},
        {"denial_fingerprint": "1" * 64},
        {"denial_fingerprint": ""},
        {"consumed": True},
    ],
)
def test_invalid_override_shapes_are_denied(override_changes):
    ledger, action, denial = _denied_deterministic()
    override = _override_for(ledger, action, denial, **override_changes)
    ledger["override_events"] = [override]
    result = decide(ledger, action, [_history(action)], override_event=override)
    assert result["decision"] == "DENIED_UNAUTHORIZED_OVERRIDE"
    assert "receipt" not in result


def test_valid_exact_user_override_authorizes_only_one_exact_action():
    ledger, action, denial = _denied_deterministic()
    override = _override_for(ledger, action, denial)
    ledger["override_events"] = [override]
    result = decide(ledger, action, [_history(action)], override_event=override)
    assert result["decision"] == "AUTHORIZED_USER_OVERRIDE"
    assert result["receipt"]["payload"]["override_event_id"] == override["event_id"]
    assert load_policy()["retry_budgets"]["deterministic-regression"] == 0

    other = _action(
        retry=True,
        failure_class="deterministic-regression",
        target="render:/different",
    )
    other_denial = decide(ledger, other, [_history(other)])
    assert other_denial["decision"] == "DENIED_STALE_FAILURE"
    reused = decide(ledger, other, [_history(other)], override_event=override)
    assert reused["decision"] == "DENIED_UNAUTHORIZED_OVERRIDE"


def test_consumed_override_cannot_be_reused():
    ledger, action, denial = _denied_deterministic()
    override = _override_for(ledger, action, denial, consumed=True)
    ledger["override_events"] = [override]
    result = decide(ledger, action, [_history(action)], override_event=override)
    assert result["decision"] == "DENIED_UNAUTHORIZED_OVERRIDE"
