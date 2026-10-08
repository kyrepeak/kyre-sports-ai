"""API 2 Finalization Authority V1 Step 4 — Closeout Event Consumer.

Bridges Runless event-resume detection to exactly one Step-2A-authorized
closeout action. Tail-SLA/event telemetry is detection-only and can never grant
mutation authority. Canonical terminal truth always wins before execution.

The module has no built-in network or product/runtime mutation capability. Any
actual action is supplied explicitly by the caller as ``execute_action`` after
final MONSTER Step-2A global authority has already been issued for the exact
action/target pair.
"""
from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from typing import Any, Callable, Mapping

NETWORK_CALLS = False
AUTO_MUTATE = False
MAY_MODIFY_PRODUCT_RUNTIME = False
MUTATION_AUTHORITY_GRANTED = False
POLLING_REQUIRED = False
GITHUB_ACTIONS_FALLBACK = 0
TELEMETRY_DETECTION_ONLY = True

_HASH64 = re.compile(r"^[0-9a-f]{64}$")
_SUCCESS = {"SUCCESS", "GREEN", "COMPLETED", "OK"}


class CloseoutEventConsumerFailure(RuntimeError):
    pass


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _text(value: Any, field: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise CloseoutEventConsumerFailure(f"{field} is required")
    return text


def _hash64(value: Any, field: str) -> str:
    text = str(value or "").strip().lower()
    if not _HASH64.fullmatch(text):
        raise CloseoutEventConsumerFailure(f"{field} must be sha256")
    return text


def _base_result(decision: str, **extra: Any) -> dict[str, Any]:
    return {
        "decision": decision,
        "network_calls": NETWORK_CALLS,
        "auto_mutate": AUTO_MUTATE,
        "mutation_authority_granted": MUTATION_AUTHORITY_GRANTED,
        "polling_required": POLLING_REQUIRED,
        "github_actions_fallback": GITHUB_ACTIONS_FALLBACK,
        "telemetry_detection_only": TELEMETRY_DETECTION_ONLY,
        **extra,
    }


def _terminal(canonical_latch: Mapping[str, Any]) -> bool:
    canonical = canonical_latch.get("canonical_completion")
    return (
        canonical_latch.get("short_circuit") is True
        and isinstance(canonical, Mapping)
        and canonical.get("complete") is True
    )


def _validate_resume(resume_claim: Mapping[str, Any], action_type: str) -> str | None:
    if resume_claim.get("decision") != "RUNLESS_RESUME_CONSUMED":
        return "CLOSEOUT_RESUME_NOT_CONSUMED"
    if resume_claim.get("step_2a_required") is not True:
        return "CLOSEOUT_RESUME_CONTRACT_INVALID"
    if resume_claim.get("mutation_authority_granted") is not False:
        return "CLOSEOUT_RESUME_CONTRACT_INVALID"
    if str(resume_claim.get("next_legal_action") or "") != action_type:
        return "CLOSEOUT_RESUME_ACTION_MISMATCH"
    return None


def _validate_step2a(step2a_result: Mapping[str, Any], action: Mapping[str, Any]) -> str | None:
    if not (
        step2a_result.get("decision") == "GLOBAL_EXECUTION_AUTHORIZED"
        and step2a_result.get("allowed") is True
        and step2a_result.get("execution_authorized") is True
        and isinstance(step2a_result.get("execution_proof"), Mapping)
    ):
        return "CLOSEOUT_STEP2A_REQUIRED"

    if (
        str(step2a_result.get("action_type") or "") != str(action.get("action_type") or "")
        or str(step2a_result.get("target") or "") != str(action.get("target") or "")
    ):
        return "CLOSEOUT_STEP2A_SCOPE_MISMATCH"

    try:
        _hash64(step2a_result.get("execution_proof_hash"), "execution_proof_hash")
        _hash64(step2a_result.get("action_fingerprint"), "action_fingerprint")
    except CloseoutEventConsumerFailure:
        return "CLOSEOUT_STEP2A_REQUIRED"
    return None


def _consumer_key(
    *,
    workstream_id: str,
    continuation_packet_hash: str,
    action: Mapping[str, Any],
    execution_proof_hash: str,
    action_fingerprint: str,
) -> str:
    return _digest(
        {
            "workstream_id": workstream_id,
            "continuation_packet_hash": continuation_packet_hash,
            "task_id": str(action.get("task_id") or ""),
            "checkpoint_id": str(action.get("checkpoint_id") or ""),
            "action_type": str(action.get("action_type") or ""),
            "target": str(action.get("target") or ""),
            "execution_proof_hash": execution_proof_hash,
            "action_fingerprint": action_fingerprint,
        }
    )


def consume_closeout_event(
    *,
    workstream_id: str,
    continuation_packet_hash: str,
    resume_claim: Mapping[str, Any],
    step2a_result: Mapping[str, Any],
    action: Mapping[str, Any],
    terminal_latch: Mapping[str, Any],
    consumer_ledger: Mapping[str, Any],
    execute_action: Callable[[Mapping[str, Any]], Mapping[str, Any]],
    telemetry: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Consume one Runless closeout event and execute at most one legal action.

    Ordering is intentional:
    1. canonical terminal truth wins;
    2. Runless resume must already be consumed one-shot;
    3. final Step-2A global authority must bind the exact action/target;
    4. prior consumer receipt blocks re-execution;
    5. the caller-supplied executor is invoked exactly once.

    No failure path retries automatically.
    """
    workstream = _text(workstream_id, "workstream_id")
    packet_hash = _hash64(continuation_packet_hash, "continuation_packet_hash")
    if not isinstance(resume_claim, Mapping):
        raise CloseoutEventConsumerFailure("resume_claim must be an object")
    if not isinstance(step2a_result, Mapping):
        raise CloseoutEventConsumerFailure("step2a_result must be an object")
    if not isinstance(action, Mapping):
        raise CloseoutEventConsumerFailure("action must be an object")
    if not isinstance(terminal_latch, Mapping):
        raise CloseoutEventConsumerFailure("terminal_latch must be an object")
    if not isinstance(consumer_ledger, Mapping):
        raise CloseoutEventConsumerFailure("consumer_ledger must be an object")
    if not callable(execute_action):
        raise CloseoutEventConsumerFailure("execute_action must be callable")

    action_type = _text(action.get("action_type"), "action.action_type")
    _text(action.get("target"), "action.target")
    _text(action.get("task_id"), "action.task_id")
    _text(action.get("checkpoint_id"), "action.checkpoint_id")
    ledger = deepcopy(dict(consumer_ledger))

    if _terminal(terminal_latch):
        return {
            "result": _base_result(
                "CLOSEOUT_ALREADY_TERMINAL",
                allowed=True,
                action_executed=False,
                executor_calls=0,
                duplicate_action_blocked=True,
                retry_allowed_now=False,
                next_legal_action="MOVE_TO_NEXT_STEP",
                terminal_digest=terminal_latch.get("terminal_digest"),
            ),
            "consumer_ledger": ledger,
            "receipt": None,
        }

    resume_error = _validate_resume(resume_claim, action_type)
    if resume_error:
        return {
            "result": _base_result(
                resume_error,
                allowed=False,
                action_executed=False,
                executor_calls=0,
                duplicate_action_blocked=False,
                retry_allowed_now=False,
                next_legal_action="WAIT_FOR_MATERIAL_EVENT",
            ),
            "consumer_ledger": ledger,
            "receipt": None,
        }

    step2a_error = _validate_step2a(step2a_result, action)
    if step2a_error:
        return {
            "result": _base_result(
                step2a_error,
                allowed=False,
                action_executed=False,
                executor_calls=0,
                duplicate_action_blocked=False,
                retry_allowed_now=False,
                next_legal_action="REQUEST_FRESH_STEP_2A_GLOBAL_AUTHORITY",
            ),
            "consumer_ledger": ledger,
            "receipt": None,
        }

    proof_hash = _hash64(step2a_result.get("execution_proof_hash"), "execution_proof_hash")
    action_fp = _hash64(step2a_result.get("action_fingerprint"), "action_fingerprint")
    key = _consumer_key(
        workstream_id=workstream,
        continuation_packet_hash=packet_hash,
        action=action,
        execution_proof_hash=proof_hash,
        action_fingerprint=action_fp,
    )
    if key in ledger:
        return {
            "result": _base_result(
                "CLOSEOUT_DUPLICATE_BLOCKED",
                allowed=False,
                action_executed=False,
                executor_calls=0,
                duplicate_action_blocked=True,
                retry_allowed_now=False,
                next_legal_action="REUSE_EXISTING_CLOSEOUT_RECEIPT",
                consumer_key=key,
            ),
            "consumer_ledger": ledger,
            "receipt": deepcopy(ledger[key]),
        }

    try:
        executor_receipt = execute_action(deepcopy(dict(action)))
    except Exception as exc:
        return {
            "result": _base_result(
                "CLOSEOUT_ACTION_FAILED",
                allowed=False,
                action_executed=True,
                executor_calls=1,
                duplicate_action_blocked=False,
                retry_allowed_now=False,
                next_legal_action="CLASSIFY_CLOSEOUT_ACTION_FAILURE",
                failure_class="EXECUTOR_EXCEPTION",
                error=str(exc),
                consumer_key=key,
            ),
            "consumer_ledger": ledger,
            "receipt": None,
        }

    if not isinstance(executor_receipt, Mapping):
        executor_receipt = {"status": "FAILURE", "failure_class": "MALFORMED_EXECUTOR_RECEIPT"}
    executor_copy = deepcopy(dict(executor_receipt))
    status = str(executor_copy.get("status") or "").strip().upper()
    if status not in _SUCCESS:
        return {
            "result": _base_result(
                "CLOSEOUT_ACTION_FAILED",
                allowed=False,
                action_executed=True,
                executor_calls=1,
                duplicate_action_blocked=False,
                retry_allowed_now=False,
                next_legal_action="CLASSIFY_CLOSEOUT_ACTION_FAILURE",
                failure_class=str(executor_copy.get("failure_class") or "EXECUTOR_REPORTED_FAILURE"),
                consumer_key=key,
            ),
            "consumer_ledger": ledger,
            "receipt": None,
        }

    if (
        executor_copy.get("action_type") not in {None, action_type}
        or executor_copy.get("target") not in {None, str(action.get("target"))}
    ):
        return {
            "result": _base_result(
                "CLOSEOUT_ACTION_FAILED",
                allowed=False,
                action_executed=True,
                executor_calls=1,
                duplicate_action_blocked=False,
                retry_allowed_now=False,
                next_legal_action="CLASSIFY_CLOSEOUT_ACTION_FAILURE",
                failure_class="EXECUTOR_RECEIPT_SCOPE_MISMATCH",
                consumer_key=key,
            ),
            "consumer_ledger": ledger,
            "receipt": None,
        }

    receipt_body = {
        "consumer_key": key,
        "workstream_id": workstream,
        "continuation_packet_hash": packet_hash,
        "task_id": str(action.get("task_id")),
        "checkpoint_id": str(action.get("checkpoint_id")),
        "action_type": action_type,
        "target": str(action.get("target")),
        "execution_proof_hash": proof_hash,
        "action_fingerprint": action_fp,
        "executor_receipt": executor_copy,
        "telemetry_detection_only": True,
    }
    receipt = {**receipt_body, "receipt_digest": _digest(receipt_body)}
    ledger[key] = deepcopy(receipt)

    return {
        "result": _base_result(
            "CLOSEOUT_ACTION_CONSUMED",
            allowed=True,
            action_executed=True,
            executor_calls=1,
            duplicate_action_blocked=False,
            retry_allowed_now=False,
            next_legal_action="RECONCILE_CANONICAL_COMPLETION",
            consumer_key=key,
            receipt_digest=receipt["receipt_digest"],
        ),
        "consumer_ledger": ledger,
        "receipt": receipt,
    }
