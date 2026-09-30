from __future__ import annotations

from copy import deepcopy
import subprocess
import sys
from pathlib import Path

import pytest

from devsystem.action_ledger_v2 import build_receipt
from devsystem.forward_motion_v2 import fingerprint_action
from devsystem.mandatory_2a_receipt_v1 import (
    TwoAReceiptFailure,
    authorize_action_with_receipt,
    contract_self_test,
    new_consumption_ledger,
    require_single_use_authorization,
    validate_execution_receipt,
)
from devsystem.persistent_execution_brain_v1 import BrainStateInput, build_state


def _brain(*, waiting=False, observed_head="2" * 40):
    return build_state(BrainStateInput(
        program_id="test",
        program_title="2A Step 2 receipts",
        total_steps=2,
        current_step=1,
        step_title="Single-Use Receipt",
        execution_state="WAITING_ON_ASYNC" if waiting else "ACTIVE",
        repository="owner/repo",
        main_sha="1" * 40,
        work_branch="step2",
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


def _action(target="github:pr/1"):
    return {
        "task_id": "test",
        "checkpoint_id": "1",
        "action_type": "merge",
        "target": target,
        "inputs": {"head": "2" * 40},
    }


def _forward(action):
    return {
        "decision": "AUTHORIZED",
        "receipt": build_receipt({
            "policy_version": 2,
            "task_id": action["task_id"],
            "checkpoint_id": action["checkpoint_id"],
            "action_fingerprint": fingerprint_action(action),
            "root_cause_fingerprint": "r" * 64,
            "evidence_fingerprint": "e" * 64,
            "relevant_input_fingerprint": "i" * 64,
            "decision": "AUTHORIZED",
            "previous_chain_hash": "0" * 64,
            "event_nonce": "step2-test",
            "override_event_id": None,
        }),
    }


def test_allowed_non_async_action_gets_execution_receipt():
    brain = _brain()
    action = _action()
    result = authorize_action_with_receipt(
        brain, action, [], forward_decision=_forward(action)
    )
    assert result["allowed"] is True
    assert result["receipt_issued"] is True
    assert result["execution_receipt_hash"]
    assert validate_execution_receipt(
        result["execution_receipt"], brain, action
    )["status"] == "GREEN"


def test_allowed_async_observation_also_gets_execution_receipt():
    brain = _brain(waiting=True)
    action = {
        "task_id": "test",
        "checkpoint_id": "1",
        "action_type": "observe_async",
        "target": "github:run/9001",
        "authoritative_run_id": 9001,
        "authoritative_job_id": 7001,
        "observed_async_state": "IN_PROGRESS",
        "evidence": {"run_id": 9001, "job_id": 7001, "state": "IN_PROGRESS"},
    }
    result = authorize_action_with_receipt(brain, action, [])
    assert result["allowed"] is True
    assert result["receipt_issued"] is True
    assert validate_execution_receipt(
        result["execution_receipt"], brain, action
    )["status"] == "GREEN"


def test_denied_action_never_gets_execution_receipt():
    result = authorize_action_with_receipt(_brain(), _action(), [])
    assert result["allowed"] is False
    assert result["receipt_issued"] is False
    assert result["execution_receipt"] is None


def test_execution_receipt_is_exact_action_bound():
    brain = _brain()
    action = _action()
    result = authorize_action_with_receipt(
        brain, action, [], forward_decision=_forward(action)
    )
    with pytest.raises(TwoAReceiptFailure, match="exact action"):
        validate_execution_receipt(
            result["execution_receipt"], brain, _action("github:pr/2")
        )


def test_execution_receipt_is_exact_brain_state_bound():
    brain = _brain()
    action = _action()
    result = authorize_action_with_receipt(
        brain, action, [], forward_decision=_forward(action)
    )
    with pytest.raises(TwoAReceiptFailure, match="brain_state_id mismatch"):
        validate_execution_receipt(
            result["execution_receipt"],
            _brain(observed_head="3" * 40),
            action,
        )


def test_execution_receipt_is_tamper_evident():
    brain = _brain()
    action = _action()
    result = authorize_action_with_receipt(
        brain, action, [], forward_decision=_forward(action)
    )
    tampered = deepcopy(result["execution_receipt"])
    tampered["payload"]["target"] = "github:pr/evil"
    with pytest.raises(TwoAReceiptFailure, match="hash mismatch"):
        validate_execution_receipt(tampered, brain, action)


def test_execution_receipt_can_be_consumed_exactly_once():
    brain = _brain()
    action = _action()
    auth = authorize_action_with_receipt(
        brain, action, [], forward_decision=_forward(action)
    )
    ledger = new_consumption_ledger()
    used = require_single_use_authorization(auth, brain, action, ledger)
    assert len(used["consumed_receipts"]) == 1
    with pytest.raises(TwoAReceiptFailure, match="already consumed"):
        require_single_use_authorization(auth, brain, action, used)


def test_missing_receipt_blocks_execution_even_if_allowed_flag_is_forged():
    brain = _brain()
    action = _action()
    forged = {
        "allowed": True,
        "decision": "TWO_A_AUTHORIZED",
        "execution_receipt": None,
    }
    with pytest.raises(TwoAReceiptFailure, match="missing mandatory execution receipt"):
        require_single_use_authorization(
            forged, brain, action, new_consumption_ledger()
        )


def test_receipt_for_one_action_cannot_be_spent_on_another():
    brain = _brain()
    action = _action()
    auth = authorize_action_with_receipt(
        brain, action, [], forward_decision=_forward(action)
    )
    with pytest.raises(TwoAReceiptFailure):
        require_single_use_authorization(
            auth, brain, _action("github:pr/2"), new_consumption_ledger()
        )


def test_contract_self_test_is_green():
    result = contract_self_test()
    assert result["status"] == "GREEN"
    assert result["every_allowed_action_gets_receipt"] is True
    assert result["single_use_enforced"] is True
    assert result["exact_action_binding"] is True
    assert result["brain_state_binding"] is True
    assert result["tamper_evident"] is True
    assert result["denied_action_gets_no_receipt"] is True
    assert result["missing_receipt_fails_closed"] is True
    assert result["step1_gate_preserved"] is True
    assert result["product_runtime_mutation"] is False


def test_direct_script_execution_is_green():
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, str(root / "devsystem" / "mandatory_2a_receipt_v1.py")],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "MONSTER_2A_SINGLE_USE_AUTH_RECEIPT_V1_GREEN" in completed.stdout
