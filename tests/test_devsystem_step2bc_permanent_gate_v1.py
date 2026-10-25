from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: str):
    target = ROOT / path
    spec = importlib.util.spec_from_file_location(name, target)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_step2b_and_step2c_are_permanent_devsystem_requirements():
    gate = _load(
        "mandatory_2bc_permanent_enforcement_v1",
        "devsystem/mandatory_2bc_permanent_enforcement_v1.py",
    )
    result = gate.validate()

    assert result["status"] == "GREEN"
    assert result["base_permanent_contract_green"] is True
    assert result["step2a_permanent_chain_preserved"] is True
    assert result["automatic_loop_kill_permanent"] is True
    assert result["mandatory_2b_reliability_gate_v1_permanent"] is True
    assert result["mandatory_2c_autonomous_recovery_v1_permanent"] is True
    assert result["step2b_step2c_workflows_permanent"] is True
    assert result["no_blind_attempt_three"] is True
    assert result["autonomous_diagnosis_after_two_failures"] is True
    assert result["human_intervention_only_for_verified_blocker"] is True
    assert result["network_calls"] is False
    assert result["auto_mutate"] is False
    assert result["product_runtime_mutation"] is False

    required = set(gate.REQUIRED_CONTROL_FILES)
    for path in (
        "devsystem/automatic_loop_kill_v1.py",
        "devsystem/mandatory_2a_action_gate_v1.py",
        "devsystem/mandatory_2b_reliability_gate_v1.py",
        "tests/test_devsystem_mandatory_2b_reliability_gate_v1.py",
        ".github/workflows/monster-step2b-reliability-gate-v1.yml",
        "devsystem/mandatory_2c_autonomous_recovery_v1.py",
        "tests/test_devsystem_mandatory_2c_autonomous_recovery_v1.py",
        "tests/test_devsystem_step2c_step2b_step2a_integration_v1.py",
        ".github/workflows/monster-step2c-autonomous-recovery-v1.yml",
        "tests/test_devsystem_step2bc_permanent_gate_v1.py",
    ):
        assert path in required


def test_step2b_and_step2c_permanent_markers_cannot_drift():
    gate = _load(
        "mandatory_2bc_permanent_enforcement_markers_v1",
        "devsystem/mandatory_2bc_permanent_enforcement_v1.py",
    )
    result = gate.contract_self_test()
    assert result["status"] == "GREEN"

    step2b = (ROOT / "devsystem/mandatory_2b_reliability_gate_v1.py").read_text(encoding="utf-8")
    step2c = (ROOT / "devsystem/mandatory_2c_autonomous_recovery_v1.py").read_text(encoding="utf-8")
    workflow2b = (ROOT / ".github/workflows/monster-step2b-reliability-gate-v1.yml").read_text(encoding="utf-8")
    workflow2c = (ROOT / ".github/workflows/monster-step2c-autonomous-recovery-v1.yml").read_text(encoding="utf-8")

    for marker in (
        "MONSTER_2B_FIRST_SECOND_PASS_RELIABILITY_GATE_V1",
        "TWO_B_TWO_C_RECOVERY_REQUIRED",
        "TWO_B_RECOVERY_ATTEMPT_AUTHORIZED",
        "recovery_receipt_hash",
    ):
        assert marker in step2b

    for marker in (
        "MONSTER_2C_AUTONOMOUS_RECOVERY_GREEN_CONVERGENCE_V1",
        "TWO_C_EXPAND_DIAGNOSIS",
        "TWO_C_RECOVERY_AUTHORIZED",
        "TWO_C_HUMAN_BLOCKER",
    ):
        assert marker in step2c

    assert "python devsystem/mandatory_2b_reliability_gate_v1.py" in workflow2b
    assert "tests/test_devsystem_mandatory_2b_reliability_gate_v1.py" in workflow2b
    assert "python devsystem/mandatory_2c_autonomous_recovery_v1.py" in workflow2c
    assert "tests/test_devsystem_mandatory_2c_autonomous_recovery_v1.py" in workflow2c
    assert "tests/test_devsystem_step2c_step2b_step2a_integration_v1.py" in workflow2c
    assert "python devsystem/mandatory_2bc_permanent_enforcement_v1.py" in workflow2c
