from __future__ import annotations

from copy import deepcopy
import subprocess
import sys
from pathlib import Path

import pytest

from devsystem.terminal_proof_receipt_v1 import (
    TerminalProofReceiptFailure,
    build_receipt,
    contract_self_test,
    validate_receipt,
    verify_terminal_receipt,
)


def _fixture():
    return {
        "repository": "owner/repo",
        "checkpoint_id": "MONSTER_V4_STEP5",
        "head_sha": "1" * 40,
        "authoritative_run": 5005,
        "authoritative_workflow": "DevSystem targeted CI",
        "test_count": 125,
        "required_lanes": {
            "browser-qa": "skipped",
            "devsystem-final-gate": "success",
            "permanent-contract": "success",
        },
        "scope_diff": [
            "devsystem/terminal_proof_receipt_v1.py",
            "tests/test_devsystem_terminal_proof_receipt_v1.py",
        ],
        "freeze_tokens": [
            "MONSTER_V4_STEP5_GREEN",
            "MONSTER_V4_STEP5_FROZEN",
        ],
    }


def test_terminal_receipt_contains_every_required_proof_dimension():
    receipt = build_receipt(**_fixture())
    validated = validate_receipt(receipt)
    assert validated["status"] == "GREEN"
    assert validated["head_sha"] == "1" * 40
    assert validated["authoritative_run"] == 5005
    assert validated["test_count"] == 125
    assert validated["required_lane_count"] == 3
    assert validated["scope_file_count"] == 2
    assert validated["freeze_token_count"] == 2


def test_exact_expected_proof_verifies():
    data = _fixture()
    receipt = build_receipt(**data)
    result = verify_terminal_receipt(
        receipt,
        expected_head_sha=data["head_sha"],
        expected_authoritative_run=data["authoritative_run"],
        expected_required_lanes=data["required_lanes"],
        expected_scope_diff=data["scope_diff"],
        expected_freeze_tokens=data["freeze_tokens"],
    )
    assert result["decision"] == "TERMINAL_PROOF_RECEIPT_VERIFIED"
    assert result["exact_sha_bound"] is True
    assert result["authoritative_run_bound"] is True
    assert result["required_lanes_bound"] is True
    assert result["scope_diff_bound"] is True
    assert result["freeze_tokens_bound"] is True


def test_hash_tamper_is_rejected():
    receipt = build_receipt(**_fixture())
    receipt = deepcopy(receipt)
    receipt["test_count"] += 1
    with pytest.raises(TerminalProofReceiptFailure, match="hash mismatch"):
        validate_receipt(receipt)


def test_valid_but_stale_sha_is_rejected_against_expected_proof():
    data = _fixture()
    stale = dict(data)
    stale["head_sha"] = "2" * 40
    receipt = build_receipt(**stale)
    with pytest.raises(TerminalProofReceiptFailure, match="head_sha"):
        verify_terminal_receipt(
            receipt,
            expected_head_sha=data["head_sha"],
            expected_authoritative_run=data["authoritative_run"],
            expected_required_lanes=data["required_lanes"],
            expected_scope_diff=data["scope_diff"],
            expected_freeze_tokens=data["freeze_tokens"],
        )


def test_failure_lane_cannot_be_minted_as_terminal_green():
    data = _fixture()
    data["required_lanes"] = {"devsystem-final-gate": "failure"}
    with pytest.raises(TerminalProofReceiptFailure, match="success or skipped"):
        build_receipt(**data)


def test_contract_self_test_is_green_and_runtime_safe():
    result = contract_self_test()
    assert result["status"] == "GREEN"
    assert result["single_terminal_object"] is True
    assert result["exact_sha_bound"] is True
    assert result["authoritative_run_bound"] is True
    assert result["test_count_bound"] is True
    assert result["required_lanes_bound"] is True
    assert result["scope_diff_bound"] is True
    assert result["freeze_tokens_bound"] is True
    assert result["receipt_hash_tamper_rejected"] is True
    assert result["stale_sha_rejected"] is True
    assert result["stale_run_rejected"] is True
    assert result["failed_lane_rejected"] is True
    assert result["scope_drift_rejected"] is True
    assert result["freeze_token_drift_rejected"] is True
    assert result["product_runtime_mutation"] is False


def test_direct_script_execution_is_green():
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, str(root / "devsystem" / "terminal_proof_receipt_v1.py")],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "MONSTER_V4_TERMINAL_PROOF_RECEIPT_V1_GREEN" in completed.stdout
