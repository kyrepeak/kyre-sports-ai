from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = Path("nba_spread_page_isolation_v1.py")


def _load_module():
    assert MODULE_PATH.exists(), "NBA Spread Step-1 isolation guard must exist"
    spec = importlib.util.spec_from_file_location("nba_spread_page_isolation_v1", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_nba_spread_isolation_contract_locks_shared_and_other_sport_surfaces():
    mod = _load_module()
    assert mod.SPORT == "NBA"
    assert mod.PAGE_SCOPE == "NBA_SPREAD"
    assert mod.MAY_MODIFY_OTHER_SPORTS is False
    assert mod.MAY_MODIFY_SHARED_ROUTER is False
    assert mod.MAY_MODIFY_APP_ENTRYPOINT is False
    assert mod.MAY_MODIFY_SHARED_APIS is False
    assert mod.MAY_MODIFY_EXISTING_NBA_WORKSTREAMS is False


def test_nba_spread_isolation_allows_only_step1_owned_paths():
    mod = _load_module()
    expected = [
        "devsystem/execution_plans/nba-spread-step1-page-isolation-v1.json",
        "devsystem/runless_proof_plans/nba-spread-step1-page-isolation-v1.json",
        "devsystem/task_ledgers/nba-spread-step1-page-isolation-v1.json",
        "nba_spread_page_isolation_v1.py",
        "tests/test_nba_spread_page_isolation_v1.py",
    ]
    result = mod.assert_nba_spread_only_change(expected)
    assert result["status"] == "GREEN"
    assert result["decision"] == "NBA_SPREAD_ONLY_CHANGE_ALLOWED"
    assert result["page_scope"] == "NBA_SPREAD"
    assert result["changed_paths"] == expected
    assert result["existing_nba_workstreams_modified"] is False


@pytest.mark.parametrize(
    "forbidden_path",
    [
        "devsystem/change_classifier_v1.py",
        "tests/test_devsystem_change_classifier_v1.py",
        "app.py",
        "streamlit_memory_lazy_router_v1.py",
        "nba_page_isolation_v1.py",
        "nba_over_under_page_v1.py",
        "wnba_data_v2.py",
        "nfl_hub_v18.py",
        "cfb_top_picks_page_v9.py",
        "mlb_schedule_v32.py",
        "sports_api/main.py",
        ".streamlit/config.toml",
    ],
)
def test_nba_spread_isolation_rejects_shared_other_sport_and_existing_nba_paths(forbidden_path: str):
    mod = _load_module()
    with pytest.raises(mod.NBASpreadIsolationViolation):
        mod.assert_nba_spread_only_change([forbidden_path])


def test_nba_spread_isolation_rejects_future_unowned_spread_files_until_scope_expands():
    mod = _load_module()
    with pytest.raises(mod.NBASpreadIsolationViolation):
        mod.assert_nba_spread_only_change(["nba_spread_page_v1.py"])
