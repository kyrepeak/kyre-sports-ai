from __future__ import annotations

from importlib import import_module
from pathlib import Path


def test_projection_formula_stays_market_blind():
    model = import_module("sports_api.projections.nfl_rushing_yards_projection_v1")
    result = model.build_projection(
        player={"carries_per_game": 16.0, "yards_per_carry": 4.5},
        opponent={"rush_attempts_allowed_per_game": 30.0, "yards_per_carry_allowed": 4.8},
    )
    assert result["ready"] is True
    assert round(result["projection_yards"], 1) == 69.2
    assert result["sportsbook_influence"] == 0.0
    assert "market" not in result["inputs"]


def test_semantic_market_failure_never_fabricates_zero_or_false_not_posted():
    slate = import_module("sports_api.api.nfl_rushing_yards_slate_v1")
    state = slate.market_state(None)
    assert state["status"] == "DATA_UNAVAILABLE"
    assert state["diagnostic_state"] == "MARKET_MAPPING_FAILURE"
    assert state["line"] is None
    assert state["sportsbook"] is None
    assert state["status"] != "MARKET_NOT_POSTED"


def test_verified_absence_is_the_only_path_to_market_not_posted():
    truth = import_module("sports_api.nfl_rushing_yards_data_truth_v1")
    state = truth.market_state_from_bundle(
        {"state": "VERIFIED_NOT_POSTED", "provider": "FanDuel", "observations": [], "reason": "verified absence"},
        player={"player_name": "Lead Back", "team_abbr": "ATL"},
    )
    assert state["status"] == "MARKET_NOT_POSTED"
    assert state["state"] == "VERIFIED_NO_STANDARD_MARKET"
    assert state["diagnostic_state"] == "VERIFIED_NO_STANDARD_MARKET"
    assert state["verified_absence"] is True
    assert state["line"] is None


def test_page2_contains_deep_rushing_sections_and_semantic_empty_states():
    page = import_module("nfl_rushing_yards_professional_v1")
    detail = {
        "player_name": "Lead Back",
        "role": "RB1",
        "team_abbr": "ATL",
        "opponent_abbr": "CAR",
        "profile": {"carries_per_game": 16.0, "rushing_yards_per_game": 72.0, "yards_per_carry": 4.5, "recent_games": []},
        "opponent_run_defense": {"rush_yards_allowed_per_game": 130.0, "yards_per_carry_allowed": 4.6, "rank": 27, "grade": "FAVORABLE"},
        "matchup_history": {"status": "FIRST_CAREER_MATCHUP", "games_detail": []},
        "market": {"status": "MARKET_NOT_POSTED", "state": "VERIFIED_NO_STANDARD_MARKET", "diagnostic_state": "VERIFIED_NO_STANDARD_MARKET", "line": None},
        "availability": {"status": "NO_INJURY_DESIGNATION"},
        "environment": {"status": "PREGAME"},
    }
    html = page.build_rushing_detail_html(detail)
    for label in ("WORKLOAD", "RECENT FORM", "OPPONENT RUN DEFENSE", "MATCHUP HISTORY", "MARKET INTELLIGENCE", "GAME ENVIRONMENT", "AVAILABILITY", "WHY KYRE LEANS"):
        assert label in html
    assert "First career matchup" in html
    assert "Market not posted yet" in html
    assert "Unavailable" not in html
    assert "N/A" not in html


def test_new_production_path_contains_no_banned_provider_dependency():
    production_files = [
        "sports_api/api/nfl_rushing_yards_slate_v1.py",
        "sports_api/nfl_rushing_yards_fastpath_v1.py",
        "sports_api/nfl_rushing_yards_data_truth_v1.py",
        "sports_api/collectors/nfl_fanduel_rushing_yards_nflverse_v1.py",
        "nfl_rushing_yards_simple_rb_grid_v1.py",
    ]
    for relative in production_files:
        source = Path(relative).read_text(encoding="utf-8").lower()
        assert "espn.com" not in source
        assert "site.api.espn" not in source
        assert "sgo" not in source
        assert "espn bet" not in source
