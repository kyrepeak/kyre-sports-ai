from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_v6_is_additive_over_frozen_v5():
    source = _source("nfl_rushing_yards_hub_v6.py")
    assert "import nfl_rushing_yards_hub_v5 as prior" in source
    assert 'FROZEN_PRIOR = "nfl_rushing_yards_hub_v5"' in source
    assert "PAGE_BUILD_STEP = 3" in source
    assert "PAGE_BUILD_TOTAL = 6" in source
    assert "_ORIGINAL_COMPACT_PLAYER_CARD_V5 = prior._compact_player_card_v5" in source
    assert "prior._compact_player_card_v5 = _compact_player_card_v6" in source
    assert "prior._compact_player_card_v5 = original_card" in source


def test_step3_profile_uses_exact_identity_only():
    source = _source("nfl_rushing_yards_hub_v6.py")
    assert "athlete_id.isdigit()" in source
    assert 'team.get("official_team_id")' in source
    assert 'player.get("official_athlete_id")' in source
    assert 'player.get("official_team_id")' in source
    assert "exact ESPN athlete" in source
    assert "player_name" not in source


def test_step3_profile_contains_verified_workload_efficiency_fields():
    source = _source("nfl_rushing_yards_hub_v6.py")
    for field in (
        'player.get("carries")',
        'player.get("rushing_yards")',
        'player.get("carries_per_game")',
        'player.get("rushing_yards_per_game")',
        'player.get("yards_per_carry")',
        'player.get("rushing_touchdowns")',
        'player.get("sample_games")',
    ):
        assert field in source
    for label in (
        "Carries",
        "Rush Yards",
        "Carries / Game",
        "Rush Yards / Game",
        "Yards / Carry",
        "Rush TDs",
        "Sample Games",
    ):
        assert label in source
    assert 'aria-label="Rusher workload and efficiency profile"' in source


def test_step3_does_not_rebuild_projection_or_market_math():
    source = _source("nfl_rushing_yards_hub_v6.py")
    assert "build_event_projections(" not in source
    assert "market_for_athlete(" not in source
    assert "weighted_blend(" not in source
    assert "EFFICIENCY_WEIGHTS" not in source
    assert "nfl_passing_yards" not in source


def test_v102_advances_only_rushing_yards_to_v6():
    source = _source("streamlit_memory_lazy_router_v102.py")
    assert "import streamlit_memory_lazy_router_v101 as prior" in source
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v101"' in source
    assert 'ACTIVE_RUSHING_YARDS_HUB = "nfl_rushing_yards_hub_v6"' in source
    assert 'RUSHING_YARDS_MARKET = "Rushing Yards"' in source
    assert "if market == RUSHING_YARDS_MARKET:" in source
    assert "return _PRIOR_RENDER_NFL(market)" in source
    assert "prior._render_nfl_v101 = _render_nfl_v102" in source
    assert "prior._render_nfl_v101 = original_handler" in source


def test_app_boots_v102_and_preserves_v101_heartbeat():
    source = _source("app.py")
    assert "from streamlit_memory_lazy_router_v102 import record_bootstrap_import_ms, render_app" in source
    assert 'FROZEN_V101_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V101_NFL_RUSHING_YARDS_PAGE_STEP2_SUMMARY_METRICS_2026-09-12"' in source
    assert 'DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V102_NFL_RUSHING_YARDS_PAGE_STEP3_WORKLOAD_EFFICIENCY_2026-09-12"' in source


def test_frozen_v5_and_v101_remain_page_step2_owners():
    v5 = _source("nfl_rushing_yards_hub_v5.py")
    v101 = _source("streamlit_memory_lazy_router_v101.py")
    assert 'FROZEN_PRIOR = "nfl_rushing_yards_hub_v4"' in v5
    assert "PAGE_BUILD_STEP = 2" in v5
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v100"' in v101
    assert 'ACTIVE_RUSHING_YARDS_HUB = "nfl_rushing_yards_hub_v5"' in v101


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
