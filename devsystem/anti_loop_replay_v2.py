"""Adversarial regression replay for Monster Anti-Loop V2."""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from devsystem.action_ledger_v2 import (
    ActionLedgerFailure,
    GENESIS_CHAIN_HASH,
    record_authorized_action,
    validate_action_ledger,
)
from devsystem.checkpoint_ledger_v2 import (
    CheckpointLedgerV2Failure,
    transition_checkpoint,
    validate_checkpoint_ledger,
)
from devsystem.forward_motion_v2 import (
    decide,
    fingerprint_action,
    fingerprint_evidence,
    fingerprint_relevant_inputs,
    fingerprint_root_cause,
)

SCENARIO = "MONSTER_ANTI_LOOP_V2_ADVERSARIAL_REPLAY"


def _ledger(*, task_id: str = "anti-loop-v2-replay", first_active: bool = True) -> dict[str, Any]:
    checkpoints = [
        {"id": "1", "state": "ACTIVE" if first_active else "DONE", "evidence": {} if first_active else {"proof": "green-1"}},
        {"id": "2", "state": "PENDING" if first_active else "ACTIVE", "evidence": {}},
    ]
    return {
        "version": 2,
        "task_id": task_id,
        "status": "ACTIVE",
        "current_checkpoint": "1" if first_active else "2",
        "total_checkpoints": 2,
        "completed_checkpoints": 0 if first_active else 1,
        "remaining_checkpoints": 2 if first_active else 1,
        "active_blocker": None,
        "resolved_root_causes": [],
        "action_log": {
            "head_chain_hash": GENESIS_CHAIN_HASH,
            "events": [],
            "consumed_receipts": [],
        },
        "transition_history": [],
        "override_events": [],
        "checkpoints": checkpoints,
    }


def _action(checkpoint_id: str = "1", **overrides: Any) -> dict[str, Any]:
    action: dict[str, Any] = {
        "task_id": "anti-loop-v2-replay",
        "checkpoint_id": checkpoint_id,
        "action_type": "production_proof",
        "target": "render:/health",
        "inputs": {"commit": "abc123", "deployment": "dep-1"},
        "evidence": {"signal": "identity-red"},
        "failure": {
            "job": "production",
            "layer": "render",
            "evidence_signal": "identity-mismatch",
            "error_family": "deployment-identity",
            "message": "expected production commit mismatch",
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


def _history(action: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    item: dict[str, Any] = {
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


def _require(payload: dict[str, Any], expected: str, label: str) -> None:
    actual = payload.get("decision")
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected}, got {actual}: {payload}")


def _record(ledger: dict[str, Any], decision: dict[str, Any], *, evidence: dict[str, Any], progress_class: str = "new_evidence") -> tuple[dict[str, Any], str]:
    updated = record_authorized_action(
        ledger,
        decision["receipt"],
        outcome="success",
        progress_class=progress_class,
        evidence=evidence,
    )
    return updated, str(updated["action_log"]["events"][-1]["event_id"])


def run_replay() -> dict[str, Any]:
    exact_duplicates_denied = 0
    semantic_root_cause_loops_denied = 0
    stagnation_locks = 0
    closed_checkpoint_reopens_denied = 0
    second_blockers_deferred = 0
    invalid_overrides_denied = 0
    valid_single_use_overrides = 0
    receipt_replays_denied = 0
    tamper_attempts_denied = 0

    base = _ledger()
    duplicate_action = _action()
    duplicate = decide(base, duplicate_action, [_history(duplicate_action)])
    _require(duplicate, "DENIED_LOOP", "exact duplicate")
    exact_duplicates_denied += 1

    old = _action(
        action_type="production_proof_run_100",
        failure={"job": "production", "layer": "render", "evidence_signal": "identity-mismatch", "error_family": "deployment-identity", "message": "expected production commit mismatch", "run_id": "100"},
    )
    rerun = _action(
        action_type="production_proof_run_999",
        failure={"job": "production", "layer": "render", "evidence_signal": "identity-mismatch", "error_family": "deployment-identity", "message": "expected production commit mismatch", "run_id": "999"},
    )
    semantic = decide(base, rerun, [_history(old)])
    _require(semantic, "DENIED_STALE_FAILURE", "same root cause new run id")
    semantic_root_cause_loops_denied += 1

    cmd_old = _action(command=["pytest", "--foo", "--bar"])
    cmd_new = _action(command=["pytest", "--bar", "--foo"])
    command_loop = decide(base, cmd_new, [_history(cmd_old)])
    _require(command_loop, "DENIED_STALE_FAILURE", "same root cause command reorder")
    semantic_root_cause_loops_denied += 1

    deterministic = _action(retry=True, failure_class="deterministic-regression")
    deterministic_result = decide(base, deterministic, [_history(deterministic)])
    _require(deterministic_result, "DENIED_STALE_FAILURE", "deterministic retry")
    if deterministic_result.get("retry_budget_remaining") != 0:
        raise AssertionError("deterministic retry budget drift")

    transient = _action(retry=True, failure_class="transient-capable", evidence_inspected=True)
    transient_history = [_history(transient, failure_class="transient-capable")]
    first_transient = decide(base, transient, transient_history)
    _require(first_transient, "AUTHORIZED_CONTROLLED_RETRY", "first transient retry")
    second_transient = decide(base, transient, transient_history + [_history(transient, controlled_retry=True, failure_class="transient-capable")])
    _require(second_transient, "DENIED_STALE_FAILURE", "second transient retry")

    unknown = _action(action_type="gather_evidence", retry=True, failure_class="unknown")
    first_unknown = decide(base, unknown, [])
    _require(first_unknown, "AUTHORIZED", "first unknown evidence action")
    second_unknown = decide(base, unknown, [_history(unknown, evidence_action=True, failure_class="unknown")])
    if second_unknown.get("decision") not in {"DENIED_LOOP", "DENIED_STALE_FAILURE"}:
        raise AssertionError(f"second unknown evidence action escaped: {second_unknown}")

    stale = _action(root_cause_hint="ROOT-STAGNANT")
    stagnant_history = [_history(stale), _history(stale), _history(stale)]
    stagnant_probe = _action(root_cause_hint="ROOT-STAGNANT", action_type="different_probe", evidence={"signal": "different-but-not-progress"})
    stagnation = decide(base, stagnant_probe, stagnant_history)
    _require(stagnation, "DENIED_STAGNATION", "stagnation lock")
    stagnation_locks += 1

    old_input = _action(root_cause_hint="ROOT-STAGNANT", inputs={"commit": "old"})
    changed_input = _action(root_cause_hint="ROOT-STAGNANT", inputs={"commit": "new"}, action_type="fresh_proof")
    changed = decide(base, changed_input, [_history(old_input), _history(old_input), _history(old_input)])
    _require(changed, "AUTHORIZED", "changed relevant input")

    old_hypothesis = _action(root_cause_hint="ROOT-HYP")
    new_hypothesis = _action(root_cause_hint="ROOT-HYP", action_type="diagnostic_probe", target="render:/ready", evidence={"signal": "new-trace"}, new_hypothesis=True)
    hypothesis = decide(base, new_hypothesis, [_history(old_hypothesis)])
    _require(hypothesis, "AUTHORIZED_NEW_HYPOTHESIS", "new hypothesis")

    close_ledger = _ledger()
    close_action = _action(action_type="close_checkpoint", target="monster:cp1", evidence={"proof": "green-cp1"})
    close_decision = decide(close_ledger, close_action, [])
    _require(close_decision, "AUTHORIZED", "close checkpoint authorization")
    close_ledger, close_event = _record(close_ledger, close_decision, evidence={"proof": "green-cp1"}, progress_class="checkpoint_closed")
    close_ledger = transition_checkpoint(close_ledger, "1", "DONE", authorized_event_id=close_event, evidence={"proof": "green-cp1"})

    reopen = _action(checkpoint_id="1", action_type="reopen_checkpoint", target="monster:cp1")
    reopen_result = decide(close_ledger, reopen, [])
    _require(reopen_result, "DENIED_CLOSED_CHECKPOINT", "closed checkpoint reopen")
    closed_checkpoint_reopens_denied += 1

    contradiction = _action(checkpoint_id="1", action_type="reopen_checkpoint", target="monster:cp1", evidence={"proof": "new-contradiction"}, contradictory_evidence={"prior_closing_proof_invalid": True}, new_hypothesis=True)
    contradiction_result = decide(close_ledger, contradiction, [])
    _require(contradiction_result, "AUTHORIZED_NEW_HYPOTHESIS", "contradictory reopen")
    reopen_copy, contradiction_event = _record(deepcopy(close_ledger), contradiction_result, evidence={"proof": "new-contradiction"}, progress_class="new_evidence")
    reopened = transition_checkpoint(reopen_copy, "1", "ACTIVE", authorized_event_id=contradiction_event, contradictory_evidence={"prior_closing_proof_invalid": True})
    if reopened.get("current_checkpoint") != "1":
        raise AssertionError("valid contradictory evidence did not reopen checkpoint")

    blocker_ledger = _ledger()
    blocker_ledger["active_blocker"] = {"blocker_id": "production", "checkpoint_id": "1"}
    second_blocker = _action(action_type="open_blocker", target="telemetry", inputs={"blocker_id": "telemetry"})
    blocker_result = decide(blocker_ledger, second_blocker, [])
    _require(blocker_result, "DEFER_SIDE_QUEST", "second blocker")
    second_blockers_deferred += 1

    unrelated = decide(base, _action(scope_relation="unrelated"), [])
    _require(unrelated, "DEFER_SIDE_QUEST", "unrelated finding")

    receipt_action = _action(action_type="receipt_proof", target="monster:receipt", evidence={"proof": "receipt"})
    receipt_decision = decide(_ledger(), receipt_action, [])
    _require(receipt_decision, "AUTHORIZED", "receipt authorization")
    receipt_ledger, _ = _record(_ledger(), receipt_decision, evidence={"proof": "receipt"})
    try:
        record_authorized_action(receipt_ledger, receipt_decision["receipt"], outcome="success", progress_class="new_evidence", evidence={"proof": "receipt"})
    except ActionLedgerFailure:
        receipt_replays_denied += 1
    else:
        raise AssertionError("authorization receipt replay was accepted")

    mismatch_ledger = _ledger()
    cp1_action = _action(checkpoint_id="1", action_type="cp1-proof", target="monster:cp1")
    cp1_decision = decide(mismatch_ledger, cp1_action, [])
    mismatch_ledger, cp1_event = _record(mismatch_ledger, cp1_decision, evidence={"proof": "cp1"})
    try:
        transition_checkpoint(mismatch_ledger, "2", "DONE", authorized_event_id=cp1_event, evidence={"proof": "wrong-checkpoint"})
    except CheckpointLedgerV2Failure:
        pass
    else:
        raise AssertionError("receipt checkpoint mismatch was accepted")

    tampered = deepcopy(receipt_ledger)
    tampered["action_log"]["events"][0]["evidence"] = {"proof": "tampered"}
    try:
        validate_action_ledger(tampered)
    except ActionLedgerFailure:
        tamper_attempts_denied += 1
    else:
        raise AssertionError("tampered action history validated")

    override_ledger = _ledger()
    denied_action = _action(retry=True, failure_class="deterministic-regression")
    denied = decide(override_ledger, denied_action, [_history(denied_action)])
    _require(denied, "DENIED_STALE_FAILURE", "override base denial")

    invalid_override = {"event_id": "OVR-AGENT", "source": "agent_self_declared", "task_id": override_ledger["task_id"], "checkpoint_id": denied_action["checkpoint_id"], "blocked_action_fingerprint": denied["action_fingerprint"], "denial_fingerprint": denied["denial_fingerprint"], "reason": "agent tries to self-authorize", "consumed": False}
    override_ledger["override_events"] = [invalid_override]
    invalid_result = decide(override_ledger, denied_action, [_history(denied_action)], override_event=invalid_override)
    _require(invalid_result, "DENIED_UNAUTHORIZED_OVERRIDE", "self-declared override")
    invalid_overrides_denied += 1

    valid_override = {"event_id": "OVR-USER-EXACT-1", "source": "user_explicit", "task_id": override_ledger["task_id"], "checkpoint_id": denied_action["checkpoint_id"], "blocked_action_fingerprint": denied["action_fingerprint"], "denial_fingerprint": denied["denial_fingerprint"], "reason": "user explicitly authorizes this exact denied action", "consumed": False}
    override_ledger["override_events"] = [valid_override]
    valid_result = decide(override_ledger, denied_action, [_history(denied_action)], override_event=valid_override)
    _require(valid_result, "AUTHORIZED_USER_OVERRIDE", "exact user override")
    valid_single_use_overrides += 1
    override_ledger["override_events"][0]["consumed"] = True
    consumed_override = deepcopy(override_ledger["override_events"][0])
    reused = decide(override_ledger, denied_action, [_history(denied_action)], override_event=consumed_override)
    _require(reused, "DENIED_UNAUTHORIZED_OVERRIDE", "override reuse")
    invalid_overrides_denied += 1

    final_ledger = _ledger()
    close1 = _action(checkpoint_id="1", action_type="final-close-1", target="monster:final-1", evidence={"proof": "one"})
    close1_decision = decide(final_ledger, close1, [])
    final_ledger, close1_event = _record(final_ledger, close1_decision, evidence={"proof": "one"}, progress_class="checkpoint_closed")
    final_ledger = transition_checkpoint(final_ledger, "1", "DONE", authorized_event_id=close1_event, evidence={"proof": "one"})

    close2 = _action(checkpoint_id="2", action_type="final-close-2", target="monster:final-2", evidence={"proof": "two"})
    close2_decision = decide(final_ledger, close2, [])
    final_ledger, close2_event = _record(final_ledger, close2_decision, evidence={"proof": "two"}, progress_class="checkpoint_closed")
    final_ledger = transition_checkpoint(final_ledger, "2", "DONE", authorized_event_id=close2_event, evidence={"proof": "two"})
    final_state = validate_checkpoint_ledger(final_ledger)
    checkpoint_count = len(final_ledger["checkpoints"])
    post_finish = decide(final_ledger, _action(checkpoint_id="2", action_type="one_more_proof", target="monster:extra"), [])
    _require(post_finish, "TASK_COMPLETE", "post-finish action")
    invented = len(final_ledger["checkpoints"]) - checkpoint_count

    result = {
        "status": "GREEN",
        "scenario": SCENARIO,
        "exact_duplicates_denied": exact_duplicates_denied,
        "semantic_root_cause_loops_denied": semantic_root_cause_loops_denied,
        "stagnation_locks": stagnation_locks,
        "closed_checkpoint_reopens_denied": closed_checkpoint_reopens_denied,
        "second_blockers_deferred": second_blockers_deferred,
        "invalid_overrides_denied": invalid_overrides_denied,
        "valid_single_use_overrides": valid_single_use_overrides,
        "receipt_replays_denied": receipt_replays_denied,
        "tamper_attempts_denied": tamper_attempts_denied,
        "final_task_status": final_state["task_status"],
        "remaining_checkpoints": final_state["remaining_checkpoints"],
        "post_finish_decision": post_finish["decision"],
        "invented_post_finish_checkpoints": invented,
    }
    print("MONSTER_ANTI_LOOP_V2_REPLAY_GREEN")
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


if __name__ == "__main__":
    run_replay()
