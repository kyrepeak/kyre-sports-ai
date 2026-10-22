from __future__ import annotations

import importlib
from pathlib import Path


def _card() -> dict:
    return {
        "player_id": "kyre:nfl:player:00-0039000",
        "qb_name": "Caleb Williams",
        "team_abbr": "CHI",
        "team_name": "Chicago Bears",
        "opponent_abbr": "NE",
        "game_id": "kyre:nfl:game:2026_07_NE_CHI",
        "game_date": "2026-10-22",
        "game_time": "20:15",
        "home_away": "HOME",
        "headshot_url": "https://example.com/caleb.png",
        "team_logo_url": "https://example.com/chi.png",
        "opponent_logo_url": "https://example.com/ne.png",
        "market": {
            "status": "VERIFIED",
            "sportsbook": "FanDuel",
            "market": "Passing Yards",
            "line": 241.5,
            "over_odds": -114,
            "under_odds": -114,
            "timestamp": "2026-10-22T20:30:00Z",
        },
        "projection_yards": 239.7,
        "edge_yards": -1.8,
        "over_probability": 0.49,
        "under_probability": 0.51,
        "favored_side": "UNDER",
        "confidence": "MEDIUM",
        "detail": {
            "player_id": "kyre:nfl:player:00-0039000",
            "qb_name": "Caleb Williams",
            "team_abbr": "CHI",
            "team_name": "Chicago Bears",
            "opponent_abbr": "NE",
            "opponent_team_id": "kyre:nfl:team:NE",
            "side": "home",
            "identity_visuals": {
                "identity_verified": True,
                "headshot_url": "https://example.com/caleb.png",
                "team_logo_url": "https://example.com/chi.png",
                "opponent_logo_url": "https://example.com/ne.png",
            },
            "profile": {
                "games": 6,
                "passing_yards_per_game": 248.3,
                "attempts_per_game": 34.2,
                "completion_pct": 66.1,
                "yards_per_attempt": 7.26,
                "pass_tds": 11,
                "interceptions": 4,
                "recent_games": [
                    {"game_id": "g1", "opponent": "GB", "attempts": 38, "completions": 25, "passing_yards": 272.0, "pass_tds": 2, "interceptions": 1},
                    {"game_id": "g2", "opponent": "MIN", "attempts": 32, "completions": 22, "passing_yards": 221.0, "pass_tds": 1, "interceptions": 0},
                    {"game_id": "g3", "opponent": "DET", "attempts": 36, "completions": 24, "passing_yards": 259.0, "pass_tds": 2, "interceptions": 1},
                    {"game_id": "g4", "opponent": "NYG", "attempts": 29, "completions": 20, "passing_yards": 205.0, "pass_tds": 1, "interceptions": 0},
                    {"game_id": "g5", "opponent": "DAL", "attempts": 41, "completions": 27, "passing_yards": 286.0, "pass_tds": 3, "interceptions": 1},
                ],
            },
            "context_projection": {
                "context_projection_yards": 239.7,
                "pressure_adjustment_yards": -4.2,
            },
            "distribution": {"confidence": "MEDIUM", "sigma_yards": 58.0},
            "market": {
                "ready": True,
                "sportsbook": "FanDuel",
                "line": 241.5,
                "over_odds": -114,
                "under_odds": -114,
                "source_timestamp": "2026-10-22T20:30:00Z",
                "books": [
                    {"sportsbook": "FanDuel", "line": 241.5, "over_odds": -114, "under_odds": -114, "source_timestamp": "2026-10-22T20:30:00Z"},
                    {"sportsbook": "DraftKings", "line": 242.5, "over_odds": -110, "under_odds": -110, "source_timestamp": "2026-10-22T20:29:00Z"},
                ],
                "line_movement": {"ready": True, "sportsbook": "FanDuel", "open_line": 239.5, "current_line": 241.5, "delta": 2.0},
            },
            "market_evaluation": {
                "ready": True,
                "lean": "UNDER",
                "grade": "MEDIUM",
                "model_over_probability": 0.49,
                "model_under_probability": 0.51,
            },
            "pass_defense": {
                "rank": 9,
                "grade": "MEDIUM",
                "pass_yards_allowed_per_game": 214.8,
                "passing_attempts_allowed_per_game": 31.4,
                "completion_pct_allowed": 63.2,
                "yards_per_attempt_allowed": 6.84,
                "recent3_pass_yards_allowed": 202.3,
                "sack_rate_generated": 7.1,
            },
            "qb_vs_team_history": {
                "available": True,
                "games": 2,
                "avg_passing_yards": 233.5,
                "avg_attempts": 33.0,
                "completion_pct": 64.0,
                "games_detail": [
                    {"opponent": "NE", "attempts": 35, "completions": 23, "passing_yards": 247.0, "pass_tds": 2, "interceptions": 1},
                    {"opponent": "NE", "attempts": 31, "completions": 20, "passing_yards": 220.0, "pass_tds": 1, "interceptions": 0},
                ],
            },
            "availability": {"verified": False, "status": "CHECK", "reason": "Official injury/availability data not verified for this request"},
            "game_environment": {"verified": True, "venue": "Soldier Field", "roof": "outdoors", "surface": "grass", "temperature_f": 52.0, "wind_mph": 11.0, "weather": "VERIFIED CONDITIONS", "rest_days": 7, "source": "NFLverse schedule"},
            "page1_decision_support": {
                "thesis": {
                    "ready": True,
                    "side": "UNDER",
                    "line": 241.5,
                    "strength": "LEAN",
                    "narrative": "Verified evidence supports a cautious Under lean.",
                    "factors": [
                        {"label": "Projection edge", "positive": True, "detail": "+1.8 yards toward the Under"},
                        {"label": "Pass defense", "positive": True, "detail": "opponent ranks 9 in pass-yards defense"},
                    ],
                },
                "risk_flags": ["Availability verification pending"],
            },
        },
    }


def test_page2_builds_complete_analysis_command_center():
    page2 = importlib.import_module("nfl_passing_yards_page2_command_center_v1")
    html = page2.build_page2_html(_card())

    for label in (
        "QB ANALYSIS COMMAND CENTER",
        "MARKET & MODEL",
        "RECENT GAME LOG",
        "HIT RATE LAB",
        "MATCHUP & PASS DEFENSE",
        "QB VS DEFENSE HISTORY",
        "LINE MOVEMENT & SPORTSBOOKS",
        "VOLUME & EFFICIENCY",
        "GAME CONDITIONS",
        "AVAILABILITY",
        "WHY KYRE LEANS",
        "WHAT COULD MAKE THIS BET LOSE?",
        "FINAL DECISION",
    ):
        assert label in html

    assert "Caleb Williams" in html
    assert "241.5" in html
    assert "239.7" in html
    assert "FanDuel" in html
    assert "DraftKings" in html
    assert "272" in html and "221" in html and "259" in html
    assert "Soldier Field" in html
    assert "Availability verification pending" in html


def test_page2_preserves_independent_sportsbook_lines_and_current_book_movement():
    page2 = importlib.import_module("nfl_passing_yards_page2_command_center_v1")
    html = page2.build_page2_html(_card())

    assert "FanDuel" in html and "241.5" in html
    assert "DraftKings" in html and "242.5" in html
    assert "OPEN 239.5" in html
    assert "CURRENT 241.5" in html
    assert "+2.0" in html
    assert "AVERAGE" not in html.upper()


def test_page2_uses_explicit_unavailable_states_instead_of_fake_zeroes():
    page2 = importlib.import_module("nfl_passing_yards_page2_command_center_v1")
    card = _card()
    detail = card["detail"]
    detail["availability"] = {"verified": False, "status": "CHECK", "reason": "Verified injury feed unavailable"}
    detail["game_environment"] = {"verified": False, "reason": "Verified game-condition feed unavailable"}
    detail["qb_vs_team_history"] = {"available": False, "games": 0, "avg_passing_yards": None, "message": "No verified prior matchup history"}
    detail["market"]["line_movement"] = {"ready": False, "sportsbook": "FanDuel", "open_line": None, "current_line": 241.5, "delta": None}

    html = page2.build_page2_html(card)

    assert "NOT AVAILABLE" in html
    assert "Verified injury feed unavailable" in html
    assert "Verified game-condition feed unavailable" in html
    assert "No verified prior matchup history" in html
    assert "OPEN 0" not in html


def test_page2_source_policy_has_no_sgo_or_espn_dependencies():
    source = Path("nfl_passing_yards_page2_command_center_v1.py").read_text(encoding="utf-8").lower()
    assert "sportsgameodds" not in source
    assert "sgo" not in source
    assert "espn" not in source


def test_existing_detail_route_hands_selected_card_to_command_center():
    source = Path("nfl_passing_yards_simple_qb_grid_v1.py").read_text(encoding="utf-8")
    assert "nfl_passing_yards_page2_command_center_v1" in source
    assert "render_page2" in source
