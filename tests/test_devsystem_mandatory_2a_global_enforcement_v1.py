from __future__ import annotations

from copy import deepcopy
import subprocess
import sys
from pathlib import Path

import pytest

from devsystem.action_ledger_v2 import build_receipt
from devsystem.forward_motion_v2 import fingerprint_action
from devsystem.mandatory_2a_global_enforcement_v1 import (
    TwoAGlobalEnforcementFailure,
    contract_self_test,
    enforce_action,
    require_global_execution_authority,
)
from devsystem.mandatory_2a_receipt_v1 import new_consumption_ledger
from devsystem.mandatory_2a_replay_lock_v1 import new_replay_ledger
from devsystem.persistent_execution_brain_v1 import BrainStateInput, build_state


def _brain(*, waiting=False):
    return build_state(BrainStateInput(
        program_id="test",
        program_title="2A Step 4 global enforcement",
        total_steps=2,
        current_step=1,
        step_title="Global Enforcement + Tripwire",
        execution_state="WAITING_ON_ASYNC" if waiting else "ACTIVE",
        repository="owner/repo",
        main_sha="1" * 40,
        work_branch="step4",
        observed_head_sha="2" * 40,
        next_legal_action="Continue safely.",
        completed_steps=(),
        frozen_steps=(),
        remaining_steps=(2,),
        authoritative_run_id=9001 if waiting else None,
        authoritative_job_id=7001 if waiting else None,
        async_state="IN_PROGRESS" if waiting else "NONE",
        updated_at_utc="2026-09-30T03:44:00Z",
    ))


def _action(target="github:pr/1", action_type="merge"):
    return {
        "task_id": "test",
        "checkpoint_id": "1",
        "action_type": action_type,
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
            "event_nonce": "step4-test",
            "override_event_id": None,
        }),
    }


def _enforce(brain, action, replay=None, consumption=None, forward=True):
    return enforce_action(
        brain,
        action,
        [],
        replay or new_replay_ledger(),
        consumption or new_consumption_ledger(),
        forward_decision=_forward(action) if forward else None,
    )


def test_canonical_entrypoint_emits_only_valid_global_execution_authority():
    brain = _brain()
    action = _action()
    outcome = _enforce(brain, action)
    result = outcome["result"]
    assert result["decision"] == "GLOBAL_EXECUTION_AUTHORIZED"
    assert result["allowed"] is True
    assert result["execution_authorized"] is True
    assert result["tripwire_triggered"] is False
    validated = require_global_execution_authority(result, brain, action)
    assert validated["status"] == "GREEN"


def test_missing_step1_forward_authorization_trips_and_continues():
    outcome = _enforce(_brain(), _action(), forward=False)
    result = outcome["result"]
    assert result["decision"] == "TRIPWIRE_BLOCKED_CONTINUE"
    assert result["allowed"] is False
    assert result["tripwire_triggered"] is True
    assert result["requires_user_intervention"] is False
    assert result["next_legal_action"]


def test_replay_is_preserved_as_loop_skipped_continue():
    brain = _brain()
    action = _action()
    first = _enforce(brain, action)
    second = _enforce(
        brain,
        action,
        replay=first["replay_ledger"],
        consumption=first["consumption_ledger"],
    )
    result = second["result"]
    assert result["decision"] == "LOOP_SKIPPED_CONTINUE"
    assert result["allowed"] is False
    assert result["requires_user_intervention"] is False


@pytest.mark.parametrize("fake", [
    {"allowed": True, "decision": "TWO_A_AUTHORIZED"},
    {
        "allowed": True,
        "decision": "TWO_A_AUTHORIZED",
        "execution_receipt": {"fake": True},
    },
    {
        "allowed": True,
        "decision": "EXECUTION_SLOT_CLAIMED",
        "slot_claimed": True,
    },
])
def test_raw_lower_step_outputs_cannot_bypass_global_tripwire(fake):
    with pytest.raises(TwoAGlobalEnforcementFailure):
        require_global_execution_authority(fake, _brain(), _action())


def test_global_proof_is_tamper_evident():
    brain = _brain()
    action = _action()
    outcome = _enforce(brain, action)
    tampered = deepcopy(outcome["result"])
    tampered["execution_proof"]["payload"]["target"] = "github:pr/evil"
    with pytest.raises(TwoAGlobalEnforcementFailure, match="hash mismatch"):
        require_global_execution_authority(tampered, brain, action)


def test_global_proof_cannot_be_spent_on_different_action():
    brain = _brain()
    action = _action("github:pr/1")
    outcome = _enforce(brain, action)
    with pytest.raises(TwoAGlobalEnforcementFailure):
        require_global_execution_authority(
            outcome["result"],
            brain,
            _action("github:pr/2"),
        )


def test_live_async_mutation_is_globally_blocked():
    brain = _brain(waiting=True)
    action = _action("github:mutation", "patch")
    outcome = _enforce(brain, action, forward=False)
    result = outcome["result"]
    assert result["allowed"] is False
    assert result["execution_authorized"] is False
    assert result["requires_user_intervention"] is False


def test_unknown_action_type_fails_closed_at_global_entrypoint():
    brain = _brain()
    action = _action("github:future", "future_unregistered_mutation")
    outcome = _enforce(brain, action, forward=False)
    assert outcome["result"]["decision"] == "TRIPWIRE_BLOCKED_CONTINUE"
    assert outcome["result"]["allowed"] is False


def test_contract_self_test_is_green():
    result = contract_self_test()
    assert result["status"] == "GREEN"
    assert result["canonical_entrypoint_authorizes"] is True
    assert result["global_proof_valid"] is True
    assert result["missing_prerequisite_tripwire_blocks"] is True
    assert result["replay_stays_loop_skipped"] is True
    assert result["raw_step_outputs_cannot_bypass"] is True
    assert result["global_proof_tamper_blocked"] is True
    assert result["live_async_mutation_tripwire_blocks"] is True
    assert result["safe_continue_no_user"] is True
    assert result["step1_preserved"] is True
    assert result["step2_preserved"] is True
    assert result["step3_preserved"] is True
    assert result["product_runtime_mutation"] is False


def test_direct_script_execution_is_green():
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, str(root / "devsystem" / "mandatory_2a_global_enforcement_v1.py")],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "MONSTER_2A_GLOBAL_ENFORCEMENT_TRIPWIRE_V1_GREEN" in completed.stdout
