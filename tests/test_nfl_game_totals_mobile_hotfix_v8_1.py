from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "nfl_game_totals_hub_v8_1.py"
HELPER = ROOT / "sports_api" / "nfl_game_totals_mobile_navigation_v1.py"
ROUTER = ROOT / "nfl_hub_v18.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _load_helper():
    if not HELPER.exists():
        pytest.fail("mobile navigation helper has not been implemented yet")
    spec = importlib.util.spec_from_file_location("mobile_navigation", HELPER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_hotfix_runtime_files_exist_and_router_advances_only_game_total():
    assert PAGE.exists(), "V8.1 mobile hotfix page has not been implemented yet"
    assert HELPER.exists(), "mobile navigation helper has not been implemented yet"
    router = _read(ROUTER)
    assert 'if market == "Game Total":' in router
    assert "from nfl_game_totals_hub_v8_1 import render_nfl_game_totals_hub" in router
    assert "from nfl_moneyline_hub_v9 import render_nfl_moneyline_hub" in router


def test_find_next_game_day_skips_empty_dates_and_returns_first_verified_slate():
    module = _load_helper()
    calls: list[str] = []

    def loader(day_str: str):
        calls.append(day_str)
        if day_str == "2026-09-17":
            return pd.DataFrame([{"game_id": "401772510"}]), {"request_ok": True, "games": 1}
        return pd.DataFrame(), {"request_ok": True, "games": 0}

    result = module.find_next_game_day(date(2026, 9, 15), loader, max_days=7)
    assert result["ready"] is True
    assert result["date"] == date(2026, 9, 17)
    assert result["day_str"] == "2026-09-17"
    assert calls == ["2026-09-16", "2026-09-17"]


def test_find_next_game_day_fails_closed_on_provider_failure():
    module = _load_helper()

    def loader(day_str: str):
        return pd.DataFrame(), {"request_ok": False, "error": "provider unavailable"}

    result = module.find_next_game_day(date(2026, 9, 15), loader, max_days=7)
    assert result["ready"] is False
    assert result["date"] is None
    assert result["provider_failed"] is True
    assert "provider" in result["reason"].lower()


def test_hotfix_auto_surfaces_next_slate_only_when_today_is_empty():
    source = _read(PAGE)
    assert "import nfl_game_totals_hub_v8 as v8" in source
    assert "AUTO_ADVANCE_EMPTY_TODAY = True" in source
    assert "find_next_game_day(" in source
    assert "selected == today" in source
    assert "nfl_game_totals_v8_1_pending_date" in source
    assert "st.rerun()" in source


def test_mobile_controls_are_large_and_explicit():
    source = _read(PAGE)
    assert '"➡️ Next Game Day"' in source
    assert '"🔄 Reload Data"' in source
    assert "use_container_width=True" in source
    assert "No verified NFL games were returned for this date." in source
    assert "Next Game Day" in source


def test_reload_data_clears_only_game_totals_cache_functions():
    source = _read(PAGE)
    assert "def _clear_game_totals_caches" in source
    for token in (
        "load_nfl_slate",
        "_cached_market_batch",
        "_cached_team_profiles",
        "_cached_pace_profiles",
        "_cached_explosive_profiles",
        "_cached_red_zone_drive_profiles",
        "_cached_environment_contexts",
    ):
        assert token in source
    assert "st.cache_data.clear()" not in source


def test_reload_data_also_clears_multisource_router_caches_without_global_clear():
    source = _read(PAGE)
    assert "from sports_api.nfl_data_router_v1 import clear_router_caches" in source
    assert "clear_router_caches()" in source
    assert "st.cache_data.clear()" not in source


def test_hotfix_preserves_certified_step8_projection_firewall():
    source = _read(PAGE)
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source
    assert "PROJECTION_MODEL_ENABLED = True" in source
    assert "MARKET_COMPARISON_ENABLED = False" in source
    assert "WAGER_ACTIONS_ENABLED = False" in source
    assert "v8._render_schedule(" in source
