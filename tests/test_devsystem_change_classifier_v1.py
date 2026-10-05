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


def test_nfl_lane_is_protected_after_activation():
    module = _load()
    result = module.classify(["nfl_moneyline_hub_v8.py", "nfl_passing_yards_hub_v1.py"])
    assert result["nfl"] is True
    assert result["unprotected_domains"] == []
    assert result["risk_tier"] != "blocked"


def test_nba_step1_bootstrap_scope_is_allowed_while_domain_remains_planned():
    module = _load()
    result = module.classify([
        "devsystem/change_classifier_v1.py",
        "devsystem/task_ledgers/nba-over-under-step1-page-isolation-v1.json",
        "nba_page_isolation_v1.py",
        "tests/test_devsystem_change_classifier_v1.py",
        "tests/test_nba_page_isolation_v1.py",
    ])
    assert result["nba"] is True
    assert result["core"] is True
    assert result["unprotected_domains"] == []
    assert result["risk_tier"] == "high"


def test_future_domains_are_reserved_and_fail_closed():
    module = _load()
    result = module.classify(["nba_model_v1.py", "soccer_moneyline_v1.py"])
    assert result["nba"] is True
    assert result["soccer"] is True
    assert result["unprotected_domains"] == ["nba", "soccer"]


def test_unapproved_nba_file_cannot_hide_inside_step1_bootstrap_diff():
    module = _load()
    result = module.classify([
        "nba_page_isolation_v1.py",
        "nba_over_under_page_v1.py",
    ])
    assert result["nba"] is True
    assert result["unprotected_domains"] == ["nba"]
    assert result["risk_tier"] == "blocked"


def test_devsystem_change_is_core_high_risk():
    module = _load()
    result = module.classify(["devsystem/final_gate_v1.py"])
    assert result["core"] is True
    assert result["infra"] is True
    assert result["risk_tier"] == "high"


def test_root_streamlit_wnba_router_is_wnba_owned_not_core():
    module = _load()
    result = module.classify([
        "streamlit_memory_lazy_router_wnba_pra_repair_v1_step2_team_identity.py"
    ])
    assert result["wnba"] is True
    assert result["nba"] is False
    assert result["core"] is False
    assert result["ui"] is True
    assert result["risk_tier"] == "medium"


def test_unscoped_root_streamlit_file_remains_core():
    module = _load()
    result = module.classify(["streamlit_memory_lazy_router_generic.py"])
    assert result["core"] is True
    assert result["ui"] is True
    assert result["risk_tier"] == "high"
