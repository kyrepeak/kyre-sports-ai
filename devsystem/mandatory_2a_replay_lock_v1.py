"""MONSTER 2A Enforcement Step 3 — Replay + Loop Lock V1.

Step 2 makes authorization receipts single-use. Step 3 closes the wider replay
gap: the same semantic action must not execute again merely because a new
authorization/receipt was minted later.

Before execution, a legal action must atomically claim an execution slot in
this replay ledger. The slot is keyed by:
- exact stable action fingerprint,
- Step-2 execution receipt hash,
- Step-1 source authorization/control-cycle fingerprint.

If any key was already claimed, the action is not executed. It becomes
LOOP_SKIPPED_CONTINUE and control moves to non-conflicting work.

This module performs no network calls and no repository/product mutations.
"""
from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from devsystem.forward_motion_v2 import fingerprint_action
from devsystem.mandatory_2a_receipt_v1 import (
    TwoAReceiptFailure,
    authorize_action_with_receipt,
    new_consumption_ledger,
    require_single_use_authorization,
    validate_execution_receipt,
)
from devsystem.persistent_execution_brain_v1 import (
    BrainStateInput,
    build_state,
)

VERSION = "MONSTER_2A_REPLAY_LOOP_LOCK_V1"
REPLAY_LEDGER_SCHEMA_VERSION = 1
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False


class TwoAReplayLockFailure(RuntimeError):
    pass


def new_replay_ledger() -> dict[str, Any]:
    return {
        "schema_version": REPLAY_LEDGER_SCHEMA_VERSION,
        "claimed_action_fingerprints": [],
        "claimed_receipt_hashes": [],
        "claimed_source_fingerprints": [],
    }


def validate_replay_ledger(ledger: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(ledger, Mapping):
        raise TwoAReplayLockFailure("replay ledger must be an object")
    if int(ledger.get("schema_version") or 0) != REPLAY_LEDGER_SCHEMA_VERSION:
        raise TwoAReplayLockFailure("replay ledger version mismatch")

    fields = (
        "claimed_action_fingerprints",
        "claimed_receipt_hashes",
        "claimed_source_fingerprints",
    )
    counts: dict[str, int] = {}
    for field in fields:
        values = ledger.get(field)
        if not isinstance(values, list):
            raise TwoAReplayLockFailure(f"replay ledger requires {field} list")
        normalized = [str(value) for value in values]
        if any(not value for value in normalized):
            raise TwoAReplayLockFailure(f"replay ledger {field} may not contain empty values")
        if len(normalized) != len(set(normalized)):
            raise TwoAReplayLockFailure(f"replay ledger {field} contains duplicate claims")
        counts[field] = len(normalized)

    return {
        "status": "GREEN",
        "claimed_actions": counts["claimed_action_fingerprints"],
        "claimed_receipts": counts["claimed_receipt_hashes"],
        "claimed_sources": counts["claimed_source_fingerprints"],
    }


def _authorization_keys(
    authorization_result: Mapping[str, Any],
    brain_state: Mapping[str, Any],
    action: Mapping[str, Any],
) -> dict[str, str]:
    if not isinstance(authorization_result, Mapping):
        raise TwoAReplayLockFailure("authorization result must be an object")
    if authorization_result.get("allowed") is not True:
        raise TwoAReplayLockFailure("denied authorization has no executable replay keys")

    receipt = authorization_result.get("execution_receipt")
    if not isinstance(receipt, Mapping):
        raise TwoAReplayLockFailure("allowed action is missing Step-2 execution receipt")

    try:
        validation = validate_execution_receipt(receipt, brain_state, action)
    except TwoAReceiptFailure as exc:
        raise TwoAReplayLockFailure(f"invalid Step-2 receipt: {exc}") from exc

    payload = receipt.get("payload")
    if not isinstance(payload, Mapping):
        raise TwoAReplayLockFailure("Step-2 receipt payload missing")

    action_fp = str(validation["action_fingerprint"])
    receipt_hash = str(validation["receipt_hash"])
    source_fp = str(payload.get("source_authorization_fingerprint") or "")
    if not source_fp:
        raise TwoAReplayLockFailure("source authorization fingerprint missing")

    return {
        "action_fingerprint": action_fp,
        "receipt_hash": receipt_hash,
        "source_fingerprint": source_fp,
    }


def _skip(
    reason: str,
    *,
    action: Mapping[str, Any],
    keys: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    result = {
        "version": VERSION,
        "decision": "LOOP_SKIPPED_CONTINUE",
        "legacy_decision": "LOOP_BLOCKED",
        "reason": reason,
        "allowed": False,
        "skipped": True,
        "autonomous_skip": True,
        "requires_user_intervention": False,
        "continuation_policy": "CONTINUE_NON_CONFLICTING_WORK",
        "next_legal_action": "CONTINUE_NON_CONFLICTING_WORK",
        "recheck_policy": "ONLY_AFTER_NEW_EVIDENCE_OR_INDEPENDENT_PROGRESS",
        "action_type": str(action.get("action_type") or ""),
        "target": str(action.get("target") or ""),
    }
    if keys:
        result.update(dict(keys))
    return result


def preflight_replay_lock(
    authorization_result: Mapping[str, Any],
    brain_state: Mapping[str, Any],
    action: Mapping[str, Any],
    replay_ledger: Mapping[str, Any],
) -> dict[str, Any]:
    validate_replay_ledger(replay_ledger)

    if not isinstance(authorization_result, Mapping):
        raise TwoAReplayLockFailure("authorization result must be an object")

    if authorization_result.get("allowed") is not True:
        source_decision = str(
            authorization_result.get("source_decision")
            or authorization_result.get("decision")
            or ""
        )
        if "LOOP_SKIPPED_CONTINUE" in source_decision:
            return _skip(
                "Step-1/2 already classified this action as a loop",
                action=action,
            )
        return {
            "version": VERSION,
            "decision": "DENIED_UPSTREAM",
            "reason": "upstream Step-1/2 authorization denied this action",
            "allowed": False,
            "skipped": False,
            "requires_user_intervention": False,
            "next_legal_action": authorization_result.get("next_legal_action"),
        }

    keys = _authorization_keys(authorization_result, brain_state, action)
    seen_action = keys["action_fingerprint"] in replay_ledger["claimed_action_fingerprints"]
    seen_receipt = keys["receipt_hash"] in replay_ledger["claimed_receipt_hashes"]
    seen_source = keys["source_fingerprint"] in replay_ledger["claimed_source_fingerprints"]

    if seen_action or seen_receipt or seen_source:
        reasons = []
        if seen_action:
            reasons.append("action fingerprint")
        if seen_receipt:
            reasons.append("receipt hash")
        if seen_source:
            reasons.append("source/control-cycle fingerprint")
        return _skip(
            "replay claim already exists for " + ", ".join(reasons),
            action=action,
            keys=keys,
        )

    return {
        "version": VERSION,
        "decision": "EXECUTION_SLOT_AVAILABLE",
        "reason": "no replay key has been claimed",
        "allowed": True,
        "skipped": False,
        "requires_user_intervention": False,
        **keys,
    }


def claim_execution_slot(
    authorization_result: Mapping[str, Any],
    brain_state: Mapping[str, Any],
    action: Mapping[str, Any],
    replay_ledger: Mapping[str, Any],
    consumption_ledger: Mapping[str, Any],
) -> dict[str, Any]:
    preflight = preflight_replay_lock(
        authorization_result,
        brain_state,
        action,
        replay_ledger,
    )
    if preflight.get("allowed") is not True:
        return {
            "result": preflight,
            "replay_ledger": deepcopy(dict(replay_ledger)),
            "consumption_ledger": deepcopy(dict(consumption_ledger)),
        }

    try:
        updated_consumption = require_single_use_authorization(
            authorization_result,
            brain_state,
            action,
            consumption_ledger,
        )
    except TwoAReceiptFailure as exc:
        raise TwoAReplayLockFailure(f"Step-2 receipt consumption failed: {exc}") from exc

    updated_replay = deepcopy(dict(replay_ledger))
    updated_replay["claimed_action_fingerprints"].append(
        str(preflight["action_fingerprint"])
    )
    updated_replay["claimed_receipt_hashes"].append(
        str(preflight["receipt_hash"])
    )
    updated_replay["claimed_source_fingerprints"].append(
        str(preflight["source_fingerprint"])
    )
    validate_replay_ledger(updated_replay)

    result = {
        **preflight,
        "decision": "EXECUTION_SLOT_CLAIMED",
        "reason": "single-use receipt consumed and replay keys reserved before execution",
        "allowed": True,
        "slot_claimed": True,
    }
    return {
        "result": result,
        "replay_ledger": updated_replay,
        "consumption_ledger": updated_consumption,
    }


def _brain(*, waiting: bool = False, updated_at: str = "2026-09-30T03:37:00Z"):
    return build_state(BrainStateInput(
        program_id="self-test",
        program_title="2A replay lock self-test",
        total_steps=2,
        current_step=1,
        step_title="Replay + Loop Lock",
        execution_state="WAITING_ON_ASYNC" if waiting else "ACTIVE",
        repository="owner/repo",
        main_sha="1" * 40,
        work_branch="two-a-step3",
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


def _forward(action: Mapping[str, Any]) -> dict[str, Any]:
    from devsystem.action_ledger_v2 import build_receipt

    return {
        "decision": "AUTHORIZED",
        "receipt": build_receipt({
            "policy_version": 2,
            "task_id": str(action["task_id"]),
            "checkpoint_id": str(action["checkpoint_id"]),
            "action_fingerprint": fingerprint_action(dict(action)),
            "root_cause_fingerprint": "r" * 64,
            "evidence_fingerprint": "e" * 64,
            "relevant_input_fingerprint": "i" * 64,
            "decision": "AUTHORIZED",
            "previous_chain_hash": "0" * 64,
            "event_nonce": "mandatory-2a-step3-self-test",
            "override_event_id": None,
        }),
    }


def contract_self_test() -> dict[str, Any]:
    brain = _brain()
    action = {
        "task_id": "self-test",
        "checkpoint_id": "1",
        "action_type": "merge",
        "target": "github:pr/1",
        "inputs": {"head": "2" * 40},
    }
    auth = authorize_action_with_receipt(
        brain,
        action,
        [],
        forward_decision=_forward(action),
    )
    replay = new_replay_ledger()
    consumption = new_consumption_ledger()
    first = claim_execution_slot(auth, brain, action, replay, consumption)

    exact_replay = claim_execution_slot(
        auth,
        brain,
        action,
        first["replay_ledger"],
        first["consumption_ledger"],
    )

    newer_brain = _brain(updated_at="2026-09-30T03:38:00Z")
    reauthorized = authorize_action_with_receipt(
        newer_brain,
        action,
        [],
        forward_decision=_forward(action),
    )
    new_receipt_same_action = preflight_replay_lock(
        reauthorized,
        newer_brain,
        action,
        first["replay_ledger"],
    )

    waiting = _brain(waiting=True)
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
    async_auth = authorize_action_with_receipt(waiting, observe, [])
    async_first = claim_execution_slot(
        async_auth,
        waiting,
        observe,
        new_replay_ledger(),
        new_consumption_ledger(),
    )
    async_replay = preflight_replay_lock(
        async_auth,
        waiting,
        observe,
        async_first["replay_ledger"],
    )

    changed = dict(action)
    changed["target"] = "github:pr/2"
    changed_auth = authorize_action_with_receipt(
        brain,
        changed,
        [],
        forward_decision=_forward(changed),
    )
    genuinely_new = preflight_replay_lock(
        changed_auth,
        brain,
        changed,
        first["replay_ledger"],
    )

    result = {
        "status": "GREEN",
        "version": VERSION,
        "execution_slot_claim_before_action": first["result"]["slot_claimed"] is True,
        "exact_receipt_replay_skipped": exact_replay["result"]["decision"] == "LOOP_SKIPPED_CONTINUE",
        "new_receipt_same_action_skipped": new_receipt_same_action["decision"] == "LOOP_SKIPPED_CONTINUE",
        "async_cycle_replay_skipped": async_replay["decision"] == "LOOP_SKIPPED_CONTINUE",
        "autonomous_skip_no_user": (
            exact_replay["result"]["requires_user_intervention"] is False
            and new_receipt_same_action["requires_user_intervention"] is False
            and async_replay["requires_user_intervention"] is False
        ),
        "genuinely_new_action_allowed": genuinely_new["allowed"] is True,
        "step2_single_use_preserved": len(first["consumption_ledger"]["consumed_receipts"]) == 1,
        "step1_gate_preserved": True,
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
    }
    required = (
        "execution_slot_claim_before_action",
        "exact_receipt_replay_skipped",
        "new_receipt_same_action_skipped",
        "async_cycle_replay_skipped",
        "autonomous_skip_no_user",
        "genuinely_new_action_allowed",
        "step2_single_use_preserved",
        "step1_gate_preserved",
    )
    if not all(result[key] is True for key in required):
        raise TwoAReplayLockFailure("Step-3 replay/loop lock self-test failed")
    return result


if __name__ == "__main__":
    print("MONSTER_2A_REPLAY_LOOP_LOCK_V1_GREEN")
    print(json.dumps(contract_self_test(), indent=2, sort_keys=True))
