from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_step4_page_is_additive_over_certified_v2():
    source = _source("nfl_rushing_yards_hub_v3.py")
    assert "import nfl_rushing_yards_hub_v2 as prior" in source
    assert 'FROZEN_PRIOR = "nfl_rushing_yards_hub_v2"' in source
    assert "_ORIGINAL_STEP3_RENDER = prior._render_step3_projection" in source
    assert "prior._render_step3_projection = _render_step3_and_step4" in source
    assert "prior._render_step3_projection = original_step3" in source


def test_step3_renders_before_market_context():
    source = _source("nfl_rushing_yards_hub_v3.py")
    body = source.split("def _render_step3_and_step4", 1)[1].split("def render_nfl_rushing_yards_hub", 1)[0]
    step3 = body.index("_ORIGINAL_STEP3_RENDER(context, event_id)")
    step4 = body.index("_render_step4_market(context, event_id)")
    assert step3 < step4
    assert "projection influence remains 0.0%" in source


def test_step4_market_join_uses_exact_athlete_and_team_ids():
    source = _source("nfl_rushing_yards_hub_v3.py")
    assert "market_api.market_for_athlete(" in source
    assert '_safe(row.get("official_athlete_id"), "")' in source
    assert '_safe(row.get("official_team_id"), "")' in source
    assert "Projection − Line" in source
    assert "Over Price" in source
    assert "Under Price" in source


def test_probability_ev_grading_and_staking_remain_locked():
    page = _source("nfl_rushing_yards_hub_v3.py")
    client = _source("nfl_rushing_yards_market_api_v1.py")
    for phrase in (
        '"probability_enabled": False',
        '"fair_odds_enabled": False',
        '"ev_enabled": False',
        '"grading_enabled": False',
        '"stake_sizing_enabled": False',
        '"wager_actions": False',
    ):
        assert phrase in client
    assert "GRADE LOCKED" in page
    assert "no probability, value grade or betting recommendation" in page
    assert "sportsbook projection influence remains exactly 0.0%" in page


def test_step4_does_not_import_passing_yards():
    page = _source("nfl_rushing_yards_hub_v3.py")
    client = _source("nfl_rushing_yards_market_api_v1.py")
    assert "nfl_passing_yards" not in page
    assert "nfl_passing_yards" not in client


def test_certified_v2_and_v98_remain_historical_owners():
    v2 = _source("nfl_rushing_yards_hub_v2.py")
    v98 = _source("streamlit_memory_lazy_router_v98.py")
    assert 'FROZEN_PRIOR = "nfl_rushing_yards_hub_v1"' in v2
    assert 'ACTIVE_RUSHING_YARDS_HUB = "nfl_rushing_yards_hub_v2"' in v98
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v97"' in v98


def test_router_v99_advances_only_rushing_target_to_v3():
    source = _source("streamlit_memory_lazy_router_v99.py")
    assert "import streamlit_memory_lazy_router_v98 as prior" in source
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v98"' in source
    assert 'ACTIVE_RUSHING_YARDS_HUB = "nfl_rushing_yards_hub_v3"' in source
    assert 'RUSHING_YARDS_MARKET = "Rushing Yards"' in source
    assert "if market == RUSHING_YARDS_MARKET:" in source
    assert "return _PRIOR_RENDER_NFL(market)" in source
    assert "prior._render_nfl_v98 = _render_nfl_v99" in source
    assert "prior._render_nfl_v98 = original_v98_handler" in source


def test_app_boots_v99_with_step4_heartbeat():
    source = _source("app.py")
    assert "from streamlit_memory_lazy_router_v99 import record_bootstrap_import_ms, render_app" in source
    assert 'FROZEN_V98_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V98_NFL_RUSHING_YARDS_UI_CLEANUP_2026-09-12"' in source
    assert 'DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V99_NFL_RUSHING_YARDS_STEP4_MARKET_CONTEXT_2026-09-12"' in source


def test_step3_projection_engine_still_rejects_market_influence():
    source = _source("nfl_rushing_yards_projection_v1.py")
    assert '"sportsbook_influence": 0.0' in source
    assert '"market_enabled": False' in source
    assert '"ev_enabled": False' in source
    assert '"ranking_enabled": False' in source
    assert '"recommendation_enabled": False' in source
    assert '"stake_sizing_enabled": False' in source
    assert '"wager_actions": False' in source
