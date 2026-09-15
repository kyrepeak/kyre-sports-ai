"""Deterministic regression replay for the Monster A9 loop pattern.

The replay uses no network and no sports/runtime code. It exercises the exact
control-plane mistakes that caused A9 to sprawl: duplicate unchanged proof,
multiple simultaneous blockers, reopening closed checkpoints, approval churn for
in-scope repairs, and inventing work after the finish line.
"""
from __future__ import annotations

import json
from typing import Any

from devsystem.checkpoint_ledger_v1 import transition_checkpoint, validate_ledger
from devsystem.forward_motion_v1 import decide, fingerprint_action, load_policy


SCENARIO = "MONSTER_A9_ANTI_LOOP_REPLAY_V1"


def _ledger() -> dict[str, Any]:
    return {
        "task_id": "monster-a9-replay-v1",
        "title": "Monster A9 production activation replay",
        "mode": "strict_auto_continue",
        "status": "ACTIVE",
        "current_checkpoint": "A9.14b",
        "total_checkpoints": 5,
        "completed_checkpoints": 1,
        "remaining_checkpoints": 4,
        "exit_conditions": [
            "render production witness green",
            "production identity pin green",
            "devsystem final gate green",
            "production activation closed",
        ],
        "active_blocker": None,
        "deferred_findings": [],
        "evidence_fingerprints": [],
        "action_history": [],
        "checkpoints": [
            {
                "id": "A9.13",
                "state": "DONE",
                "entry_condition": "Streamlit telemetry implementation certified",
                "exit_condition": "protected main verified",
                "evidence": {"main_verified": True},
            },
            {
                "id": "A9.14b",
                "state": "ACTIVE",
                "entry_condition": "production identity drift diagnosed",
                "exit_condition": "Render telemetry witness green",
                "evidence": {},
            },
            {
                "id": "A9.14c",
                "state": "PENDING",
                "entry_condition": "Render telemetry witness green",
                "exit_condition": "production identity pin green",
                "evidence": {},
            },
            {
                "id": "A9.14d",
                "state": "PENDING",
                "entry_condition": "production identity pin green",
                "exit_condition": "fresh production verification green",
                "evidence": {},
            },
            {
                "id": "A9.CLOSE",
                "state": "PENDING",
                "entry_condition": "fresh production verification green",
                "exit_condition": "A9 closed",
                "evidence": {},
            },
        ],
    }


def _action(checkpoint_id: str, action_type: str, target: str, **overrides: Any) -> dict[str, Any]:
    action: dict[str, Any] = {
        "task_id": "monster-a9-replay-v1",
        "checkpoint_id": checkpoint_id,
        "action_type": action_type,
        "target": target,
        "inputs": {},
        "evidence_class": "a9_replay",
        "scope_relation": "in_scope",
        "retry": False,
        "failure_class": None,
        "new_hypothesis": False,
        "requires_user": False,
        "resolvable_with_available_tools": True,
    }
    action.update(overrides)
    return action


def _record(history: list[dict[str, Any]], action: dict[str, Any], result: str, **extra: Any) -> None:
    item = {
        "fingerprint": fingerprint_action(action),
        "result": result,
    }
    item.update(extra)
    history.append(item)


def _require_decision(payload: dict[str, Any], expected: str, label: str) -> None:
    actual = payload.get("decision")
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected}, got {actual}: {payload}")


def run_replay() -> dict[str, Any]:
    policy = load_policy()
    ledger = _ledger()
    history: list[dict[str, Any]] = []
    duplicate_proofs_rejected = 0
    closed_checkpoint_reopens_rejected = 0
    second_blockers_deferred = 0
    in_scope_approval_stops = 0
    max_active_blockers = 0

    validate_ledger(ledger)

    # A9.14b starts with a production proof against the pre-repair runtime.
    old_proof = _action(
        "A9.14b",
        "production_proof",
        "render:/health+posthog:fingerprint",
        inputs={"render_commit": "1ddd2a3", "streamlit_main": "31345d4", "activation_epoch": 1},
        evidence_class="production_activation",
    )
    first = decide(ledger, old_proof, history, policy)
    _require_decision(first, "ALLOW_ADVANCE", "initial production proof")
    _record(history, old_proof, "failure", failure_class="production_identity")

    # The root cause becomes the one active blocker: Render identity drift.
    blocker_action = _action(
        "A9.14b",
        "open_blocker",
        "production-identity",
        inputs={"blocker_id": "production-identity", "expected": "5c3c800", "actual": "1ddd2a3"},
        evidence_class="production_identity",
    )
    blocker_decision = decide(ledger, blocker_action, history, policy)
    _require_decision(blocker_decision, "ALLOW_ADVANCE", "open production identity blocker")
    ledger["active_blocker"] = {
        "blocker_id": "production-identity",
        "checkpoint_id": "A9.14b",
        "root_cause_class": "production_identity",
    }
    max_active_blockers = max(max_active_blockers, 1)
    validate_ledger(ledger)

    # A repeat of the unchanged Render/PostHog proof is forbidden.
    duplicate = decide(ledger, old_proof, history, policy)
    _require_decision(duplicate, "REJECT_DUPLICATE_PROOF", "unchanged production proof")
    duplicate_proofs_rejected += 1

    # A second telemetry blocker cannot steal focus from production identity.
    second_blocker = _action(
        "A9.14b",
        "open_blocker",
        "posthog:event-proof",
        inputs={"blocker_id": "telemetry-proof"},
        evidence_class="telemetry",
    )
    second_blocker_result = decide(ledger, second_blocker, history, policy)
    _require_decision(second_blocker_result, "DEFER_SIDE_QUEST", "second blocker")
    second_blockers_deferred += 1

    # A closed checkpoint cannot be reopened just to re-prove old work.
    reopen = _action(
        "A9.13",
        "reopen_checkpoint",
        "streamlit-telemetry-implementation",
        inputs={"reason": "recheck"},
    )
    reopen_result = decide(ledger, reopen, history, policy)
    _require_decision(reopen_result, "REJECT_CLOSED_CHECKPOINT_REOPEN", "closed checkpoint reopen")
    closed_checkpoint_reopens_rejected += 1

    # The witness reveals a stale telemetry test contract. This is directly in
    # scope, so Strict Auto-Continue permits the repair without asking again.
    repair = _action(
        "A9.14b",
        "in_scope_repair",
        "tests/test_monster_telemetry_probe_v1.py",
        inputs={"contract": "queued->not_flushed/flushed", "repair_scope": "test-only"},
        evidence_class="test_contract",
    )
    repair_result = decide(ledger, repair, history, policy)
    if repair_result.get("decision") == "STOP_EXTERNAL_BLOCKER":
        in_scope_approval_stops += 1
    _require_decision(repair_result, "ALLOW_ADVANCE", "in-scope stale-test repair")
    _record(history, repair, "success")

    # The repaired runtime gets a new revision; changed inputs make a fresh proof
    # legitimate rather than a duplicate retry.
    new_proof = _action(
        "A9.14b",
        "production_proof",
        "render:/health+readiness",
        inputs={"render_commit": "3228d1e", "deployment": "dep-new", "activation_epoch": 2},
        evidence_class="production_identity",
    )
    new_proof_result = decide(ledger, new_proof, history, policy)
    _require_decision(new_proof_result, "ALLOW_ADVANCE", "changed-runtime production proof")
    _record(history, new_proof, "success")

    # One GREEN witness resolves the active blocker and closes A9.14b.
    witness = _action(
        "A9.14b",
        "certification_witness",
        "render:/health+ready",
        inputs={"render_commit": "3228d1e", "witness": "green"},
        evidence_class="production_witness",
    )
    witness_result = decide(ledger, witness, history, policy)
    _require_decision(witness_result, "ALLOW_ADVANCE", "Render witness")
    _record(history, witness, "success")
    ledger = transition_checkpoint(
        ledger,
        "A9.14b",
        "DONE",
        evidence={"render_witness": "GREEN", "render_commit": "3228d1e"},
    )

    # A9.14c: immutable production identity pin follows the certified witness.
    pin = _action(
        "A9.14c",
        "update_identity_pin",
        "devsystem/production_targets_v1.json",
        inputs={"certified_commit": "3228d1e"},
        evidence_class="production_identity_pin",
    )
    pin_result = decide(ledger, pin, history, policy)
    _require_decision(pin_result, "ALLOW_ADVANCE", "identity pin")
    _record(history, pin, "success")
    ledger = transition_checkpoint(
        ledger,
        "A9.14c",
        "DONE",
        evidence={"identity_pin": "GREEN", "certified_commit": "3228d1e"},
    )

    # A9.14d: fresh permanent gate / production verification.
    final_gate = _action(
        "A9.14d",
        "final_gate",
        "devsystem-final-gate",
        inputs={"main_commit": "fcfac157", "production_identity": "3228d1e"},
        evidence_class="devsystem_final_gate",
    )
    final_gate_result = decide(ledger, final_gate, history, policy)
    _require_decision(final_gate_result, "ALLOW_ADVANCE", "fresh final gate")
    _record(history, final_gate, "success")
    ledger = transition_checkpoint(
        ledger,
        "A9.14d",
        "DONE",
        evidence={"devsystem_final_gate": "GREEN", "production_verification": "GREEN"},
    )

    # Final activation closes the declared A9 finish line.
    close = _action(
        "A9.CLOSE",
        "close_task",
        "monster:A9",
        inputs={"all_exit_conditions": True},
        evidence_class="task_closure",
    )
    close_result = decide(ledger, close, history, policy)
    _require_decision(close_result, "ALLOW_ADVANCE", "A9 closure")
    _record(history, close, "success")
    ledger = transition_checkpoint(
        ledger,
        "A9.CLOSE",
        "DONE",
        evidence={"A9": "GREEN_CLOSED"},
    )
    final_ledger = validate_ledger(ledger)

    # Once closed, even a plausible-sounding extra certification action must not
    # create A9.15 or any other invented checkpoint.
    checkpoint_count_before = len(ledger["checkpoints"])
    after_finish = _action(
        "A9.CLOSE",
        "one_more_proof",
        "posthog:final-recheck",
        inputs={"reason": "just-one-more-check"},
    )
    after_finish_result = decide(ledger, after_finish, history, policy)
    _require_decision(after_finish_result, "TASK_COMPLETE", "post-finish action")
    invented_post_finish_checkpoints = len(ledger["checkpoints"]) - checkpoint_count_before

    result = {
        "status": "GREEN",
        "scenario": SCENARIO,
        "duplicate_proofs_rejected": duplicate_proofs_rejected,
        "closed_checkpoint_reopens_rejected": closed_checkpoint_reopens_rejected,
        "second_blockers_deferred": second_blockers_deferred,
        "max_active_blockers": max_active_blockers,
        "in_scope_approval_stops": in_scope_approval_stops,
        "final_task_status": final_ledger["task_status"],
        "remaining_checkpoints": final_ledger["remaining_checkpoints"],
        "post_finish_decision": after_finish_result["decision"],
        "invented_post_finish_checkpoints": invented_post_finish_checkpoints,
        "history_events": len(history),
    }
    print("MONSTER_A9_ANTI_LOOP_REPLAY_GREEN")
    print(json.dumps(result, indent=2, sort_keys=True))
    return result


if __name__ == "__main__":
    run_replay()
