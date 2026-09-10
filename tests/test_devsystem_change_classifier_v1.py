from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _load():
    path = ROOT / "devsystem" / "change_classifier_v1.py"
    spec = importlib.util.spec_from_file_location("change_classifier_v1", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_wnba_does_not_accidentally_classify_as_nba():
    module = _load()
    result = module.classify([
        "sports_api/wnba_step20b_runtime_acceleration.py",
        "tests/test_wnba_step20b_runtime_acceleration.py",
    ])
    assert result["wnba"] is True
    assert result["nba"] is False
    assert result["unprotected_domains"] == []


def test_api_subdirectories_classify_to_the_correct_sport():
    module = _load()
    result = module.classify([
        "sports_api/api/mlb.py",
        "sports_api/collectors/mlb_fanduel_direct.py",
    ])
    assert result["mlb"] is True
    assert result["core"] is False
    assert result["api"] is True


def test_unprotected_existing_nfl_lane_fails_closed():
    module = _load()
    result = module.classify(["nfl_moneyline_hub_v8.py"])
    assert result["nfl"] is True
    assert result["unprotected_domains"] == ["nfl"]
    assert result["risk_tier"] == "blocked"


def test_future_domains_are_reserved_and_fail_closed():
    module = _load()
    result = module.classify(["nba_model_v1.py", "soccer_moneyline_v1.py"])
    assert result["nba"] is True
    assert result["soccer"] is True
    assert result["unprotected_domains"] == ["nba", "soccer"]


def test_devsystem_change_is_core_high_risk():
    module = _load()
    result = module.classify(["devsystem/final_gate_v1.py"])
    assert result["core"] is True
    assert result["infra"] is True
    assert result["risk_tier"] == "high"
