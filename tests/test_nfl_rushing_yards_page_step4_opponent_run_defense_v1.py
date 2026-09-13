from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_v7_is_additive_over_frozen_v6():
    source = _source("nfl_rushing_yards_hub_v7.py")
    assert "import nfl_rushing_yards_hub_v6 as prior" in source
    assert 'FROZEN_PRIOR = "nfl_rushing_yards_hub_v6"' in source
    assert "PAGE_BUILD_STEP = 4" in source
    assert "PAGE_BUILD_TOTAL = 6" in source
    assert "_ORIGINAL_COMPACT_PLAYER_CARD_V6 = prior._compact_player_card_v6" in source
    assert "prior._compact_player_card_v6 = _compact_player_card_v7" in source
    assert "prior._compact_player_card_v6 = original_card" in source


def test_step4_uses_exact_opponent_team_identity_only():
    source = _source("nfl_rushing_yards_hub_v7.py")
    assert 'team.get("official_team_id")' in source
    assert 'team.get("opponent_official_team_id")' in source
    assert 'opponent.get("official_team_id")' in source
    assert 'run_front.get("official_team_id")' in source
    assert "rendered_opponent_id != opponent_id" in source
    assert 'run_front.get("data_available") is not True' in source
    assert "fuzzy" not in source.lower()


def test_step4_displays_only_certified_run_front_metrics():
    source = _source("nfl_rushing_yards_hub_v7.py")
    for field in (
        'run_front.get("rush_attempts_allowed_per_game")',
        'run_front.get("rush_yards_allowed_per_game")',
        'run_front.get("yards_per_carry_allowed")',
        'run_front.get("rushing_touchdowns_allowed_per_game")',
    ):
        assert field in source
    for label in (
        "Rush Att Allowed / Game",
        "Rush Yards Allowed / Game",
        "Yards / Carry Allowed",
        "Rush TDs Allowed / Game",
    ):
        assert label in source
    assert 'aria-label="Opponent run defense matchup"' in source
    assert "Opponent Run Defense Matchup" in source


def test_step4_does_not_add_matchup_grades_or_model_math():
    source = _source("nfl_rushing_yards_hub_v7.py")
    assert "build_event_projections(" not in source
    assert "market_for_athlete(" not in source
    assert "weighted_blend(" not in source
    assert "EFFICIENCY_WEIGHTS" not in source
    assert "favorable" not in source.lower()
    assert "tough" not in source.lower()
    assert "nfl_passing_yards" not in source


def test_v103_advances_only_rushing_yards_to_v7():
    source = _source("streamlit_memory_lazy_router_v103.py")
    assert "import streamlit_memory_lazy_router_v102 as prior" in source
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v102"' in source
    assert 'ACTIVE_RUSHING_YARDS_HUB = "nfl_rushing_yards_hub_v7"' in source
    assert 'RUSHING_YARDS_MARKET = "Rushing Yards"' in source
    assert "if market == RUSHING_YARDS_MARKET:" in source
    assert "return _PRIOR_RENDER_NFL(market)" in source
    assert "prior._render_nfl_v102 = _render_nfl_v103" in source
    assert "prior._render_nfl_v102 = original_handler" in source


def test_app_boots_v103_and_preserves_v102_heartbeat():
    source = _source("app.py")
    assert "from streamlit_memory_lazy_router_v103 import record_bootstrap_import_ms, render_app" in source
    assert 'FROZEN_V102_DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V102_NFL_RUSHING_YARDS_PAGE_STEP3_WORKLOAD_EFFICIENCY_2026-09-12"' in source
    assert 'DEPLOYMENT_HEARTBEAT = "STREAMLIT_MAIN_V103_NFL_RUSHING_YARDS_PAGE_STEP4_OPPONENT_RUN_DEFENSE_2026-09-12"' in source


def test_frozen_v6_and_v102_remain_page_step3_owners():
    v6 = _source("nfl_rushing_yards_hub_v6.py")
    v102 = _source("streamlit_memory_lazy_router_v102.py")
    assert 'FROZEN_PRIOR = "nfl_rushing_yards_hub_v5"' in v6
    assert "PAGE_BUILD_STEP = 3" in v6
    assert 'FROZEN_ROUTER = "streamlit_memory_lazy_router_v101"' in v102
    assert 'ACTIVE_RUSHING_YARDS_HUB = "nfl_rushing_yards_hub_v6"' in v102


def test_context_contract_still_requires_exact_run_front_identity():
    source = _source("nfl_rushing_yards_context_api_v1.py")
    assert 'if _safe(raw.get("official_team_id")) != opponent_id:' in source
    assert '"rush_attempts_allowed_per_game"' in source
    assert '"rush_yards_allowed_per_game"' in source
    assert '"yards_per_carry_allowed"' in source
    assert '"rushing_touchdowns_allowed_per_game"' in source


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
