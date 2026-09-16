from __future__ import annotations

import pytest

from devsystem.action_ledger_v2 import GENESIS_CHAIN_HASH, build_receipt, record_authorized_action
from devsystem.checkpoint_ledger_v2 import (
    CheckpointLedgerV2Failure,
    transition_checkpoint,
    validate_checkpoint_ledger,
)


def _base_ledger() -> dict:
    return {
        "version": 2,
        "task_id": "checkpoint-v2-test",
        "status": "ACTIVE",
        "current_checkpoint": "2",
        "total_checkpoints": 2,
        "completed_checkpoints": 1,
        "remaining_checkpoints": 1,
        "active_blocker": None,
        "action_log": {
            "head_chain_hash": GENESIS_CHAIN_HASH,
            "events": [],
            "consumed_receipts": [],
        },
        "transition_history": [],
        "override_events": [],
        "checkpoints": [
            {"id": "1", "state": "DONE", "evidence": {"proof": "green-1"}},
            {"id": "2", "state": "ACTIVE", "evidence": {}},
        ],
    }


def _add_event(ledger: dict, checkpoint_id: str, nonce: str, evidence=None) -> tuple[dict, str]:
    receipt = build_receipt({
        "policy_version": 2,
        "task_id": ledger["task_id"],
        "checkpoint_id": checkpoint_id,
        "action_fingerprint": (nonce[0] * 64) if nonce else "a" * 64,
        "root_cause_fingerprint": "b" * 64,
        "evidence_fingerprint": "c" * 64,
        "relevant_input_fingerprint": "d" * 64,
        "decision": "AUTHORIZED",
        "previous_chain_hash": ledger["action_log"]["head_chain_hash"],
        "event_nonce": nonce,
        "override_event_id": None,
    })
    updated = record_authorized_action(
        ledger,
        receipt,
        outcome="success",
        progress_class="checkpoint_closed",
        evidence=evidence or {"proof": nonce},
    )
    return updated, updated["action_log"]["events"][-1]["event_id"]


def test_active_ledger_requires_exactly_one_active_checkpoint():
    ledger = _base_ledger()
    ledger["checkpoints"][0]["state"] = "ACTIVE"
    with pytest.raises(CheckpointLedgerV2Failure, match="exactly one ACTIVE"):
        validate_checkpoint_ledger(ledger)


def test_done_checkpoint_cannot_reopen_without_contradictory_evidence():
    ledger, event_id = _add_event(_base_ledger(), "1", "reopen")
    with pytest.raises(CheckpointLedgerV2Failure, match="contradictory evidence"):
        transition_checkpoint(ledger, "1", "ACTIVE", authorized_event_id=event_id)


def test_transition_requires_existing_unused_authorized_action_event():
    with pytest.raises(CheckpointLedgerV2Failure, match="authorized action event"):
        transition_checkpoint(
            _base_ledger(),
            "2",
            "DONE",
            authorized_event_id="ACT-MISSING",
            evidence={"proof": "green"},
        )


def test_final_checkpoint_closure_sets_terminal_state():
    ledger, event_id = _add_event(_base_ledger(), "2", "close")
    updated = transition_checkpoint(
        ledger,
        "2",
        "DONE",
        authorized_event_id=event_id,
        evidence={"contract": "GREEN"},
    )
    result = validate_checkpoint_ledger(updated)
    assert result["task_status"] == "DONE"
    assert updated["status"] == "DONE"
    assert updated["current_checkpoint"] is None
    assert updated["remaining_checkpoints"] == 0


def test_authorized_event_cannot_transition_two_checkpoints():
    ledger, event_id = _add_event(_base_ledger(), "2", "close")
    closed = transition_checkpoint(
        ledger, "2", "DONE", authorized_event_id=event_id, evidence={"proof": "green"}
    )
    with pytest.raises(CheckpointLedgerV2Failure, match="already used"):
        transition_checkpoint(
            closed,
            "2",
            "DONE",
            authorized_event_id=event_id,
            evidence={"proof": "green"},
        )


def test_valid_contradictory_evidence_can_reopen_done_checkpoint():
    ledger, event_id = _add_event(_base_ledger(), "1", "contradiction")
    updated = transition_checkpoint(
        ledger,
        "1",
        "ACTIVE",
        authorized_event_id=event_id,
        contradictory_evidence={"new_failure": "closing proof invalidated"},
    )
    assert updated["current_checkpoint"] == "1"
    assert updated["checkpoints"][0]["state"] == "ACTIVE"
    assert updated["checkpoints"][1]["state"] == "PENDING"


def test_event_checkpoint_identity_must_match_transition_target():
    ledger, event_id = _add_event(_base_ledger(), "1", "wrong-target")
    with pytest.raises(CheckpointLedgerV2Failure, match="checkpoint mismatch"):
        transition_checkpoint(
            ledger,
            "2",
            "DONE",
            authorized_event_id=event_id,
            evidence={"proof": "green"},
        )
