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


def test_global_monster_permanent_gate_requires_step2bc_and_isolation():
    permanent_gate = (ROOT / "devsystem/permanent_gate_v1.py").read_text(encoding="utf-8")
    targeted_ci = (ROOT / ".github/workflows/devsystem-targeted-ci.yml").read_text(encoding="utf-8")

    for marker in (
        '"devsystem/mandatory_2b_reliability_gate_v1.py"',
        '"devsystem/mandatory_2c_autonomous_recovery_v1.py"',
        '"devsystem/mandatory_2bc_permanent_enforcement_v1.py"',
        '"devsystem/monster_system_isolation_v1.py"',
    ):
        assert marker in permanent_gate

    assert "python devsystem/monster_system_isolation_v1.py" in permanent_gate
    assert "python devsystem/mandatory_2bc_permanent_enforcement_v1.py" in permanent_gate
    assert "python devsystem/monster_system_isolation_v1.py" in targeted_ci
    assert "python devsystem/mandatory_2bc_permanent_enforcement_v1.py" in targeted_ci


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
