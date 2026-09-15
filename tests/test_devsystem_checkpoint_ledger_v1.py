from __future__ import annotations

import copy

import pytest

from devsystem.checkpoint_ledger_v1 import LedgerFailure, transition_checkpoint, validate_ledger


def _ledger() -> dict:
    return {
        "task_id": "monster-anti-loop-v1",
        "title": "Monster Anti-Loop V1",
        "mode": "strict_auto_continue",
        "status": "ACTIVE",
        "current_checkpoint": "3",
        "total_checkpoints": 8,
        "completed_checkpoints": 2,
        "remaining_checkpoints": 6,
        "exit_conditions": ["all checkpoints done", "final gate green"],
        "active_blocker": None,
        "deferred_findings": [],
        "evidence_fingerprints": [],
        "action_history": [],
        "checkpoints": [
            {"id": "1", "state": "DONE", "entry_condition": "approved", "exit_condition": "rules locked", "evidence": {"approval": True}},
            {"id": "2", "state": "DONE", "entry_condition": "rules locked", "exit_condition": "laws defined", "evidence": {"spec": "approved"}},
            {"id": "3", "state": "ACTIVE", "entry_condition": "laws defined", "exit_condition": "ledger green", "evidence": {}},
            {"id": "4", "state": "PENDING", "entry_condition": "ledger green", "exit_condition": "controller green", "evidence": {}},
            {"id": "5", "state": "PENDING", "entry_condition": "controller green", "exit_condition": "budgets green", "evidence": {}},
            {"id": "6", "state": "PENDING", "entry_condition": "budgets green", "exit_condition": "CI wired", "evidence": {}},
            {"id": "7", "state": "PENDING", "entry_condition": "CI wired", "exit_condition": "A9 replay green", "evidence": {}},
            {"id": "8", "state": "PENDING", "entry_condition": "A9 replay green", "exit_condition": "merged", "evidence": {}},
        ],
    }


def test_valid_sequential_ledger_reports_counts():
    result = validate_ledger(_ledger())
    assert result["status"] == "GREEN"
    assert result["active_checkpoint"] == "3"
    assert result["completed_checkpoints"] == 2
    assert result["remaining_checkpoints"] == 6


def test_two_active_checkpoints_fail_closed():
    ledger = _ledger()
    ledger["checkpoints"][3]["state"] = "ACTIVE"
    with pytest.raises(LedgerFailure, match="exactly one ACTIVE checkpoint"):
        validate_ledger(ledger)


def test_done_checkpoint_cannot_reopen_without_contradictory_evidence():
    with pytest.raises(LedgerFailure, match="DONE checkpoint cannot be reopened"):
        transition_checkpoint(_ledger(), "2", "ACTIVE")


def test_done_checkpoint_can_reopen_only_with_contradictory_evidence():
    ledger = transition_checkpoint(
        _ledger(),
        "2",
        "ACTIVE",
        evidence={"contradiction": "previous closing evidence invalidated"},
        contradictory_evidence=True,
    )
    assert ledger["current_checkpoint"] == "2"
    assert next(cp for cp in ledger["checkpoints"] if cp["id"] == "2")["state"] == "ACTIVE"


def test_only_one_active_blocker_is_allowed():
    ledger = _ledger()
    ledger["active_blocker"] = [
        {"blocker_id": "b1", "checkpoint_id": "3"},
        {"blocker_id": "b2", "checkpoint_id": "3"},
    ]
    with pytest.raises(LedgerFailure, match="one active blocker"):
        validate_ledger(ledger)


def test_terminal_task_closes_when_all_checkpoints_done():
    ledger = _ledger()
    for checkpoint in ledger["checkpoints"]:
        checkpoint["state"] = "DONE"
        checkpoint["evidence"] = {"verified": True}
    ledger["status"] = "DONE"
    ledger["current_checkpoint"] = None
    ledger["completed_checkpoints"] = 8
    ledger["remaining_checkpoints"] = 0

    result = validate_ledger(copy.deepcopy(ledger))
    assert result["status"] == "GREEN"
    assert result["task_status"] == "DONE"
    assert result["remaining_checkpoints"] == 0
