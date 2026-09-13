from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_v4_is_visual_only_additive_over_certified_v3():
    source = _source("nfl_rushing_yards_hub_v4.py")
    assert "import nfl_rushing_yards_hub_v3 as prior" in source
    assert 'FROZEN_PRIOR = "nfl_rushing_yards_hub_v3"' in source
    assert 'PAGE_BUILD_STEP = 1' in source
    assert 'PAGE_BUILD_TOTAL = 6' in source
    assert "_ORIGINAL_CONTEXT_BOARD_V2 = step3._render_context_board_v2" in source
    assert "step3._render_context_board_v2 = _render_context_board_v4" in source
    assert "step3._render_context_board_v2 = original_context" in source


def test_compact_card_uses_exact_id_visuals_only():
    source = _source("nfl_rushing_yards_hub_v4.py")
    assert "athlete_id.isdigit()" in source
    assert "https://a.espncdn.com/i/headshots/nfl/players/full/" in source
    assert "https://a.espncdn.com/i/teamlogos/nfl/500/" in source
    assert "official_athlete_id" in source
    assert "official_team_id" in source
    assert "fuzzy" in source.lower()
    assert "synthetic" in source.lower()


def test_compact_card_reuses_certified_projection_and_market_outputs():
    source = _source("nfl_rushing_yards_hub_v4.py")
    assert "step3.projection.build_event_projections(context)" in source
    assert "prior._load_rushing_market(event_id)" in source
    assert "prior.market_api.market_for_athlete(" in source
    assert "Projected Rush Yards" in source
    assert "FanDuel Line" in source
    assert "Projection − Line" in source
    assert "Expected Carries" in source
    assert "Expected YPC" in source


def test_compact_card_does_not_add_probability_ev_or_grading():
    source = _source("nfl_rushing_yards_hub_v4.py")
    assert "sportsbook projection influence <strong>0.0%</strong>" in source
    assert "probability/EV/grade OFF" in source
    assert "recommendation" in source
    assert "wagering" in source
    assert "nfl_passing_yards" not in source


def test_v100_advances_only_rushing_yards_to_v4():
    source = _source("streamlit_memory_lazy_router_v100.py")
    assert "import streamlit_memory_lazy_router_v99 as prior" in source
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v99"' in source
    assert 'ACTIVE_RUSHING_YARDS_HUB = "nfl_rushing_yards_hub_v4"' in source
    assert 'RUSHING_YARDS_MARKET = "Rushing Yards"' in source
    assert "if market == RUSHING_YARDS_MARKET:" in source
    assert "return _PRIOR_RENDER_NFL(market)" in source
    assert "prior._render_nfl_v99 = _render_nfl_v100" in source
    assert "prior._render_nfl_v99 = original_v99_handler" in source


def test_app_boots_v100_and_preserves_v99_heartbeat():
    source = _source("app.py")
    assert "from streamlit_memory_lazy_router_v100 import record_bootstrap_import_ms, render_app" in source
    assert 'FROZEN_V99_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V99_NFL_RUSHING_YARDS_STEP4_MARKET_CONTEXT_2026-09-12"' in source
    assert 'DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V100_NFL_RUSHING_YARDS_PAGE_STEP1_COMPACT_PLAYER_CARDS_2026-09-12"' in source


def test_certified_v3_and_v99_stay_historical_owners():
    v3 = _source("nfl_rushing_yards_hub_v3.py")
    v99 = _source("streamlit_memory_lazy_router_v99.py")
    assert 'FROZEN_PRIOR = "nfl_rushing_yards_hub_v2"' in v3
    assert 'ACTIVE_RUSHING_YARDS_HUB = "nfl_rushing_yards_hub_v3"' in v99
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v98"' in v99


def test_frozen_projection_market_safety_remains_intact():
    projection = _source("nfl_rushing_yards_projection_v1.py")
    market = _source("nfl_rushing_yards_market_api_v1.py")
    assert '"sportsbook_influence": 0.0' in projection
    assert '"market_enabled": False' in projection
    assert '"ev_enabled": False' in projection
    assert '"projection_weight": 0.0' in market
    assert '"probability_enabled": False' in market
    assert '"grading_enabled": False' in market
    assert '"wager_actions": False' in market
