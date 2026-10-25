from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: str):
    target = ROOT / path
    spec = importlib.util.spec_from_file_location(name, target)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_monster_permanent_system_gate_composes_full_control_chain():
    gate = _load(
        "monster_system_permanent_gate_v1",
        "devsystem/monster_system_permanent_gate_v1.py",
    )
    result = gate.validate()
    assert result["status"] == "GREEN"
    assert result["monster_only"] is True
    assert result["base_permanent_gate_green"] is True
    assert result["step2bc_permanent_enforcement_green"] is True
    assert result["isolation_guard_green"] is True
    assert result["canonical_front_door_green"] is True
    assert result["step2a_step2b_step2c_chain_permanent"] is True
    assert result["anti_loop_permanent"] is True
    assert result["human_only_blocker_rule_permanent"] is True


def test_monster_permanent_workflow_is_scoped_to_monster_main_only():
    workflow = (ROOT / ".github/workflows/monster-step2bc-permanent-system-v1.yml").read_text(encoding="utf-8")
    assert "branches: [monster-main]" in workflow
    assert "python devsystem/monster_system_permanent_gate_v1.py" in workflow
    assert "python devsystem/monster_execution_front_door_v1.py" in workflow
    assert "python devsystem/monster_system_isolation_v1.py" in workflow
    assert "tests/test_devsystem_monster_step2bc_global_permanence_v1.py" in workflow
    assert "api2" not in workflow.lower()


def test_monster_hard_isolation_rejects_foreign_api2_state():
    isolation = _load(
        "monster_system_isolation_v1",
        "devsystem/monster_system_isolation_v1.py",
    )

    allowed = {
        "task_id": "monster-step2bc-permanent-system-v1",
        "checkpoint_id": "2BC",
        "authoritative_path": {
            "repository": "kyrepeak/kyre-sports-ai",
            "branch": "monster-step2bc-permanent-system-v1",
            "target": "monster:control-plane",
            "proof_path": "monster-runless-v2",
        },
        "evidence": {"source": "monster-control-test", "fingerprint": "monster-only-evidence"},
    }
    assert isolation.assert_monster_only(allowed)["monster_only"] is True

    contaminated = [
        {**allowed, "task_id": "api2-some-task"},
        {**allowed, "authoritative_path": {**allowed["authoritative_path"], "branch": "api2-live-branch"}},
        {**allowed, "authoritative_path": {**allowed["authoritative_path"], "proof_path": "API 2 proof"}},
        {**allowed, "evidence": {"source": "api_2-ledger", "fingerprint": "x"}},
    ]
    for payload in contaminated:
        with pytest.raises(isolation.MonsterSystemIsolationFailure):
            isolation.assert_monster_only(payload)


def test_monster_canonical_front_door_blocks_foreign_state_before_step2a():
    front = _load(
        "monster_execution_front_door_v1",
        "devsystem/monster_execution_front_door_v1.py",
    )
    result = front.contract_self_test()
    assert result["status"] == "GREEN"
    assert result["monster_only"] is True
    assert result["foreign_state_blocked"] is True
    assert result["step2a_chain_preserved"] is True
    assert result["step2b_chain_preserved"] is True
    assert result["step2c_chain_preserved"] is True
    assert result["anti_loop_preserved"] is True
