from __future__ import annotations

import importlib.util
from pathlib import Path
import pytest


ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: str):
    target = ROOT / path
    spec = importlib.util.spec_from_file_location(name, target)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_permanent_contract_is_green():
    module = _load("permanent_gate_v1", "devsystem/permanent_gate_v1.py")
    result = module.validate()
    assert result["status"] == "GREEN"
    assert result["active_domains"] == ["cfb", "mlb", "wnba"]
    assert "nfl" in result["blocked_until_activated"]
    assert result["critical_test_count"] == 13


def test_final_gate_accepts_success_and_skipped_only():
    module = _load("final_gate_v1", "devsystem/final_gate_v1.py")
    result = module.evaluate({
        "classify": {"result": "success"},
        "browser-qa": {"result": "skipped"},
        "mlb-critical": {"result": "success"},
    })
    assert result["status"] == "GREEN"

    with pytest.raises(module.FinalGateFailure):
        module.evaluate({
            "classify": {"result": "success"},
            "cfb-critical": {"result": "failure"},
        })
