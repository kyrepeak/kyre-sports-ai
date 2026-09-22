"""Receipt-event-aware monotonic checkpoint ledger for Monster Anti-Loop V2."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from devsystem.action_ledger_v2 import validate_action_ledger

CHECKPOINT_STATES = {"PENDING", "ACTIVE", "DONE", "BLOCKED", "DEFERRED"}
TASK_STATES = {"ACTIVE", "DONE", "BLOCKED", "FAILED"}


class CheckpointLedgerV2Failure(RuntimeError):
    pass


def _checkpoints(ledger: dict[str, Any]) -> list[dict[str, Any]]:
    checkpoints = ledger.get("checkpoints")
    if not isinstance(checkpoints, list) or not checkpoints:
        raise CheckpointLedgerV2Failure("ledger requires a non-empty checkpoints list")
    return checkpoints


def _active_blocker(ledger: dict[str, Any]) -> dict[str, Any] | None:
    blocker = ledger.get("active_blocker")
    if blocker is None:
        return None
    if isinstance(blocker, list):
        if len(blocker) > 1:
            raise CheckpointLedgerV2Failure("only one active blocker is allowed")
        if not blocker:
            return None
        blocker = blocker[0]
    if not isinstance(blocker, dict):
        raise CheckpointLedgerV2Failure("active_blocker must be an object or null")
    if not str(blocker.get("blocker_id") or "").strip():
        raise CheckpointLedgerV2Failure("active blocker requires blocker_id")
    return blocker


def _event_map(ledger: dict[str, Any]) -> dict[str, dict[str, Any]]:
    log = ledger.get("action_log") or {}
    events = log.get("events") or []
    mapping: dict[str, dict[str, Any]] = {}
    for event in events:
        event_id = str(event.get("event_id") or "")
        if not event_id:
            raise CheckpointLedgerV2Failure("action event requires event_id")
        if event_id in mapping:
            raise CheckpointLedgerV2Failure("action event IDs must be unique")
        mapping[event_id] = event
    return mapping


def validate_checkpoint_ledger(task_ledger: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(task_ledger, dict):
        raise CheckpointLedgerV2Failure("ledger must be an object")
    if int(task_ledger.get("version", 0)) != 2:
        raise CheckpointLedgerV2Failure("checkpoint ledger version must be 2")

    validate_action_ledger(task_ledger)
    checkpoints = _checkpoints(task_ledger)
    ids = [str(cp.get("id") or "") for cp in checkpoints]
    if any(not value for value in ids) or len(ids) != len(set(ids)):
        raise CheckpointLedgerV2Failure("checkpoint IDs must be non-empty and unique")
    for cp in checkpoints:
        if cp.get("state") not in CHECKPOINT_STATES:
            raise CheckpointLedgerV2Failure("invalid checkpoint state")

    status = str(task_ledger.get("status") or "")
    if status not in TASK_STATES:
        raise CheckpointLedgerV2Failure("invalid task status")
    completed = sum(cp.get("state") == "DONE" for cp in checkpoints)
    total = len(checkpoints)
    remaining = total - completed
    active = [cp for cp in checkpoints if cp.get("state") == "ACTIVE"]
    blocker = _active_blocker(task_ledger)
    if status == "ACTIVE" and len(active) != 1:
        raise CheckpointLedgerV2Failure("ACTIVE task requires exactly one ACTIVE checkpoint")

    if int(task_ledger.get("total_checkpoints", -1)) != total:
        raise CheckpointLedgerV2Failure("total_checkpoints mismatch")
    if int(task_ledger.get("completed_checkpoints", -1)) != completed:
        raise CheckpointLedgerV2Failure("completed_checkpoints mismatch")
    if int(task_ledger.get("remaining_checkpoints", -1)) != remaining:
        raise CheckpointLedgerV2Failure("remaining_checkpoints mismatch")

    if status == "ACTIVE":
        if str(task_ledger.get("current_checkpoint") or "") != str(active[0]["id"]):
            raise CheckpointLedgerV2Failure("current_checkpoint must identify the ACTIVE checkpoint")
    elif status == "DONE":
        if completed != total or active:
            raise CheckpointLedgerV2Failure("DONE task requires every checkpoint DONE and no ACTIVE checkpoint")
        if task_ledger.get("current_checkpoint") is not None:
            raise CheckpointLedgerV2Failure("DONE task requires current_checkpoint=null")
        if blocker is not None:
            raise CheckpointLedgerV2Failure("DONE task cannot retain active blocker")
        if remaining != 0:
            raise CheckpointLedgerV2Failure("DONE task requires zero remaining checkpoints")
    elif len(active) > 1:
        raise CheckpointLedgerV2Failure("task permits at most one ACTIVE checkpoint")

    if blocker is not None and str(blocker.get("checkpoint_id") or "") not in ids:
        raise CheckpointLedgerV2Failure("active blocker references unknown checkpoint")

    events = _event_map(task_ledger)
    transitions = task_ledger.get("transition_history")
    if not isinstance(transitions, list):
        raise CheckpointLedgerV2Failure("transition_history must be a list")
    used: set[str] = set()
    for transition in transitions:
        if not isinstance(transition, dict):
            raise CheckpointLedgerV2Failure("transition record must be an object")
        event_id = str(transition.get("authorized_event_id") or "")
        if event_id not in events:
            raise CheckpointLedgerV2Failure("transition references missing authorized action event")
        if event_id in used:
            raise CheckpointLedgerV2Failure("authorized action event already used by a transition")
        used.add(event_id)

    return {
        "status": "GREEN",
        "task_status": status,
        "active_checkpoint": str(active[0]["id"]) if active else None,
        "completed_checkpoints": completed,
        "remaining_checkpoints": remaining,
        "active_blocker": blocker,
        "transition_count": len(transitions),
    }


def _recount(ledger: dict[str, Any]) -> None:
    checkpoints = _checkpoints(ledger)
    completed = sum(cp.get("state") == "DONE" for cp in checkpoints)
    ledger["total_checkpoints"] = len(checkpoints)
    ledger["completed_checkpoints"] = completed
    ledger["remaining_checkpoints"] = len(checkpoints) - completed


def transition_checkpoint(
    task_ledger: dict[str, Any],
    checkpoint_id: str,
    new_state: str,
    *,
    authorized_event_id: str,
    evidence: dict[str, Any] | None = None,
    contradictory_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if new_state not in CHECKPOINT_STATES:
        raise CheckpointLedgerV2Failure("invalid checkpoint state")
    updated = deepcopy(task_ledger)
    checkpoints = _checkpoints(updated)
    target_index = next(
        (index for index, cp in enumerate(checkpoints) if str(cp.get("id")) == str(checkpoint_id)),
        None,
    )
    if target_index is None:
        raise CheckpointLedgerV2Failure(f"unknown checkpoint: {checkpoint_id}")
    target = checkpoints[target_index]

    events = _event_map(updated)
    event = events.get(str(authorized_event_id))
    if event is None:
        raise CheckpointLedgerV2Failure("authorized action event does not exist")
    transitions = updated.get("transition_history")
    if not isinstance(transitions, list):
        raise CheckpointLedgerV2Failure("transition_history must be a list")
    if any(str(item.get("authorized_event_id") or "") == str(authorized_event_id) for item in transitions):
        raise CheckpointLedgerV2Failure("authorized action event already used")

    receipt_payload = ((event.get("receipt") or {}).get("payload") or {})
    if str(receipt_payload.get("task_id") or "") != str(updated.get("task_id") or ""):
        raise CheckpointLedgerV2Failure("authorized action event task mismatch")
    if str(receipt_payload.get("checkpoint_id") or "") != str(checkpoint_id):
        raise CheckpointLedgerV2Failure("authorized action event checkpoint mismatch")

    previous_state = str(target.get("state") or "")
    if previous_state == "DONE" and new_state != "DONE":
        if not isinstance(contradictory_evidence, dict) or not contradictory_evidence:
            raise CheckpointLedgerV2Failure("DONE checkpoint reopen requires contradictory evidence")

    transition_record: dict[str, Any] = {
        "checkpoint_id": str(checkpoint_id),
        "from_state": previous_state,
        "to_state": new_state,
        "authorized_event_id": str(authorized_event_id),
        "evidence": deepcopy(evidence) if evidence is not None else None,
        "contradictory_evidence": deepcopy(contradictory_evidence) if contradictory_evidence is not None else None,
    }

    if new_state == "ACTIVE":
        for index, cp in enumerate(checkpoints):
            if index != target_index and cp.get("state") == "ACTIVE":
                cp["state"] = "PENDING"
        if previous_state == "DONE":
            for cp in checkpoints[target_index + 1 :]:
                if cp.get("state") == "ACTIVE":
                    cp["state"] = "PENDING"
        target["state"] = "ACTIVE"
        if contradictory_evidence:
            target["contradictory_evidence"] = deepcopy(contradictory_evidence)
        if evidence is not None:
            target["evidence"] = deepcopy(evidence)
        updated["status"] = "ACTIVE"
        updated["current_checkpoint"] = str(target["id"])
        updated["active_blocker"] = None

    elif new_state == "DONE":
        closing = evidence if evidence is not None else target.get("evidence")
        if not isinstance(closing, dict) or not closing:
            raise CheckpointLedgerV2Failure("DONE checkpoint requires closing evidence")
        target["state"] = "DONE"
        target["evidence"] = deepcopy(closing)
        updated["active_blocker"] = None
        next_pending = next(
            (cp for cp in checkpoints[target_index + 1 :] if cp.get("state") == "PENDING"),
            None,
        )
        if all(cp.get("state") == "DONE" for cp in checkpoints):
            updated["status"] = "DONE"
            updated["current_checkpoint"] = None
        elif next_pending is not None:
            for cp in checkpoints:
                if cp is not next_pending and cp.get("state") == "ACTIVE":
                    cp["state"] = "PENDING"
            next_pending["state"] = "ACTIVE"
            updated["status"] = "ACTIVE"
            updated["current_checkpoint"] = str(next_pending["id"])
        else:
            raise CheckpointLedgerV2Failure("unfinished sequential task has no later PENDING checkpoint")

    elif new_state == "BLOCKED":
        target["state"] = "BLOCKED"
        if evidence is not None:
            target["evidence"] = deepcopy(evidence)
        for cp in checkpoints:
            if cp is not target and cp.get("state") == "ACTIVE":
                cp["state"] = "PENDING"
        updated["status"] = "BLOCKED"
        updated["current_checkpoint"] = str(target["id"])

    else:
        target["state"] = new_state
        if evidence is not None:
            target["evidence"] = deepcopy(evidence)

    transitions.append(transition_record)
    _recount(updated)
    validate_checkpoint_ledger(updated)
    return updated
