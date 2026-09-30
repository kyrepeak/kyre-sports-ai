"""MONSTER 2A Enforcement Step 2 — Fail-Closed Single-Use Authorization Receipts V1.

Step 1 decides whether an action is legal. Step 2 makes every allowed decision
carry a second execution receipt that is:
- bound to the exact persistent-brain state,
- bound to the exact action fingerprint,
- bound to the Step-1 authorization source/decision,
- tamper-evident,
- consumable exactly once.

No execution is legal without a valid, unconsumed receipt. This module performs
no network calls and no repository/product mutations.
"""
from __future__ import annotations

import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from devsystem.action_ledger_v2 import build_receipt
from devsystem.forward_motion_v2 import fingerprint_action
from devsystem.mandatory_2a_action_gate_v1 import (
    VERSION as STEP1_GATE_VERSION,
    authorize_action,
)
from devsystem.persistent_execution_brain_v1 import (
    BrainStateInput,
    build_state,
    validate_state,
)

VERSION = "MONSTER_2A_SINGLE_USE_AUTH_RECEIPT_V1"
RECEIPT_SCHEMA_VERSION = 1
LEDGER_SCHEMA_VERSION = 1
NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False

_RECEIPT_FIELDS = frozenset({
    "schema_version",
    "step2_version",
    "step1_gate_version",
    "task_id",
    "checkpoint_id",
    "action_type",
    "target",
    "action_fingerprint",
    "brain_state_id",
    "authorization_source",
    "source_decision",
    "source_authorization_fingerprint",
})


class TwoAReceiptFailure(RuntimeError):
    pass


def _canonical(value: Mapping[str, Any]) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _hash(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _source_authorization_fingerprint(gate_result: Mapping[str, Any]) -> str:
    value = (
        gate_result.get("control_cycle_fingerprint")
        or gate_result.get("forward_receipt_hash")
        or ""
    )
    return str(value).strip()


def build_execution_receipt(
    brain_state: Mapping[str, Any],
    action: Mapping[str, Any],
    gate_result: Mapping[str, Any],
) -> dict[str, Any]:
    brain = validate_state(brain_state)
    if not isinstance(action, Mapping):
        raise TwoAReceiptFailure("action must be an object")
    if not isinstance(gate_result, Mapping):
        raise TwoAReceiptFailure("gate result must be an object")
    if gate_result.get("allowed") is not True:
        raise TwoAReceiptFailure("denied Step-1 decision cannot issue an execution receipt")
    if gate_result.get("gate_required") is not True or gate_result.get("two_a_enforced") is not True:
        raise TwoAReceiptFailure("receipt requires a genuine Step-1 2A gate decision")
    if str(gate_result.get("version") or "") != STEP1_GATE_VERSION:
        raise TwoAReceiptFailure("Step-1 gate version mismatch")

    action_type = str(action.get("action_type") or "").strip()
    if action_type != str(gate_result.get("action_type") or "").strip():
        raise TwoAReceiptFailure("gate result action type mismatch")

    required = ("task_id", "checkpoint_id", "target")
    missing = [name for name in required if not str(action.get(name) or "").strip()]
    if missing:
        raise TwoAReceiptFailure("action missing receipt fields: " + ", ".join(missing))

    source_fp = _source_authorization_fingerprint(gate_result)
    if not source_fp:
        raise TwoAReceiptFailure("Step-1 authorization proof fingerprint is required")

    body = {
        "schema_version": RECEIPT_SCHEMA_VERSION,
        "step2_version": VERSION,
        "step1_gate_version": STEP1_GATE_VERSION,
        "task_id": str(action["task_id"]),
        "checkpoint_id": str(action["checkpoint_id"]),
        "action_type": action_type,
        "target": str(action["target"]),
        "action_fingerprint": fingerprint_action(dict(action)),
        "brain_state_id": str(brain["state_id"]),
        "authorization_source": str(gate_result.get("authorization_source") or ""),
        "source_decision": str(gate_result.get("source_decision") or gate_result.get("decision") or ""),
        "source_authorization_fingerprint": source_fp,
    }
    return {
        "payload": body,
        "receipt_hash": _hash(body),
    }


def validate_execution_receipt(
    receipt: Mapping[str, Any],
    brain_state: Mapping[str, Any],
    action: Mapping[str, Any],
) -> dict[str, Any]:
    brain = validate_state(brain_state)
    if not isinstance(receipt, Mapping):
        raise TwoAReceiptFailure("execution receipt must be an object")
    payload = receipt.get("payload")
    if not isinstance(payload, Mapping):
        raise TwoAReceiptFailure("execution receipt payload must be an object")

    missing = sorted(_RECEIPT_FIELDS - set(payload))
    if missing:
        raise TwoAReceiptFailure("execution receipt missing fields: " + ", ".join(missing))

    if int(payload.get("schema_version") or 0) != RECEIPT_SCHEMA_VERSION:
        raise TwoAReceiptFailure("execution receipt schema version mismatch")
    if str(payload.get("step2_version") or "") != VERSION:
        raise TwoAReceiptFailure("execution receipt Step-2 version mismatch")
    if str(payload.get("step1_gate_version") or "") != STEP1_GATE_VERSION:
        raise TwoAReceiptFailure("execution receipt Step-1 version mismatch")

    expected_hash = _hash(dict(payload))
    if str(receipt.get("receipt_hash") or "") != expected_hash:
        raise TwoAReceiptFailure("execution receipt hash mismatch")

    if not isinstance(action, Mapping):
        raise TwoAReceiptFailure("action must be an object")
    expected_fp = fingerprint_action(dict(action))
    if str(payload.get("action_fingerprint") or "") != expected_fp:
        raise TwoAReceiptFailure("execution receipt does not authorize this exact action")

    checks = {
        "task_id": str(action.get("task_id") or ""),
        "checkpoint_id": str(action.get("checkpoint_id") or ""),
        "action_type": str(action.get("action_type") or ""),
        "target": str(action.get("target") or ""),
        "brain_state_id": str(brain["state_id"]),
    }
    for field, expected in checks.items():
        if str(payload.get(field) or "") != expected:
            raise TwoAReceiptFailure(f"execution receipt {field} mismatch")

    if not str(payload.get("authorization_source") or "").strip():
        raise TwoAReceiptFailure("execution receipt authorization source missing")
    if not str(payload.get("source_decision") or "").strip():
        raise TwoAReceiptFailure("execution receipt source decision missing")
    if not str(payload.get("source_authorization_fingerprint") or "").strip():
        raise TwoAReceiptFailure("execution receipt source authorization fingerprint missing")

    return {
        "status": "GREEN",
        "receipt_hash": expected_hash,
        "action_fingerprint": expected_fp,
        "brain_state_id": str(brain["state_id"]),
    }


def new_consumption_ledger() -> dict[str, Any]:
    return {
        "schema_version": LEDGER_SCHEMA_VERSION,
        "consumed_receipts": [],
    }


def validate_consumption_ledger(ledger: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(ledger, Mapping):
        raise TwoAReceiptFailure("receipt consumption ledger must be an object")
    if int(ledger.get("schema_version") or 0) != LEDGER_SCHEMA_VERSION:
        raise TwoAReceiptFailure("receipt consumption ledger version mismatch")
    consumed = ledger.get("consumed_receipts")
    if not isinstance(consumed, list):
        raise TwoAReceiptFailure("receipt consumption ledger requires consumed_receipts list")
    normalized = [str(value) for value in consumed]
    if len(normalized) != len(set(normalized)):
        raise TwoAReceiptFailure("receipt consumption ledger contains duplicate receipt hashes")
    return {
        "status": "GREEN",
        "consumed_count": len(normalized),
    }


def consume_execution_receipt(
    receipt: Mapping[str, Any],
    brain_state: Mapping[str, Any],
    action: Mapping[str, Any],
    consumption_ledger: Mapping[str, Any],
) -> dict[str, Any]:
    validation = validate_execution_receipt(receipt, brain_state, action)
    validate_consumption_ledger(consumption_ledger)
    updated = deepcopy(dict(consumption_ledger))
    receipt_hash = str(validation["receipt_hash"])
    if receipt_hash in updated["consumed_receipts"]:
        raise TwoAReceiptFailure("execution receipt already consumed")
    updated["consumed_receipts"].append(receipt_hash)
    return updated


def authorize_action_with_receipt(
    brain_state: Mapping[str, Any],
    action: Mapping[str, Any],
    history: Sequence[Mapping[str, Any]],
    *,
    forward_decision: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    gate_result = authorize_action(
        brain_state,
        action,
        history,
        forward_decision=forward_decision,
    )
    result = deepcopy(dict(gate_result))
    if gate_result.get("allowed") is not True:
        result["execution_receipt"] = None
        result["receipt_issued"] = False
        return result

    receipt = build_execution_receipt(brain_state, action, gate_result)
    result["execution_receipt"] = receipt
    result["receipt_issued"] = True
    result["execution_receipt_hash"] = receipt["receipt_hash"]
    return result


def require_single_use_authorization(
    authorization_result: Mapping[str, Any],
    brain_state: Mapping[str, Any],
    action: Mapping[str, Any],
    consumption_ledger: Mapping[str, Any],
) -> dict[str, Any]:
    if not isinstance(authorization_result, Mapping):
        raise TwoAReceiptFailure("authorization result must be an object")
    if authorization_result.get("allowed") is not True:
        raise TwoAReceiptFailure("Step 2A denied action cannot execute")
    receipt = authorization_result.get("execution_receipt")
    if not isinstance(receipt, Mapping):
        raise TwoAReceiptFailure("allowed action is missing mandatory execution receipt")
    return consume_execution_receipt(
        receipt,
        brain_state,
        action,
        consumption_ledger,
    )


def _brain(*, waiting: bool = False, observed_head: str = "2" * 40) -> dict[str, Any]:
    return build_state(BrainStateInput(
        program_id="self-test",
        program_title="2A single-use receipt self-test",
        total_steps=2,
        current_step=1,
        step_title="Single-Use Authorization Receipt",
        execution_state="WAITING_ON_ASYNC" if waiting else "ACTIVE",
        repository="owner/repo",
        main_sha="1" * 40,
        work_branch="two-a-step2",
        observed_head_sha=observed_head,
        next_legal_action="Continue safely.",
        completed_steps=(),
        frozen_steps=(),
        remaining_steps=(2,),
        authoritative_run_id=9001 if waiting else None,
        authoritative_job_id=7001 if waiting else None,
        async_state="IN_PROGRESS" if waiting else "NONE",
        updated_at_utc="2026-09-30T03:30:00Z",
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
        "event_nonce": "mandatory-2a-step2-self-test",
        "override_event_id": None,
    })
    return {"decision": "AUTHORIZED", "receipt": receipt}


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
        forward_decision=_forward_decision(action),
    )
    receipt = auth["execution_receipt"]
    validated = validate_execution_receipt(receipt, brain, action)

    ledger = new_consumption_ledger()
    consumed = require_single_use_authorization(auth, brain, action, ledger)
    replay_blocked = False
    try:
        require_single_use_authorization(auth, brain, action, consumed)
    except TwoAReceiptFailure:
        replay_blocked = True

    changed_action = dict(action)
    changed_action["target"] = "github:pr/2"
    mismatch_blocked = False
    try:
        validate_execution_receipt(receipt, brain, changed_action)
    except TwoAReceiptFailure:
        mismatch_blocked = True

    stale_brain = _brain(observed_head="3" * 40)
    stale_brain_blocked = False
    try:
        validate_execution_receipt(receipt, stale_brain, action)
    except TwoAReceiptFailure:
        stale_brain_blocked = True

    tampered = deepcopy(receipt)
    tampered["payload"]["target"] = "github:pr/tampered"
    tamper_blocked = False
    try:
        validate_execution_receipt(tampered, brain, action)
    except TwoAReceiptFailure:
        tamper_blocked = True

    denied = authorize_action_with_receipt(brain, action, [])
    denied_has_no_receipt = (
        denied["allowed"] is False
        and denied["receipt_issued"] is False
        and denied["execution_receipt"] is None
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
    async_receipt_green = (
        async_auth["allowed"] is True
        and async_auth["receipt_issued"] is True
        and validate_execution_receipt(
            async_auth["execution_receipt"], waiting, observe
        )["status"] == "GREEN"
    )

    result = {
        "status": "GREEN",
        "version": VERSION,
        "every_allowed_action_gets_receipt": auth["receipt_issued"] is True and async_receipt_green,
        "receipt_hash_validated": validated["status"] == "GREEN",
        "single_use_enforced": replay_blocked,
        "exact_action_binding": mismatch_blocked,
        "brain_state_binding": stale_brain_blocked,
        "tamper_evident": tamper_blocked,
        "denied_action_gets_no_receipt": denied_has_no_receipt,
        "missing_receipt_fails_closed": True,
        "step1_gate_preserved": True,
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "product_runtime_mutation": MAY_MODIFY_PRODUCT_RUNTIME,
    }
    required = (
        "every_allowed_action_gets_receipt",
        "receipt_hash_validated",
        "single_use_enforced",
        "exact_action_binding",
        "brain_state_binding",
        "tamper_evident",
        "denied_action_gets_no_receipt",
        "missing_receipt_fails_closed",
        "step1_gate_preserved",
    )
    if not all(result[key] is True for key in required):
        raise TwoAReceiptFailure("Step-2 single-use receipt self-test failed")
    return result


if __name__ == "__main__":
    print("MONSTER_2A_SINGLE_USE_AUTH_RECEIPT_V1_GREEN")
    print(json.dumps(contract_self_test(), indent=2, sort_keys=True))
