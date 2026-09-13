from __future__ import annotations

from pathlib import Path
import subprocess
import sys

import nfl_rushing_yards_hub_v10 as speed

ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_request_scope_memo_executes_identical_work_once():
    calls: list[str] = []
    stats: dict = {}

    def original(value: str):
        calls.append(value)
        return {"value": value}

    wrapped = speed._timed_request_memo(original, lambda value: (value,), stats, "probe")
    first = wrapped("401000001")
    second = wrapped("401000001")
    third = wrapped("401000001")

    assert first is second is third
    assert calls == ["401000001"]
    assert stats["probe"]["calls"] == 3
    assert stats["probe"]["misses"] == 1
    assert stats["probe"]["hits"] == 2
    assert stats["probe"]["work_ms"] >= 0.0


def test_v10_patches_only_repeated_render_work_and_restores_it():
    source = _source("nfl_rushing_yards_hub_v10.py")
    assert "import nfl_rushing_yards_hub_v9 as prior" in source
    assert 'FROZEN_PRIOR = "nfl_rushing_yards_hub_v9"' in source
    assert "PERFORMANCE_ONLY = True" in source
    assert "SPORTSBOOK_PROJECTION_INFLUENCE = 0.0" in source

    for target in (
        "context_page._load_rushing_context",
        "projection_page.projection.build_event_projections",
        "market_page._load_rushing_market",
        "market_page.market_api.market_for_athlete",
    ):
        assert target in source

    assert "context_page._load_rushing_context = original_context" in source
    assert "projection_page.projection.build_event_projections = original_projection" in source
    assert "market_page._load_rushing_market = original_market" in source
    assert "market_page.market_api.market_for_athlete = original_athlete_market" in source
    assert 'st.session_state["nfl_rushing_yards_speed_v1_last"]' in source


def test_v10_does_not_change_projection_or_market_semantics():
    source = _source("nfl_rushing_yards_hub_v10.py")
    for forbidden in (
        "projection_weight =",
        "probability_enabled = True",
        "grading_enabled = True",
        "ev_enabled = True",
        "wager_actions = True",
        "stake_size",
        "kelly",
        "MAX_MARKET_AGE_SECONDS =",
        "ttl=",
    ):
        assert forbidden not in source


def test_v106_is_a_true_lazy_fast_route_over_v105():
    source = _source("streamlit_memory_lazy_router_v106.py")
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v105"' in source
    assert 'ACTIVE_PAGE = "nfl_rushing_yards_hub_v10"' in source
    assert 'RUSHING_YARDS_MARKET = "Rushing Yards"' in source
    assert "return importlib.import_module(FROZEN_ROUTER)" in source
    assert "import streamlit_memory_lazy_router_v105" not in source
    assert "historical router chain" in source
    assert "SKIPPED" in source
    assert "projection math unchanged" in source
    assert 'st.session_state["nfl_rushing_yards_cold_start_v1_last"]' in source


def test_v106_fresh_import_does_not_load_frozen_router_or_active_page():
    code = (
        "import sys; "
        "import streamlit_memory_lazy_router_v106 as r; "
        "assert r.FROZEN_ROUTER not in sys.modules; "
        "assert r.ACTIVE_PAGE not in sys.modules; "
        "print('RUSH_FAST_IMPORT_GREEN')"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "RUSH_FAST_IMPORT_GREEN" in result.stdout


def test_v106_restores_exact_rushing_route_from_query_only():
    source = _source("streamlit_memory_lazy_router_v106.py")
    assert 'ROUTE_QUERY_SPORT = "ks_nfl_sport"' in source
    assert 'ROUTE_QUERY_MARKET = "ks_nfl_market"' in source
    assert 'st.session_state["ks_sport_touch"] = NFL_SPORT_LABEL' in source
    assert 'st.session_state["ks_nfl_market_touch"] = RUSHING_YARDS_MARKET' in source
    assert "if _fast_route_active():" in source
    assert "return _render_direct_rushing()" in source
    assert "return _load_prior().render_app()" in source


def test_app_activates_v106_and_preserves_v105_rollback_heartbeat():
    source = _source("app.py")
    assert "from streamlit_memory_lazy_router_v106 import record_bootstrap_import_ms, render_app" in source
    assert 'FROZEN_V105_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V105_NFL_RUSHING_YARDS_PAGE_STEP6_SUPPORT_CONCERNS_2026-09-12"' in source
    assert 'DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V106_NFL_RUSHING_YARDS_PERFORMANCE_FAST_ROUTE_2026-09-12"' in source
    assert 'st.session_state.get("nfl_rushing_yards_cold_start_v1_last")' in source
    assert 'st.session_state.get("nfl_rushing_yards_speed_v1_last")' in source


def test_frozen_final_page_and_router_remain_certified_owners():
    v9 = _source("nfl_rushing_yards_hub_v9.py")
    v105 = _source("streamlit_memory_lazy_router_v105.py")
    assert 'FROZEN_PRIOR = "nfl_rushing_yards_hub_v8"' in v9
    assert "PAGE_BUILD_STEP = 6" in v9
    assert "PAGE_BUILD_TOTAL = 6" in v9
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v104"' in v105
    assert 'ACTIVE_RUSHING_YARDS_HUB = "nfl_rushing_yards_hub_v9"' in v105


def test_frozen_projection_market_and_cache_freshness_remain_intact():
    projection = _source("nfl_rushing_yards_projection_v1.py")
    market = _source("nfl_rushing_yards_market_api_v1.py")
    v1 = _source("nfl_rushing_yards_hub_v1.py")
    v3 = _source("nfl_rushing_yards_hub_v3.py")
    assert '"sportsbook_influence": 0.0' in projection
    assert '"projection_weight": 0.0' in market
    assert "MAX_MARKET_AGE_SECONDS = 300" in market
    assert "@st.cache_data(ttl=120, show_spinner=False)" in v1
    assert "@st.cache_data(ttl=20, show_spinner=False)" in v3
    assert '"probability_enabled": False' in market
    assert '"grading_enabled": False' in market
    assert '"wager_actions": False' in market


def test_rushing_browser_witness_requires_fast_path_and_real_page():
    source = _source("devsystem/nfl_rushing_yards_fast_route_browser_v1.py")
    assert "ks_nfl_sport=NFL" in source
    assert "ks_nfl_market=Rushing%20Yards" in source
    assert 'FAST_MARKER = "RUSHING FAST PATH V1"' in source
    assert 'PAGE_MARKER = "Ground Game Lab"' in source
    assert 'READY_MARKER = "Monster Performance Diagnosis"' in source
    assert "historical router chain SKIPPED" in source
    assert "active_page_import_ms" in source
    assert "full_route_ready_ms" in source
