from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_v8_is_additive_over_frozen_v7():
    source = _source("nfl_rushing_yards_hub_v8.py")
    assert "import nfl_rushing_yards_hub_v7 as prior" in source
    assert 'FROZEN_PRIOR = "nfl_rushing_yards_hub_v7"' in source
    assert "PAGE_BUILD_STEP = 5" in source
    assert "PAGE_BUILD_TOTAL = 6" in source
    assert "_ORIGINAL_COMPACT_PLAYER_CARD_V7 = prior._compact_player_card_v7" in source
    assert "prior._compact_player_card_v7 = _compact_player_card_v8" in source
    assert "prior._compact_player_card_v7 = original_card" in source


def test_step5_displays_certified_projection_recipe_fields():
    source = _source("nfl_rushing_yards_hub_v8.py")
    for field in (
        'projection_row.get("formula")',
        'projection_row.get("workload_source")',
        'projection_row.get("player_efficiency_source")',
        'projection_row.get("efficiency_coverage")',
        'projection_row.get("coverage_grade")',
        'projection_row.get("coverage_basis")',
        'projection_row.get("efficiency_components")',
        'projection_row.get("expected_yards_per_carry")',
    ):
        assert field in source
    for label in (
        "Projection Recipe",
        "Certified Formula",
        "Workload Source",
        "Player Efficiency Source",
        "Certified Expected YPC",
        "Certified blend weight",
    ):
        assert label in source
    assert 'aria-label="Projection recipe"' in source


def test_step5_limits_components_to_certified_projection_keys():
    source = _source("nfl_rushing_yards_hub_v8.py")
    assert '"player_yards_per_carry"' in source
    assert '"opponent_yards_per_carry_allowed"' in source
    assert "normalized_weight" in source
    assert "efficiency_components" in source


def test_step5_does_not_rebuild_projection_or_market_logic():
    source = _source("nfl_rushing_yards_hub_v8.py")
    assert "nfl_rushing_yards_projection_v1" not in source
    assert "nfl_rushing_yards_market_api_v1" not in source
    assert "build_event_projections(" not in source
    assert "build_player_projection(" not in source
    assert "weighted_blend(" not in source
    assert "market_for_athlete(" not in source
    assert "EFFICIENCY_WEIGHTS" not in source
    assert "nfl_passing_yards" not in source


def test_v104_advances_only_rushing_yards_to_v8():
    source = _source("streamlit_memory_lazy_router_v104.py")
    assert "import streamlit_memory_lazy_router_v103 as prior" in source
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v103"' in source
    assert 'ACTIVE_RUSHING_YARDS_HUB = "nfl_rushing_yards_hub_v8"' in source
    assert 'RUSHING_YARDS_MARKET = "Rushing Yards"' in source
    assert "if market == RUSHING_YARDS_MARKET:" in source
    assert "return _PRIOR_RENDER_NFL(market)" in source
    assert "prior._render_nfl_v103 = _render_nfl_v104" in source
    assert "prior._render_nfl_v103 = original_handler" in source


def test_app_boots_v104_and_preserves_v103_heartbeat():
    source = _source("app.py")
    assert "from streamlit_memory_lazy_router_v104 import record_bootstrap_import_ms, render_app" in source
    assert 'FROZEN_V103_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V103_NFL_RUSHING_YARDS_PAGE_STEP4_OPPONENT_RUN_DEFENSE_2026-09-12"' in source
    assert 'DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V104_NFL_RUSHING_YARDS_PAGE_STEP5_PROJECTION_RECIPE_2026-09-12"' in source


def test_frozen_v7_and_v103_remain_step4_owners():
    v7 = _source("nfl_rushing_yards_hub_v7.py")
    v103 = _source("streamlit_memory_lazy_router_v103.py")
    assert 'FROZEN_PRIOR = "nfl_rushing_yards_hub_v6"' in v7
    assert "PAGE_BUILD_STEP = 4" in v7
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v102"' in v103
    assert 'ACTIVE_RUSHING_YARDS_HUB = "nfl_rushing_yards_hub_v7"' in v103


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
