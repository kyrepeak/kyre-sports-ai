from __future__ import annotations

import importlib


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
        "market": {
            "status": "VERIFIED",
            "sportsbook": "FanDuel",
            "line": 241.5,
            "over_odds": -114,
            "under_odds": -114,
            "timestamp": "2026-10-22T20:30:00Z",
        },
        "projection_yards": 252.8,
        "edge_yards": 11.3,
        "over_probability": 0.61,
        "under_probability": 0.39,
        "favored_side": "OVER",
        "confidence": "MEDIUM",
        "detail": {
            "profile": {
                "games": 6,
                "passing_yards_per_game": 248.3,
                "attempts_per_game": 34.2,
                "completion_pct": 66.1,
                "yards_per_attempt": 7.26,
                "pass_tds": 11,
                "interceptions": 4,
                "recent_games": [],
            },
            "season_game_log": [],
            "context_projection": {
                "context_projection_yards": 252.8,
                "pressure_adjustment_yards": 1.4,
            },
            "distribution": {"confidence": "MEDIUM", "sigma_yards": 45.6},
            "market": {
                "ready": True,
                "sportsbook": "FanDuel",
                "line": 241.5,
                "over_odds": -114,
                "under_odds": -114,
                "source_timestamp": "2026-10-22T20:30:00Z",
                "books": [
                    {
                        "sportsbook": "FanDuel",
                        "line": 241.5,
                        "over_odds": -114,
                        "under_odds": -114,
                        "source_timestamp": "2026-10-22T20:30:00Z",
                    }
                ],
                "line_movement": {"ready": False, "sportsbook": "FanDuel"},
            },
            "market_evaluation": {
                "ready": True,
                "lean": "OVER",
                "grade": "MEDIUM",
                "model_over_probability": 0.61,
                "model_under_probability": 0.39,
            },
            "pass_defense": {
                "rank": 26,
                "grade": "FAVORABLE",
                "pass_yards_allowed_per_game": 256.0,
                "passing_attempts_allowed_per_game": 36.5,
                "completion_pct_allowed": 60.7,
                "yards_per_attempt_allowed": 7.01,
                "recent3_pass_yards_allowed": 211.8,
                "sack_rate_generated": 6.4,
            },
            "qb_vs_team_history": {
                "available": True,
                "games": 2,
                "avg_passing_yards": 233.5,
                "avg_attempts": 33.0,
                "completion_pct": 64.0,
                "games_detail": [
                    {
                        "season": 2024,
                        "date": "2024-10-06",
                        "opponent": "NE",
                        "attempts": 35,
                        "completions": 23,
                        "passing_yards": 247.0,
                        "pass_tds": 2,
                        "interceptions": 1,
                    }
                ],
            },
            "availability": {
                "verified": False,
                "status": "CHECK",
                "reason": "Official injury/availability data not verified for this request",
            },
            "game_environment": {
                "verified": True,
                "venue": "Ford Field",
                "roof": "dome",
                "surface": "sportturf",
                "temperature_f": None,
                "wind_mph": None,
                "rest_days": 7,
                "source": "NFLverse schedule",
            },
            "page1_decision_support": {
                "thesis": {
                    "ready": True,
                    "side": "OVER",
                    "line": 241.5,
                    "strength": "MODERATE",
                    "narrative": "Verified evidence favors the Over.",
                    "factors": [
                        {"label": "Projection edge", "positive": True, "detail": "+11.3 yards versus the exact market line"},
                        {"label": "Recent hit rate", "positive": True, "detail": "4 of last 5 games"},
                    ],
                },
                "risk_flags": ["Availability verification pending"],
            },
        },
    }


def test_page1_full_analysis_link_uses_canonical_universal_runtime_route():
    page1 = importlib.import_module("nfl_passing_yards_simple_qb_grid_v1")
    html = page1.build_qb_card_html(_card())
    assert "sport=nfl" in html
    assert "market=passing-yards" in html
    assert "player_id=kyre%3Anfl%3Aplayer%3A00-0039000" in html
    assert "game_id=kyre%3Anfl%3Agame%3A2026_07_NE_CHI" in html
    assert "date=2026-10-22" in html
    assert "ks_py_detail" not in html


def test_page2_cleanup_successor_has_compact_hierarchy_without_duplicate_market_section():
    page2 = importlib.import_module("nfl_passing_yards_page2_command_center_v2")
    html = page2.build_page2_html(_card())
    assert "QB ANALYSIS COMMAND CENTER" in html
    assert "RECENT PERFORMANCE" in html
    assert "QB FORM VS OPPONENT DEFENSE" in html
    assert "WHY KYRE LEANS" in html
    assert "RISK PANEL" in html
    assert "FINAL DECISION" in html
    assert "MARKET & MODEL" not in html
    assert html.count("FanDuel") >= 1


def test_page2_verified_matchup_history_rows_are_visible_for_every_player_payload():
    page2 = importlib.import_module("nfl_passing_yards_page2_command_center_v2")
    html = page2.build_page2_html(_card())
    assert "QB VS DEFENSE HISTORY" in html
    assert "2024-10-06" in html
    assert "247" in html
    assert "NE" in html


def test_page2_semantic_matchup_empty_state_never_uses_generic_unavailable():
    page2 = importlib.import_module("nfl_passing_yards_page2_command_center_v2")
    detail = {"qb_vs_team_history": {"available": False, "state": "FIRST_CAREER_MATCHUP"}}
    html = page2._history(detail)
    assert "First career matchup" in html
    assert "NOT AVAILABLE" not in html


def test_page2_indoor_weather_is_not_applicable_instead_of_missing():
    page2 = importlib.import_module("nfl_passing_yards_page2_command_center_v2")
    html = page2._conditions(_card()["detail"])
    assert "INDOOR" in html.upper()
    assert "NOT APPLICABLE" in html.upper()
    assert "NOT AVAILABLE" not in html.upper()


def test_page2_responsive_values_do_not_force_word_breaks():
    page2 = importlib.import_module("nfl_passing_yards_page2_command_center_v2")
    css = page2.CSS
    assert "overflow-wrap:anywhere" not in css.replace(" ", "").lower()
    assert "word-break:break-all" not in css.replace(" ", "").lower()
    assert "min-width:0" in css.replace(" ", "").lower()
