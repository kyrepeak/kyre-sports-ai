from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from devsystem.mandatory_2b_reliability_gate_v1 import (
    authorize_implementation,
    contract_self_test,
)


def _preflight():
    return {
        "finished_state": "Page works in production with verified data and no accidental blanks.",
        "current_state_inspected": True,
        "root_cause_proven": True,
        "authoritative_path": {
            "repository": "owner/repo",
            "branch": "work-branch",
            "target": "sports-page",
            "proof_path": "production",
        },
        "acceptance_criteria": [
            {
                "id": "ac1",
                "requirement": "Production page returns verified data",
                "source": "Kyre Sports API",
                "verification": "production request",
                "expected_result": "verified data",
            }
        ],
        "dependency_checks": [
            {
                "name": "Kyre Sports API",
                "reachable": True,
                "auth_ok": True,
                "response_shape_ok": True,
                "required_fields_ok": True,
                "freshness_ok": True,
            }
        ],
    }


def _action(preflight=None, history=None):
    action = {
        "task_id": "task-1",
        "checkpoint_id": "step-1",
        "action_type": "patch",
        "target": "github:mutation",
    }
    if preflight is not None:
        action["reliability_preflight"] = preflight
    if history is not None:
        action["implementation_attempt_history"] = history
    return action


def test_missing_preflight_fails_closed():
    result = authorize_implementation(_action())
    assert result["allowed"] is False
    assert result["decision"] == "TWO_B_PREFLIGHT_REQUIRED"


def test_valid_preflight_authorizes_attempt_one():
    result = authorize_implementation(_action(_preflight(), []))
    assert result["allowed"] is True
    assert result["decision"] == "TWO_B_ATTEMPT_1_AUTHORIZED"
    assert result["implementation_attempt"] == 1
    assert result["reliability_receipt_hash"]


def test_failed_dependency_blocks_before_implementation():
    preflight = _preflight()
    preflight["dependency_checks"][0]["reachable"] = False
    result = authorize_implementation(_action(preflight, []))
    assert result["allowed"] is False
    assert result["decision"] == "TWO_B_DEPENDENCY_PREFLIGHT_BLOCKED"


def test_attempt_two_requires_classification_and_new_evidence():
    prior = [{"attempt": 1, "outcome": "FAILED", "evidence_fingerprint": "old-evidence"}]
    result = authorize_implementation(_action(_preflight(), prior))
    assert result["allowed"] is False
    assert result["decision"] == "TWO_B_ATTEMPT_2_EVIDENCE_REQUIRED"


def test_attempt_two_authorized_only_with_new_evidence():
    preflight = _preflight()
    preflight.update({
        "failure_classification": "provider/data",
        "failed_assumption": "primary provider is reachable",
        "new_evidence": {"fingerprint": "new-evidence", "summary": "production returned 403"},
    })
    prior = [{"attempt": 1, "outcome": "FAILED", "evidence_fingerprint": "old-evidence"}]
    result = authorize_implementation(_action(preflight, prior))
    assert result["allowed"] is True
    assert result["decision"] == "TWO_B_ATTEMPT_2_AUTHORIZED"
    assert result["implementation_attempt"] == 2


def test_two_failed_attempts_handoff_to_anti_loop_root_cause_reset():
    preflight = _preflight()
    prior = [
        {"attempt": 1, "outcome": "FAILED", "evidence_fingerprint": "e1"},
        {"attempt": 2, "outcome": "FAILED", "evidence_fingerprint": "e2"},
    ]
    result = authorize_implementation(_action(preflight, prior))
    assert result["allowed"] is False
    assert result["decision"] == "TWO_B_ROOT_CAUSE_RESET_REQUIRED"
    assert result["anti_loop_handoff"] is True
    assert result["next_legal_action"] == "ROOT_CAUSE_RESET"


def test_contract_self_test_is_green():
    result = contract_self_test()
    assert result["status"] == "GREEN"
    assert result["first_pass_gate"] is True
    assert result["second_pass_requires_new_evidence"] is True
    assert result["third_patch_blocked"] is True
    assert result["anti_loop_root_cause_reset"] is True
    assert result["product_runtime_mutation"] is False


def test_direct_script_execution_is_green():
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, str(root / "devsystem" / "mandatory_2b_reliability_gate_v1.py")],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "MONSTER_2B_FIRST_SECOND_PASS_RELIABILITY_GATE_V1_GREEN" in completed.stdout
