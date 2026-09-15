"""Deterministic forward-motion controller for Monster Mode.

This module prevents repeated proof, unchanged retry loops, approval churn, and
post-finish work invention. It is dependency-light and does not touch sports logic.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from devsystem.checkpoint_ledger_v1 import LedgerFailure, validate_ledger


ROOT = Path(__file__).resolve().parents[1]
POLICY_PATH = ROOT / "devsystem" / "forward_motion_policy_v1.json"


class ForwardMotionFailure(RuntimeError):
    """Raised when controller inputs are malformed."""


def load_policy(path: Path = POLICY_PATH) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if int(payload.get("version", 0)) != 1:
        raise ForwardMotionFailure("forward-motion policy version must be 1")
    if payload.get("mode") != "strict_auto_continue":
        raise ForwardMotionFailure("forward-motion policy mode drift")
    return payload


def _canonical_action(action: dict[str, Any]) -> dict[str, Any]:
    required = ("task_id", "checkpoint_id", "action_type", "target")
    missing = [key for key in required if not str(action.get(key) or "").strip()]
    if missing:
        raise ForwardMotionFailure("action missing required fields: " + ", ".join(missing))
    return {
        "task_id": str(action["task_id"]),
        "checkpoint_id": str(action["checkpoint_id"]),
        "action_type": str(action["action_type"]),
        "target": str(action["target"]),
        "inputs": action.get("inputs") or {},
        "evidence_class": str(action.get("evidence_class") or ""),
    }


def fingerprint_action(action: dict[str, Any]) -> str:
    canonical = json.dumps(
        _canonical_action(action),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _checkpoint(ledger: dict[str, Any], checkpoint_id: str) -> dict[str, Any]:
    for checkpoint in ledger.get("checkpoints") or []:
        if str(checkpoint.get("id")) == str(checkpoint_id):
            return checkpoint
    raise ForwardMotionFailure(f"unknown checkpoint: {checkpoint_id}")


def _same_fingerprint(history: list[dict[str, Any]], fingerprint: str) -> list[dict[str, Any]]:
    return [item for item in history if str(item.get("fingerprint") or "") == fingerprint]


def _result(
    decision: str,
    *,
    fingerprint: str,
    reason: str,
    retry_budget_remaining: int | None = None,
    user_action: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "decision": decision,
        "fingerprint": fingerprint,
        "reason": reason,
    }
    if retry_budget_remaining is not None:
        payload["retry_budget_remaining"] = retry_budget_remaining
    if user_action is not None:
        payload["user_action"] = user_action
    return payload


def decide(
    ledger: dict[str, Any],
    action: dict[str, Any],
    history: list[dict[str, Any]],
    policy: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return one deterministic next-action decision.

    The controller never mutates the ledger. State transitions remain the job of
    ``checkpoint_ledger_v1`` after an allowed action produces evidence.
    """
    try:
        ledger_state = validate_ledger(ledger)
    except LedgerFailure as exc:
        raise ForwardMotionFailure(f"invalid ledger: {exc}") from exc

    active_policy = policy or load_policy()
    fingerprint = fingerprint_action(action)

    if str(action.get("task_id")) != str(ledger.get("task_id")):
        raise ForwardMotionFailure("action task_id does not match ledger task_id")

    if ledger_state["task_status"] == "DONE":
        return _result(
            "TASK_COMPLETE",
            fingerprint=fingerprint,
            reason="declared finish line is already satisfied",
        )

    checkpoint = _checkpoint(ledger, str(action.get("checkpoint_id")))
    if action.get("action_type") == "reopen_checkpoint" and checkpoint.get("state") == "DONE":
        if not action.get("contradictory_evidence"):
            return _result(
                "REJECT_CLOSED_CHECKPOINT_REOPEN",
                fingerprint=fingerprint,
                reason="closed checkpoint cannot reopen without contradictory evidence",
            )
        if not (action.get("inputs") or {}):
            return _result(
                "REJECT_CLOSED_CHECKPOINT_REOPEN",
                fingerprint=fingerprint,
                reason="contradictory reopen requires new evidence inputs",
            )
        return _result(
            "ALLOW_NEW_HYPOTHESIS",
            fingerprint=fingerprint,
            reason="new contradictory evidence invalidates prior closing evidence",
        )

    if str(action.get("scope_relation") or "in_scope") == "unrelated":
        return _result(
            "DEFER_SIDE_QUEST",
            fingerprint=fingerprint,
            reason="finding is unrelated to the approved finish line",
        )

    if bool(action.get("requires_user")) and not bool(
        action.get("resolvable_with_available_tools", True)
    ):
        return _result(
            "STOP_EXTERNAL_BLOCKER",
            fingerprint=fingerprint,
            reason="active blocker cannot be resolved with available tools",
            user_action=str(action.get("user_action") or "").strip() or None,
        )

    matches = _same_fingerprint(history, fingerprint)
    is_retry = bool(action.get("retry"))
    failure_class = str(action.get("failure_class") or "")
    budgets = active_policy.get("retry_budgets") or {}

    if is_retry:
        if failure_class == "deterministic-regression":
            return _result(
                "REJECT_DUPLICATE_PROOF",
                fingerprint=fingerprint,
                reason="deterministic failures receive zero unchanged retries",
                retry_budget_remaining=0,
            )

        if failure_class == "transient-capable":
            allowed = int(budgets.get("transient-capable", 1))
            used = sum(bool(item.get("controlled_retry")) for item in matches)
            remaining = max(allowed - used, 0)
            if matches and remaining > 0:
                return _result(
                    "ALLOW_CONTROLLED_RETRY",
                    fingerprint=fingerprint,
                    reason="one inspected transient-capable retry is allowed",
                    retry_budget_remaining=remaining - 1,
                )
            return _result(
                "REJECT_DUPLICATE_PROOF",
                fingerprint=fingerprint,
                reason="controlled transient retry budget exhausted",
                retry_budget_remaining=0,
            )

        if failure_class in {"unknown", ""} and bool(action.get("new_hypothesis")):
            return _result(
                "ALLOW_NEW_HYPOTHESIS",
                fingerprint=fingerprint,
                reason="unknown failure is testing a new discriminating hypothesis",
            )

    if matches:
        return _result(
            "REJECT_DUPLICATE_PROOF",
            fingerprint=fingerprint,
            reason="same proof fingerprint already produced evidence and inputs did not change",
        )

    if bool(action.get("new_hypothesis")):
        return _result(
            "ALLOW_NEW_HYPOTHESIS",
            fingerprint=fingerprint,
            reason="action tests a new discriminating root-cause hypothesis",
        )

    return _result(
        "ALLOW_ADVANCE",
        fingerprint=fingerprint,
        reason="action advances the active checkpoint with a new proof fingerprint",
    )
