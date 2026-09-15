"""Deterministic checkpoint ledger for Monster forward-motion control.

This module is dependency-light and deliberately separate from sports/runtime logic.
It enforces stable sequential checkpoint state, closed-checkpoint immutability,
finite remaining counts, and the one-active-blocker contract.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any


CHECKPOINT_STATES = {"PENDING", "ACTIVE", "DONE", "BLOCKED", "DEFERRED"}
TASK_STATES = {"ACTIVE", "DONE", "BLOCKED", "FAILED"}


class LedgerFailure(RuntimeError):
    """Raised when a ledger violates the permanent Monster state contract."""


def _checkpoints(ledger: dict[str, Any]) -> list[dict[str, Any]]:
    checkpoints = ledger.get("checkpoints")
    if not isinstance(checkpoints, list) or not checkpoints:
        raise LedgerFailure("ledger requires a non-empty checkpoints list")
    return checkpoints


def _active_blocker(ledger: dict[str, Any]) -> dict[str, Any] | None:
    blocker = ledger.get("active_blocker")
    if blocker is None:
        return None
    if isinstance(blocker, list):
        if len(blocker) > 1:
            raise LedgerFailure("only one active blocker is allowed")
        if len(blocker) == 0:
            return None
        blocker = blocker[0]
    if not isinstance(blocker, dict):
        raise LedgerFailure("active_blocker must be one active blocker object or null")
    if not str(blocker.get("blocker_id") or "").strip():
        raise LedgerFailure("active blocker requires blocker_id")
    return blocker


def validate_ledger(ledger: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(ledger, dict):
        raise LedgerFailure("ledger must be an object")

    task_status = str(ledger.get("status") or "")
    if task_status not in TASK_STATES:
        raise LedgerFailure(f"invalid task status: {task_status!r}")

    checkpoints = _checkpoints(ledger)
    ids = [str(cp.get("id") or "") for cp in checkpoints]
    if any(not checkpoint_id for checkpoint_id in ids) or len(ids) != len(set(ids)):
        raise LedgerFailure("checkpoint IDs must be non-empty and unique")

    invalid_states = [
        str(cp.get("state") or "")
        for cp in checkpoints
        if str(cp.get("state") or "") not in CHECKPOINT_STATES
    ]
    if invalid_states:
        raise LedgerFailure(f"invalid checkpoint state: {invalid_states[0]!r}")

    total = len(checkpoints)
    declared_total = int(ledger.get("total_checkpoints", -1))
    if declared_total != total:
        raise LedgerFailure(
            f"total_checkpoints mismatch: declared={declared_total} actual={total}"
        )

    completed = sum(cp["state"] == "DONE" for cp in checkpoints)
    remaining = total - completed
    if int(ledger.get("completed_checkpoints", -1)) != completed:
        raise LedgerFailure("completed_checkpoints does not match DONE checkpoint count")
    if int(ledger.get("remaining_checkpoints", -1)) != remaining:
        raise LedgerFailure("remaining_checkpoints does not match unfinished checkpoint count")

    active = [cp for cp in checkpoints if cp["state"] == "ACTIVE"]
    blocker = _active_blocker(ledger)

    if task_status == "DONE":
        if completed != total or active:
            raise LedgerFailure("DONE task requires every checkpoint DONE and no ACTIVE checkpoint")
        if ledger.get("current_checkpoint") is not None:
            raise LedgerFailure("DONE task requires current_checkpoint=null")
        if blocker is not None:
            raise LedgerFailure("DONE task cannot retain an active blocker")
    elif task_status == "ACTIVE":
        if len(active) != 1:
            raise LedgerFailure("sequential ACTIVE task requires exactly one ACTIVE checkpoint")
        if str(ledger.get("current_checkpoint") or "") != str(active[0]["id"]):
            raise LedgerFailure("current_checkpoint must identify the ACTIVE checkpoint")
    else:
        if len(active) > 1:
            raise LedgerFailure("sequential task permits at most one ACTIVE checkpoint")

    if blocker is not None:
        blocker_checkpoint = str(blocker.get("checkpoint_id") or "")
        if blocker_checkpoint not in ids:
            raise LedgerFailure("active blocker references an unknown checkpoint")

    return {
        "status": "GREEN",
        "task_status": task_status,
        "active_checkpoint": str(active[0]["id"]) if active else None,
        "completed_checkpoints": completed,
        "remaining_checkpoints": remaining,
        "active_blocker": blocker,
    }


def _recount(ledger: dict[str, Any]) -> None:
    checkpoints = _checkpoints(ledger)
    completed = sum(cp["state"] == "DONE" for cp in checkpoints)
    ledger["total_checkpoints"] = len(checkpoints)
    ledger["completed_checkpoints"] = completed
    ledger["remaining_checkpoints"] = len(checkpoints) - completed


def transition_checkpoint(
    ledger: dict[str, Any],
    checkpoint_id: str,
    new_state: str,
    *,
    evidence: dict[str, Any] | None = None,
    contradictory_evidence: bool = False,
) -> dict[str, Any]:
    """Return a validated copy after one checkpoint transition.

    DONE checkpoints are immutable unless the caller explicitly supplies new
    contradictory evidence. Activating a checkpoint moves the previous ACTIVE
    checkpoint back to PENDING so a sequential task never has two active lanes.
    Completing the active checkpoint automatically activates the next PENDING
    checkpoint; completing the final checkpoint closes the task.
    """
    if new_state not in CHECKPOINT_STATES:
        raise LedgerFailure(f"invalid checkpoint state: {new_state!r}")

    updated = deepcopy(ledger)
    checkpoints = _checkpoints(updated)
    target = next(
        (cp for cp in checkpoints if str(cp.get("id")) == str(checkpoint_id)),
        None,
    )
    if target is None:
        raise LedgerFailure(f"unknown checkpoint: {checkpoint_id}")

    previous_state = str(target.get("state") or "")
    if previous_state == "DONE" and new_state != "DONE":
        if not contradictory_evidence or not evidence:
            raise LedgerFailure(
                "DONE checkpoint cannot be reopened without contradictory evidence"
            )

    if new_state == "ACTIVE":
        for checkpoint in checkpoints:
            if checkpoint is not target and checkpoint.get("state") == "ACTIVE":
                checkpoint["state"] = "PENDING"
        target["state"] = "ACTIVE"
        if evidence is not None:
            target["evidence"] = deepcopy(evidence)
        updated["current_checkpoint"] = str(target["id"])
        updated["status"] = "ACTIVE"
        updated["active_blocker"] = None

    elif new_state == "DONE":
        closing_evidence = evidence if evidence is not None else target.get("evidence")
        if not closing_evidence:
            raise LedgerFailure("DONE checkpoint requires closing evidence")
        target["state"] = "DONE"
        target["evidence"] = deepcopy(closing_evidence)
        updated["active_blocker"] = None

        pending = next((cp for cp in checkpoints if cp.get("state") == "PENDING"), None)
        if pending is None and all(cp.get("state") == "DONE" for cp in checkpoints):
            updated["status"] = "DONE"
            updated["current_checkpoint"] = None
        else:
            for checkpoint in checkpoints:
                if checkpoint.get("state") == "ACTIVE":
                    checkpoint["state"] = "PENDING"
            if pending is None:
                raise LedgerFailure("unfinished sequential task has no PENDING checkpoint")
            pending["state"] = "ACTIVE"
            updated["status"] = "ACTIVE"
            updated["current_checkpoint"] = str(pending["id"])

    elif new_state == "BLOCKED":
        target["state"] = "BLOCKED"
        if evidence is not None:
            target["evidence"] = deepcopy(evidence)
        for checkpoint in checkpoints:
            if checkpoint is not target and checkpoint.get("state") == "ACTIVE":
                checkpoint["state"] = "PENDING"
        updated["status"] = "BLOCKED"
        updated["current_checkpoint"] = str(target["id"])

    else:
        target["state"] = new_state
        if evidence is not None:
            target["evidence"] = deepcopy(evidence)

    _recount(updated)
    validate_ledger(updated)
    return updated
