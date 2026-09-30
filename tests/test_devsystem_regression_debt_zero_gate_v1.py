from __future__ import annotations

from copy import deepcopy
import subprocess
import sys
from pathlib import Path

import pytest

from devsystem.regression_debt_zero_gate_v1 import (
    RegressionDebtFailure,
    build_debt,
    contract_self_test,
    evaluate_freeze,
    validate_debt,
)


def _guard():
    return {
        "kind": "TEST",
        "path": "tests/test_regression_fixture.py",
        "permanent": True,
    }


def test_real_failure_without_regression_guard_blocks_freeze():
    debt = build_debt(
        failure_id="failure-1",
        owner="PRODUCT",
        root_cause="field parser dropped alias",
        repair_sha="1" * 40,
    )
    assert debt["state"] == "OPEN"
    with pytest.raises(RegressionDebtFailure, match="REGRESSION_DEBT_BLOCKS_FREEZE"):
        evaluate_freeze([debt])


def test_permanent_test_clears_regression_debt():
    debt = build_debt(
        failure_id="failure-1",
        owner="PRODUCT",
        root_cause="field parser dropped alias",
        repair_sha="1" * 40,
        regression_guards=[_guard()],
    )
    result = evaluate_freeze([debt])
    assert debt["state"] == "CLEARED"
    assert result["decision"] == "REGRESSION_DEBT_ZERO"
    assert result["freeze_allowed"] is True
    assert result["open_debt_count"] == 0


def test_permanent_contract_can_clear_debt():
    debt = build_debt(
        failure_id="failure-ci",
        owner="CI",
        root_cause="required workflow lane omitted",
        repair_sha="2" * 40,
        regression_guards=[
            {
                "kind": "CONTRACT",
                "path": "devsystem/permanent_gate_v1.py",
                "permanent": True,
            }
        ],
    )
    assert evaluate_freeze([debt])["freeze_allowed"] is True


def test_stale_and_external_failures_do_not_create_repair_debt():
    stale = build_debt(
        failure_id="stale-1",
        owner="STALE",
        root_cause="unused",
        repair_sha="3" * 40,
    )
    external = build_debt(
        failure_id="external-1",
        owner="EXTERNAL",
        root_cause="unused",
        repair_sha="3" * 40,
    )
    result = evaluate_freeze([stale, external])
    assert stale["state"] == "EXEMPT"
    assert external["state"] == "EXEMPT"
    assert result["exempt_count"] == 2


def test_nonpermanent_or_fake_test_guard_is_rejected():
    with pytest.raises(RegressionDebtFailure):
        build_debt(
            failure_id="bad-1",
            owner="VERIFIER",
            root_cause="selector race",
            repair_sha="4" * 40,
            regression_guards=[
                {"kind": "TEST", "path": "docs/not-a-test.md", "permanent": True}
            ],
        )
    with pytest.raises(RegressionDebtFailure):
        build_debt(
            failure_id="bad-2",
            owner="DEPLOYMENT",
            root_cause="deploy drift",
            repair_sha="4" * 40,
            regression_guards=[
                {"kind": "CONTRACT", "path": "devsystem/deploy.py", "permanent": False}
            ],
        )


def test_debt_hash_is_tamper_evident():
    debt = build_debt(
        failure_id="failure-1",
        owner="PRODUCT",
        root_cause="field parser dropped alias",
        repair_sha="1" * 40,
        regression_guards=[_guard()],
    )
    damaged = deepcopy(debt)
    damaged["root_cause"] = "different root cause"
    with pytest.raises(RegressionDebtFailure, match="hash mismatch"):
        validate_debt(damaged)


def test_one_open_debt_blocks_otherwise_cleared_batch():
    cleared = build_debt(
        failure_id="cleared-1",
        owner="PRODUCT",
        root_cause="fixed",
        repair_sha="5" * 40,
        regression_guards=[_guard()],
    )
    open_debt = build_debt(
        failure_id="open-1",
        owner="CI",
        root_cause="still unguarded",
        repair_sha="6" * 40,
    )
    with pytest.raises(RegressionDebtFailure, match="open-1"):
        evaluate_freeze([cleared, open_debt])


def test_contract_self_test_is_green_and_runtime_safe():
    result = contract_self_test()
    assert result["status"] == "GREEN"
    assert result["real_failure_creates_debt"] is True
    assert result["open_debt_blocks_freeze"] is True
    assert result["permanent_test_clears_debt"] is True
    assert result["permanent_contract_clears_debt"] is True
    assert result["stale_failure_exempt"] is True
    assert result["external_failure_exempt"] is True
    assert result["invalid_test_guard_rejected"] is True
    assert result["nonpermanent_guard_rejected"] is True
    assert result["tamper_rejected"] is True
    assert result["mixed_open_debt_blocks"] is True
    assert result["zero_debt_green"] is True
    assert result["product_runtime_mutation"] is False


def test_direct_script_execution_is_green():
    root = Path(__file__).resolve().parents[1]
    completed = subprocess.run(
        [sys.executable, str(root / "devsystem" / "regression_debt_zero_gate_v1.py")],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "MONSTER_V4_REGRESSION_DEBT_ZERO_GATE_GREEN" in completed.stdout
