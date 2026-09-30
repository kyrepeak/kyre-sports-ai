"""MONSTER 2A Enforcement Step 1 — Mandatory Action Gate V1.

Fail-closed front door for MONSTER control-plane actions.

Every covered action must be authorized here before execution:
- while one authoritative async run is live, Step 2A / Automatic Loop Kill owns
  the decision and duplicate observations are autonomously skipped;
- outside live async work, a matching Forward Motion V2 authorization receipt
  is required;
- unknown actions, missing authorization, mismatched receipts, and stale async
  identities are blocked.

This module performs no network calls and no repository/product mutations.
"""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from devsystem.action_ledger_v2 import (
    AUTHORIZED_DECISIONS,
    ActionLedgerFailure,
    build_receipt,
    validate_receipt,
)
from devsystem.automatic_loop_kill_v1 import (
    decide_control_action,
    fingerprint_control_cycle,
)
from devsystem.forward_motion_v2 import fingerprint_action
from devsystem.persistent_execution_brain_v1 import (
    BrainStateInput,
    build_state,
    validate_state,
)

VERSION = "MONSTER_2A_MANDATORY_ACTION_GATE_V1"
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False

GATED_ACTION_TYPES = frozenset({
    "observe_async",
    "poll_status",
    "read_status",
    "gather_evidence",
    "classify_terminal_result",
    "patch",
    "rerun",
    "start_run",
    "start_competing_run",
    "dispatch_workflow",
    "update_branch",
    "merge",
    "create_pr",
    "edit_product",
})
ASYNC_OBSERVATION_ACTIONS = frozenset({"observe_async", "poll_status", "read_status"})
_REQUIRED_ACTION_FIELDS = ("task_id", "checkpoint_id", "action_type", "target")


class Mandatory2AActionGateFailure(RuntimeError):
    pass


def _base_result(
    decision: str,
    reason: str,
    *,
    allowed: bool,
    action_type: str,
    **extra: Any,
) -> dict[str, Any]:
    result = {
        "version": VERSION,
        "decision": decision,
        "reason": reason,
        "allowed": bool(allowed),
        "gate_required": True,
        "two_a_enforced": True,
        "action_type": action_type,
    }
    result.update(extra)
    return result


def _validate_action(action: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(action, Mapping):
        raise Mandatory2AActionGateFailure("action must be an object")
    value = deepcopy(dict(action))
    missing = [
        field for field in _REQUIRED_ACTION_FIELDS
        if not str(value.get(field) or "").strip()
    ]
    if missing:
        raise Mandatory2AActionGateFailure(
            "action missing required fields: " + ", ".join(missing)
        )
    value["action_type"] = str(value["action_type"]).strip()
    return value


def _validate_forward_authorization(
    action: Mapping[str, Any],
    forward_decision: Mapping[str, Any] | None,
) -> tuple[bool, str, str | None]:
    if not isinstance(forward_decision, Mapping):
        return False, "forward-motion authorization is required", None

    decision = str(forward_decision.get("decision") or "")
    if decision not in AUTHORIZED_DECISIONS:
        return False, f"forward-motion decision is not authorized: {decision or 'missing'}", None

    receipt = forward_decision.get("receipt")
    try:
        validation = validate_receipt(receipt)
    except (ActionLedgerFailure, TypeError) as exc:
        return False, f"forward-motion receipt is invalid: {exc}", None

    payload = receipt.get("payload") if isinstance(receipt, Mapping) else None
    if not isinstance(payload, Mapping):
        return False, "forward-motion receipt payload is missing", None

    if str(payload.get("task_id") or "") != str(action["task_id"]):
        return False, "forward-motion receipt task mismatch", None
    if str(payload.get("checkpoint_id") or "") != str(action["checkpoint_id"]):
        return False, "forward-motion receipt checkpoint mismatch", None

    expected_fp = fingerprint_action(dict(action))
    if str(payload.get("action_fingerprint") or "") != expected_fp:
        return False, "forward-motion receipt does not authorize this exact action", None

    return True, "matching forward-motion authorization receipt", str(validation["receipt_hash"])


def authorize_action(
    brain_state: Mapping[str, Any],
    action: Mapping[str, Any],
    history: Sequence[Mapping[str, Any]],
    *,
    forward_decision: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the mandatory Step-2A authorization decision for one action.

    Callers must treat allowed=False as a hard stop. This function is read-only.
    """
    brain = validate_state(brain_state)
    proposed = _validate_action(action)
    action_type = proposed["action_type"]

    if action_type not in GATED_ACTION_TYPES:
        return _base_result(
            "TWO_A_UNKNOWN_ACTION_BLOCKED",
            "unknown action types fail closed instead of bypassing Step 2A",
            allowed=False,
            action_type=action_type,
            next_legal_action=brain["next_legal_action"],
        )

    execution = brain["execution"]

    if execution["state"] == "WAITING_ON_ASYNC":
        loop_action = deepcopy(proposed)
        loop_action.setdefault("authoritative_run_id", execution["authoritative_run_id"])
        if execution.get("authoritative_job_id") is not None:
            loop_action.setdefault("authoritative_job_id", execution["authoritative_job_id"])
        loop_action.setdefault("observed_async_state", execution["async_state"])
        loop_action.setdefault("evidence", {
            "run_id": execution["authoritative_run_id"],
            "job_id": execution.get("authoritative_job_id"),
            "state": execution["async_state"],
        })

        loop_decision = decide_control_action(brain, loop_action, history)
        source_decision = str(loop_decision.get("decision") or "")
        allowed = source_decision in {
            "AUTHORIZED_OBSERVE",
            "AUTHORIZED_TERMINAL_TRANSITION",
        }
        skipped = source_decision == "LOOP_SKIPPED_CONTINUE"

        return _base_result(
            "TWO_A_" + source_decision,
            str(loop_decision.get("reason") or ""),
            allowed=allowed,
            action_type=action_type,
            authorization_source="automatic_loop_kill_v1",
            skipped=skipped,
            source_decision=source_decision,
            next_legal_action=loop_decision.get("next_legal_action"),
            requires_user_intervention=loop_decision.get("requires_user_intervention"),
            control_cycle_fingerprint=loop_decision.get("control_cycle_fingerprint"),
        )

    if action_type in ASYNC_OBSERVATION_ACTIONS:
        return _base_result(
            "TWO_A_NO_LIVE_ASYNC_BLOCKED",
            "async observation is illegal when no authoritative async run is live",
            allowed=False,
            action_type=action_type,
            next_legal_action=brain["next_legal_action"],
        )

    ok, reason, receipt_hash = _validate_forward_authorization(
        proposed,
        forward_decision,
    )
    if not ok:
        return _base_result(
            "TWO_A_AUTHORIZATION_REQUIRED",
            reason,
            allowed=False,
            action_type=action_type,
            authorization_source="forward_motion_v2",
            next_legal_action=brain["next_legal_action"],
        )

    return _base_result(
        "TWO_A_AUTHORIZED",
        reason,
        allowed=True,
        action_type=action_type,
        authorization_source="forward_motion_v2",
        forward_receipt_hash=receipt_hash,
        next_legal_action=brain["next_legal_action"],
    )


def require_authorized(result: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(result, Mapping) or result.get("allowed") is not True:
        decision = str(result.get("decision") if isinstance(result, Mapping) else "missing")
        raise Mandatory2AActionGateFailure(
            f"Step 2A authorization required before execution: {decision}"
        )
    return deepcopy(dict(result))


def _active_brain() -> dict[str, Any]:
    return build_state(BrainStateInput(
        program_id="self-test",
        program_title="Mandatory 2A gate self-test",
        total_steps=2,
        current_step=1,
        step_title="Mandatory Action Gate",
        execution_state="ACTIVE",
        repository="owner/repo",
        main_sha="1" * 40,
        work_branch="mandatory-2a-gate",
        observed_head_sha="2" * 40,
        next_legal_action="Execute authorized control-plane action.",
        completed_steps=(),
        frozen_steps=(),
        remaining_steps=(2,),
        updated_at_utc="2026-09-30T03:20:00Z",
    ))


def _waiting_brain() -> dict[str, Any]:
    return build_state(BrainStateInput(
        program_id="self-test",
        program_title="Mandatory 2A gate self-test",
        total_steps=2,
        current_step=1,
        step_title="Mandatory Action Gate",
        execution_state="WAITING_ON_ASYNC",
        repository="owner/repo",
        main_sha="1" * 40,
        work_branch="mandatory-2a-gate",
        observed_head_sha="2" * 40,
        next_legal_action="Wait for run 9001.",
        completed_steps=(),
        frozen_steps=(),
        remaining_steps=(2,),
        authoritative_run_id=9001,
        authoritative_job_id=7001,
        async_state="IN_PROGRESS",
        updated_at_utc="2026-09-30T03:20:00Z",
    ))


def _forward_decision(action: Mapping[str, Any]) -> dict[str, Any]:
    receipt = build_receipt({
        "policy_version": 2,
        "task_id": str(action["task_id"]),
        "checkpoint_id": str(action["checkpoint_id"]),
        "action_fingerprint": fingerprint_action(dict(action)),
        "root_cause_fingerprint": "r" * 64,
        "evidence_fingerprint": "e" * 64,
        "relevant_input_fingerprint": "i" * 64,
        "decision": "AUTHORIZED",
        "previous_chain_hash": "0" * 64,
        "event_nonce": "mandatory-2a-step1-self-test",
        "override_event_id": None,
    })
    return {"decision": "AUTHORIZED", "receipt": receipt}


def contract_self_test() -> dict[str, Any]:
    active = _active_brain()
    mutation = {
        "task_id": "self-test",
        "checkpoint_id": "1",
        "action_type": "merge",
        "target": "github:pr/1",
        "inputs": {"head": "2" * 40},
    }

    missing = authorize_action(active, mutation, [])
    allowed = authorize_action(
        active,
        mutation,
        [],
        forward_decision=_forward_decision(mutation),
    )
    tampered = dict(mutation)
    tampered["target"] = "github:pr/2"
    mismatch = authorize_action(
        active,
        tampered,
        [],
        forward_decision=_forward_decision(mutation),
    )

    waiting = _waiting_brain()
    patch = {
        "task_id": "self-test",
        "checkpoint_id": "1",
        "action_type": "patch",
        "target": "github:mutation",
    }
    patch_blocked = authorize_action(waiting, patch, [])

    observe = {
        "task_id": "self-test",
        "checkpoint_id": "1",
        "action_type": "observe_async",
        "target": "github:run/9001",
        "authoritative_run_id": 9001,
        "authoritative_job_id": 7001,
        "observed_async_state": "IN_PROGRESS",
        "evidence": {"run_id": 9001, "job_id": 7001, "state": "IN_PROGRESS"},
    }
    first_observe = authorize_action(waiting, observe, [])
    history = [{
        "control_cycle_fingerprint": fingerprint_control_cycle(observe),
        "observed_async_state": "IN_PROGRESS",
    }]
    duplicate = authorize_action(waiting, observe, history)
    unknown = authorize_action(active, {
        "task_id": "self-test",
        "checkpoint_id": "1",
        "action_type": "future_unregistered_mutation",
        "target": "github:unknown",
    }, [])

    result = {
        "status": "GREEN",
        "version": VERSION,
        "mandatory_gate": True,
        "missing_authorization_fails_closed": missing["allowed"] is False,
        "matching_forward_receipt_authorizes": allowed["allowed"] is True,
        "receipt_action_mismatch_blocked": mismatch["allowed"] is False,
        "live_async_mutation_blocked": patch_blocked["source_decision"] == "ASYNC_LOCKED",
        "first_async_observation_authorized": first_observe["allowed"] is True,
        "duplicate_poll_autonomously_skipped": (
            duplicate["source_decision"] == "LOOP_SKIPPED_CONTINUE"
            and duplicate["allowed"] is False
            and duplicate["requires_user_intervention"] is False
        ),
        "unknown_action_fails_closed": unknown["allowed"] is False,
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
    }
    required = (
        "mandatory_gate",
        "missing_authorization_fails_closed",
        "matching_forward_receipt_authorizes",
        "receipt_action_mismatch_blocked",
        "live_async_mutation_blocked",
        "first_async_observation_authorized",
        "duplicate_poll_autonomously_skipped",
        "unknown_action_fails_closed",
    )
    if not all(result[key] is True for key in required):
        raise Mandatory2AActionGateFailure("mandatory 2A action gate self-test failed")
    return result


if __name__ == "__main__":
    print("MONSTER_2A_MANDATORY_ACTION_GATE_V1_GREEN")
    print(json.dumps(contract_self_test(), indent=2, sort_keys=True))
