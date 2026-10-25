from __future__ import annotations

import pytest

from devsystem.mandatory_2c_autonomous_recovery_v1 import (
    Mandatory2CAutonomousRecoveryFailure,
    contract_self_test,
    decide_recovery,
    validate_recovery_receipt,
)


def _path():
    return {
        "repository": "kyrepeak/kyre-sports-ai",
        "branch": "monster-step2c-autonomous-recovery-v1",
        "target": "github:mutation",
        "proof_path": "runless-v2",
    }


def _failed_attempts():
    return [
        {
            "attempt": 1,
            "outcome": "FAILED",
            "evidence_fingerprint": "attempt-evidence-1",
        },
        {
            "attempt": 2,
            "outcome": "FAILED",
            "evidence_fingerprint": "attempt-evidence-2",
        },
    ]


def _context():
    return {
        "task_id": "step2c-test",
        "checkpoint_id": "2C",
        "authoritative_path": _path(),
        "failed_generation": 1,
        "failed_attempts": _failed_attempts(),
        "diagnostic_history": [],
        "evidence_candidates": [],
    }


def _action():
    return {
        "task_id": "step2c-test",
        "checkpoint_id": "2C",
        "action_type": "patch",
        "target": "github:mutation",
        "reliability_preflight": {
            "authoritative_path": _path(),
        },
    }


def test_duplicate_evidence_expands_diagnosis_without_user_intervention():
    context = _context()
    context["diagnostic_history"] = [
        {"evidence_fingerprint": "duplicate-evidence"},
    ]
    context["evidence_candidates"] = [
        {
            "fingerprint": "duplicate-evidence",
            "source": "same-log",
            "summary": "same failure already inspected",
            "material": True,
        }
    ]

    result = decide_recovery(context)

    assert result["decision"] == "TWO_C_EXPAND_DIAGNOSIS"
    assert result["allowed"] is False
    assert result["requires_user_intervention"] is False
    assert result["next_legal_action"] == "GATHER_EVIDENCE_NEW_SOURCE"
    assert result["recovery_receipt_hash"] is None


def test_new_material_evidence_is_selected_for_autonomous_diagnosis():
    context = _context()
    context["diagnostic_history"] = [
        {"evidence_fingerprint": "old-evidence"},
    ]
    context["evidence_candidates"] = [
        {
            "fingerprint": "old-evidence",
            "source": "old-log",
            "summary": "already inspected",
            "material": True,
        },
        {
            "fingerprint": "new-evidence",
            "source": "deployment-log",
            "summary": "new boundary failure",
            "material": True,
        },
    ]

    result = decide_recovery(context)

    assert result["decision"] == "TWO_C_GATHER_NEW_EVIDENCE"
    assert result["allowed"] is False
    assert result["requires_user_intervention"] is False
    assert result["selected_evidence"]["fingerprint"] == "new-evidence"
    assert result["next_legal_action"] == "GATHER_SELECTED_EVIDENCE"


def test_proven_new_root_cause_issues_deterministic_recovery_receipt():
    context = _context()
    context["root_cause"] = {
        "proven": True,
        "classification": "configuration/environment",
        "failed_assumption": "pytest is already installed in the runner",
        "evidence_fingerprint": "new-root-cause-evidence",
        "repair_summary": "install pytest before the targeted suite",
    }

    first = decide_recovery(context)
    second = decide_recovery(context)

    assert first["decision"] == "TWO_C_RECOVERY_AUTHORIZED"
    assert first["allowed"] is True
    assert first["requires_user_intervention"] is False
    assert first["recovery_generation"] == 2
    assert first["recovery_receipt_hash"]
    assert first["recovery_receipt_hash"] == second["recovery_receipt_hash"]
    assert first["recovery_receipt"] == second["recovery_receipt"]

    validated = validate_recovery_receipt(first["recovery_receipt"], _action())
    assert validated["valid"] is True
    assert validated["recovery_generation"] == 2


def test_root_cause_reusing_prior_evidence_cannot_unlock_recovery():
    context = _context()
    context["root_cause"] = {
        "proven": True,
        "classification": "verification/test",
        "failed_assumption": "old assumption",
        "evidence_fingerprint": "attempt-evidence-2",
        "repair_summary": "repeat old repair",
    }

    result = decide_recovery(context)

    assert result["decision"] == "TWO_C_EXPAND_DIAGNOSIS"
    assert result["allowed"] is False
    assert result["requires_user_intervention"] is False


def test_forged_or_mismatched_recovery_receipt_fails_closed():
    context = _context()
    context["root_cause"] = {
        "proven": True,
        "classification": "deployment",
        "failed_assumption": "production runs candidate head",
        "evidence_fingerprint": "deploy-evidence-new",
        "repair_summary": "bind deployment to exact head",
    }
    receipt = decide_recovery(context)["recovery_receipt"]

    forged = {**receipt, "receipt_hash": "0" * 64}
    with pytest.raises(Mandatory2CAutonomousRecoveryFailure):
        validate_recovery_receipt(forged, _action())

    wrong_action = _action()
    wrong_action["checkpoint_id"] = "different"
    with pytest.raises(Mandatory2CAutonomousRecoveryFailure):
        validate_recovery_receipt(receipt, wrong_action)


def test_only_verified_supported_human_blocker_requests_user_intervention():
    context = _context()
    context["human_blocker"] = {
        "verified": True,
        "type": "missing_credentials",
        "evidence": "provider requires an access token that is not configured",
    }

    result = decide_recovery(context)

    assert result["decision"] == "TWO_C_HUMAN_BLOCKER"
    assert result["allowed"] is False
    assert result["requires_user_intervention"] is True
    assert result["human_blocker_type"] == "missing_credentials"


def test_unverified_or_unsupported_blocker_does_not_stop_autonomous_diagnosis():
    context = _context()
    context["human_blocker"] = {
        "verified": False,
        "type": "missing_credentials",
        "evidence": "not proven",
    }

    result = decide_recovery(context)

    assert result["decision"] == "TWO_C_EXPAND_DIAGNOSIS"
    assert result["requires_user_intervention"] is False


def test_contract_self_test_is_green():
    result = contract_self_test()
    assert result["status"] == "GREEN"
    assert result["autonomous_diagnosis"] is True
    assert result["duplicate_evidence_blocked"] is True
    assert result["new_root_cause_recovery"] is True
    assert result["human_blocker_fail_closed"] is True
    assert result["network_calls"] is False
    assert result["product_runtime_mutation"] is False
