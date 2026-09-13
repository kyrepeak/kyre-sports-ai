from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_v9_is_final_additive_layer_over_frozen_v8():
    source = _source("nfl_rushing_yards_hub_v9.py")
    assert "import nfl_rushing_yards_hub_v8 as prior" in source
    assert 'FROZEN_PRIOR = "nfl_rushing_yards_hub_v8"' in source
    assert "PAGE_BUILD_STEP = 6" in source
    assert "PAGE_BUILD_TOTAL = 6" in source
    assert "_ORIGINAL_COMPACT_PLAYER_CARD_V8 = prior._compact_player_card_v8" in source
    assert "prior._compact_player_card_v8 = _compact_player_card_v9" in source
    assert "prior._compact_player_card_v8 = original_card" in source
    assert "Final Page Step 6 / 6" in source


def test_step6_uses_only_certified_projection_explanation_fields():
    source = _source("nfl_rushing_yards_hub_v9.py")
    for field in (
        'projection_row.get("expected_yards_per_carry")',
        'projection_row.get("expected_carries")',
        'projection_row.get("efficiency_coverage")',
        'projection_row.get("coverage_grade")',
        'projection_row.get("coverage_basis")',
        'projection_row.get("workload_source")',
        'projection_row.get("efficiency_components")',
    ):
        assert field in source
    assert '"player_yards_per_carry"' in source
    assert '"opponent_yards_per_carry_allowed"' in source


def test_step6_support_concern_logic_is_descriptive_only():
    source = _source("nfl_rushing_yards_hub_v9.py")
    assert "if value >= expected_ypc:" in source
    assert "supports.append(sentence)" in source
    assert "concerns.append(sentence)" in source
    assert "Descriptive explanation only" in source
    assert "not a betting grade" in source
    assert "sportsbook projection influence remains 0.0%" in source
    assert 'aria-label="Projection supports and concerns"' in source
    assert "Support vs Concern" in source
    assert "Concerns / Counterweights" in source


def test_step6_does_not_use_market_to_classify_support_or_concern():
    source = _source("nfl_rushing_yards_hub_v9.py")
    assert "def _support_concern_rows(projection_row" in source
    assert "def _support_concerns_html(projection_row" in source
    assert "market_row.get(" not in source
    assert "projection_yards -" not in source
    assert "line - projection" not in source


def test_step6_does_not_rebuild_projection_market_or_wager_logic():
    source = _source("nfl_rushing_yards_hub_v9.py")
    assert "nfl_rushing_yards_projection_v1" not in source
    assert "nfl_rushing_yards_market_api_v1" not in source
    assert "build_event_projections(" not in source
    assert "build_player_projection(" not in source
    assert "weighted_blend(" not in source
    assert "market_for_athlete(" not in source
    assert "EFFICIENCY_WEIGHTS" not in source
    assert "nfl_passing_yards" not in source
    for forbidden in (
        "probability_enabled = True",
        "grading_enabled = True",
        "recommendation_enabled = True",
        "wager_actions = True",
        "stake_size",
        "kelly",
    ):
        assert forbidden not in source


def test_v105_advances_only_rushing_yards_to_v9():
    source = _source("streamlit_memory_lazy_router_v105.py")
    assert "import streamlit_memory_lazy_router_v104 as prior" in source
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v104"' in source
    assert 'ACTIVE_RUSHING_YARDS_HUB = "nfl_rushing_yards_hub_v9"' in source
    assert 'RUSHING_YARDS_MARKET = "Rushing Yards"' in source
    assert "if market == RUSHING_YARDS_MARKET:" in source
    assert "return _PRIOR_RENDER_NFL(market)" in source
    assert "prior._render_nfl_v104 = _render_nfl_v105" in source
    assert "prior._render_nfl_v104 = original_handler" in source


def test_app_boots_v105_and_preserves_v104_heartbeat():
    source = _source("app.py")
    assert "from streamlit_memory_lazy_router_v105 import record_bootstrap_import_ms, render_app" in source
    assert 'FROZEN_V104_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V104_NFL_RUSHING_YARDS_PAGE_STEP5_PROJECTION_RECIPE_2026-09-12"' in source
    assert 'DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V105_NFL_RUSHING_YARDS_PAGE_STEP6_SUPPORT_CONCERNS_2026-09-12"' in source


def test_frozen_v8_and_v104_remain_step5_owners():
    v8 = _source("nfl_rushing_yards_hub_v8.py")
    v104 = _source("streamlit_memory_lazy_router_v104.py")
    assert 'FROZEN_PRIOR = "nfl_rushing_yards_hub_v7"' in v8
    assert "PAGE_BUILD_STEP = 5" in v8
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v103"' in v104
    assert 'ACTIVE_RUSHING_YARDS_HUB = "nfl_rushing_yards_hub_v8"' in v104


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
