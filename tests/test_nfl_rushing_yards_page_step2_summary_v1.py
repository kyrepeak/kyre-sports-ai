from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_v5_is_visual_only_additive_over_certified_v4():
    source = _source("nfl_rushing_yards_hub_v5.py")
    assert "import nfl_rushing_yards_hub_v4 as prior" in source
    assert 'FROZEN_PRIOR = "nfl_rushing_yards_hub_v4"' in source
    assert "PAGE_BUILD_STEP = 2" in source
    assert "PAGE_BUILD_TOTAL = 6" in source
    assert "_ORIGINAL_COMPACT_PLAYER_CARD_V4 = prior._compact_player_card" in source
    assert "prior._compact_player_card = _compact_player_card_v5" in source
    assert "prior._compact_player_card = original_card" in source


def test_step2_summary_contains_the_six_compact_metrics():
    source = _source("nfl_rushing_yards_hub_v5.py")
    for label in (
        "Projection",
        "Live Line",
        "Proj − Line",
        "Exp Carries",
        "Exp YPC",
        "Market Age",
    ):
        assert label in source
    assert 'aria-label="Rushing yards summary metrics"' in source
    assert "krush5-summary" in source
    assert "krush5-box" in source


def test_step2_only_reuses_existing_certified_fields():
    source = _source("nfl_rushing_yards_hub_v5.py")
    assert 'projection_row.get("projection_yards")' in source
    assert 'projection_row.get("expected_carries")' in source
    assert 'projection_row.get("expected_yards_per_carry")' in source
    assert 'market_row.get("line")' in source
    assert 'market_row.get("age_seconds")' in source
    assert "projection - line" in source
    assert "sportsbook projection influence remains exactly 0.0%" in source


def test_step2_does_not_add_model_or_wager_behavior():
    source = _source("nfl_rushing_yards_hub_v5.py")
    assert "build_event_projections(" not in source
    assert "market_for_athlete(" not in source
    assert "nfl_passing_yards" not in source
    for forbidden in (
        "probability_enabled = True",
        "grading_enabled = True",
        "wager_actions = True",
        "stake_size",
        "kelly",
    ):
        assert forbidden not in source.lower()


def test_v101_advances_only_rushing_yards_to_v5():
    source = _source("streamlit_memory_lazy_router_v101.py")
    assert "import streamlit_memory_lazy_router_v100 as prior" in source
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v100"' in source
    assert 'ACTIVE_RUSHING_YARDS_HUB = "nfl_rushing_yards_hub_v5"' in source
    assert 'RUSHING_YARDS_MARKET = "Rushing Yards"' in source
    assert "if market == RUSHING_YARDS_MARKET:" in source
    assert "return _PRIOR_RENDER_NFL(market)" in source
    assert "prior._render_nfl_v100 = _render_nfl_v101" in source
    assert "prior._render_nfl_v100 = original_handler" in source


def test_app_boots_v101_and_preserves_v100_heartbeat():
    source = _source("app.py")
    assert "from streamlit_memory_lazy_router_v101 import record_bootstrap_import_ms, render_app" in source
    assert 'FROZEN_V100_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V100_NFL_RUSHING_YARDS_PAGE_STEP1_COMPACT_PLAYER_CARDS_2026-09-12"' in source
    assert 'DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V101_NFL_RUSHING_YARDS_PAGE_STEP2_SUMMARY_METRICS_2026-09-12"' in source


def test_frozen_v4_and_v100_remain_page_step1_owners():
    v4 = _source("nfl_rushing_yards_hub_v4.py")
    v100 = _source("streamlit_memory_lazy_router_v100.py")
    assert 'FROZEN_PRIOR = "nfl_rushing_yards_hub_v3"' in v4
    assert "PAGE_BUILD_STEP = 1" in v4
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v99"' in v100
    assert 'ACTIVE_RUSHING_YARDS_HUB = "nfl_rushing_yards_hub_v4"' in v100


def test_frozen_projection_and_market_safety_remain_intact():
    projection = _source("nfl_rushing_yards_projection_v1.py")
    market = _source("nfl_rushing_yards_market_api_v1.py")
    assert '"sportsbook_influence": 0.0' in projection
    assert '"market_enabled": False' in projection
    assert '"ev_enabled": False' in projection
    assert '"projection_weight": 0.0' in market
    assert '"probability_enabled": False' in market
    assert '"grading_enabled": False' in market
    assert '"wager_actions": False' in market
