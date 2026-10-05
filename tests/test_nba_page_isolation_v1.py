from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


MODULE_PATH = Path("nba_page_isolation_v1.py")


def _load_module():
    assert MODULE_PATH.exists(), "NBA Step-1 isolation guard must exist"
    spec = importlib.util.spec_from_file_location("nba_page_isolation_v1", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_nba_isolation_contract_is_nba_only_and_shared_surfaces_are_locked():
    mod = _load_module()
    assert mod.SPORT == "NBA"
    assert mod.PAGE_SCOPE == "NBA_OVER_UNDER"
    assert mod.MAY_MODIFY_OTHER_SPORTS is False
    assert mod.MAY_MODIFY_SHARED_ROUTER is False
    assert mod.MAY_MODIFY_APP_ENTRYPOINT is False
    assert mod.MAY_MODIFY_SHARED_APIS is False


def test_nba_isolation_allows_only_step1_owned_paths():
    mod = _load_module()
    expected = [
        "devsystem/change_classifier_v1.py",
        "devsystem/task_ledgers/nba-over-under-step1-page-isolation-v1.json",
        "nba_page_isolation_v1.py",
        "tests/test_devsystem_change_classifier_v1.py",
        "tests/test_nba_page_isolation_v1.py",
    ]
    result = mod.assert_nba_only_change(expected)
    assert result["status"] == "GREEN"
    assert result["decision"] == "NBA_ONLY_CHANGE_ALLOWED"
    assert result["changed_paths"] == expected


@pytest.mark.parametrize(
    "forbidden_path",
    [
        "app.py",
        "streamlit_memory_lazy_router_v1.py",
        "streamlit_memory_lazy_router_wnba_pra_repair_v1_step3_data_completeness.py",
        "wnba_data_v2.py",
        "nfl_hub_v18.py",
        "cfb_top_picks_page_v9.py",
        "mlb_schedule_v32.py",
        "sports_api/wnba_season_stats.py",
        ".streamlit/config.toml",
    ],
)
def test_nba_isolation_rejects_shared_or_other_sport_paths(forbidden_path: str):
    mod = _load_module()
    with pytest.raises(mod.NBAIsolationViolation):
        mod.assert_nba_only_change([forbidden_path])


def test_nba_isolation_rejects_unowned_nba_files_until_a_later_step_expands_scope():
    mod = _load_module()
    with pytest.raises(mod.NBAIsolationViolation):
        mod.assert_nba_only_change(["nba_over_under_page_v1.py"])
