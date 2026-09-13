from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_step3_page_is_additive_over_frozen_v1():
    source = _source("nfl_rushing_yards_hub_v2.py")
    assert "import nfl_rushing_yards_hub_v1 as prior" in source
    assert 'FROZEN_PRIOR = "nfl_rushing_yards_hub_v1"' in source
    assert "_ORIGINAL_CONTEXT_BOARD = prior._render_context_board" in source
    assert "prior._render_context_board = _render_context_board_v2" in source
    assert "prior._render_context_board = original_context_board" in source


def test_step3_page_uses_isolated_projection_engine_after_context():
    source = _source("nfl_rushing_yards_hub_v2.py")
    assert "import nfl_rushing_yards_projection_v1 as projection" in source
    assert "context = prior._load_rushing_context(event_id)" in source
    assert 'context.get("ready") is not True' in source
    assert 'context.get("data_available") is not True' in source
    assert "projection.build_event_projections(context)" in source
    assert "Market-Blind Baseline Projection" in source
    assert "sportsbook influence 0.0%" in source


def test_step3_does_not_import_or_modify_passing_yards():
    source = _source("nfl_rushing_yards_hub_v2.py")
    assert "nfl_passing_yards" not in source
    normalized = " ".join(source.split())
    assert "Passing Yards is not imported or modified" in normalized


def test_step4_features_remain_locked_on_page():
    source = _source("nfl_rushing_yards_hub_v2.py")
    required_locked_phrases = (
        "probability_enabled",
        "monte_carlo_enabled",
        "market_enabled",
        "fair_line_enabled",
        "ev_enabled",
        "ranking_enabled",
        "recommendation_enabled",
        "stake_sizing_enabled",
        "wager_actions",
    )
    engine = _source("nfl_rushing_yards_projection_v1.py")
    for phrase in required_locked_phrases:
        assert phrase in engine
    assert "LIVE MARKET + FINAL GRADE" in _source("nfl_rushing_yards_hub_v1.py")
    assert "Step 4" in source


def test_router_v98_advances_only_rushing_target_to_v2():
    source = _source("streamlit_memory_lazy_router_v98.py")
    assert 'ACTIVE_RUSHING_YARDS_HUB = "nfl_rushing_yards_hub_v2"' in source
    assert 'RUSHING_YARDS_MARKET = "Rushing Yards"' in source
    assert "if market == RUSHING_YARDS_MARKET:" in source
    assert "return _PRIOR_RENDER_NFL(market)" in source
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v97"' in source


def test_frozen_v1_still_owns_steps_1_and_2_only():
    source = _source("nfl_rushing_yards_hub_v1.py")
    assert "Ground Game Lab Steps 1-2" in source
    assert "STEP 2 PLAYER + MATCHUP DATA" in source
    assert "2 OF 4 • DATA LIVE" in source
    assert "3 • PROJECTION ENGINE" in source
