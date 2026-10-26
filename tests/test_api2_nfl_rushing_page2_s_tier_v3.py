from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _detail(*, verified_market: bool = True) -> dict:
    market = {
        "status": "VERIFIED" if verified_market else "MARKET_NOT_POSTED",
        "line": 64.5 if verified_market else None,
        "current_line": 64.5 if verified_market else None,
        "over_odds": -113 if verified_market else None,
        "under_odds": -113 if verified_market else None,
        "sportsbook": "FanDuel" if verified_market else "",
        "opening_line_status": "OPENING_LINE_NOT_CAPTURED",
        "movement_status": "MOVEMENT_HISTORY_NOT_CAPTURED",
    }
    recent_rows = [
        {"game_date": "2026-10-18", "opponent_abbr": "GB", "rushing_yards": 41, "attempts": 13},
        {"game_date": "2026-10-08", "opponent_abbr": "TB", "rushing_yards": 45, "attempts": 12},
        {"game_date": "2026-10-04", "opponent_abbr": "HOU", "rushing_yards": 62, "attempts": 19},
        {"game_date": "2026-09-27", "opponent_abbr": "BAL", "rushing_yards": 98, "attempts": 19},
        {"game_date": "2026-09-20", "opponent_abbr": "WAS", "rushing_yards": 30, "attempts": 12},
        {"game_date": "2026-09-13", "opponent_abbr": "NYG", "rushing_yards": 41, "attempts": 12},
    ]
    return {
        "player_name": "Javonte Williams",
        "player_headshot": "https://example.com/javonte.png",
        "team_logo": "https://example.com/dal.png",
        "team_abbr": "DAL",
        "opponent_abbr": "PHI",
        "role": "RB1",
        "home_away": "AWAY",
        "kickoff_utc": "2026-10-27T00:15:00Z",
        "profile": {"recent_games": recent_rows},
        "market": market,
        "market_intelligence": market,
        "projection": {"projection": 54.0, "expected_carries": 14.2, "expected_ypc": 3.81},
        "decision": {
            "side": "UNDER" if verified_market else "WAIT",
            "edge": -10.5 if verified_market else None,
            "probability": 0.71 if verified_market else None,
            "confidence": 0.71 if verified_market else None,
        },
        "workload_intelligence": {
            "status": "VERIFIED_DERIVED",
            "season_carries_per_game": 14.2,
            "l3_carries_per_game": 14.0,
            "l5_carries_per_game": 14.6,
            "team_rush_attempt_share": 0.70,
            "workload_trend": "STABLE",
            "red_zone_carries": 24,
            "goal_line_carries": 15,
            "fourth_quarter_carries": 14,
            "leading_carries": 13,
            "trailing_carries": 51,
        },
        "recent_form": {
            "status": "VERIFIED_DERIVED",
            "sample_games": 6,
            "season_average": 52.8,
            "l3_average": 49.3,
            "l5_average": 55.2,
            "median": 43.0,
            "floor": 30,
            "ceiling": 98,
            "current_line_hit_rate": 1 / 6 if verified_market else None,
            "hit_rate_status": "VERIFIED" if verified_market else "MARKET_NOT_POSTED",
            "games_detail": recent_rows,
        },
        "opponent_run_defense": {
            "team_abbr": "PHI",
            "rush_yards_allowed_per_game": 119.3,
            "rush_attempts_allowed_per_game": 30.2,
            "yards_per_carry_allowed": 3.96,
            "explosive_run_rate_allowed": 0.09,
            "stuff_rate": 0.19,
            "success_rate_allowed": 0.44,
            "rush_epa_allowed_per_attempt": -0.039,
            "rank": 21,
            "grade": "FAVORABLE",
        },
        "game_script": {
            "status": "VERIFIED_DERIVED",
            "team_rush_attempts_per_game": 20.3,
            "leading_share": 0.15,
            "trailing_share": 0.60,
            "fourth_quarter_share": 0.16,
            "spread_status": "GAME_SPREAD_NOT_VERIFIED",
            "total_status": "GAME_TOTAL_NOT_VERIFIED",
            "weather_status": "WEATHER_VERIFICATION_PENDING",
            "game_state": "PREGAME",
        },
        "matchup_history": {
            "status": "VERIFIED",
            "games_detail": [
                {"game_date": "2025-11-02", "opponent_abbr": "PHI", "rushing_yards": 87, "attempts": 20},
                {"game_date": "2024-10-20", "opponent_abbr": "PHI", "rushing_yards": 54, "attempts": 15},
            ],
        },
        "comparable_matchups": {
            "status": "VERIFIED",
            "target_grade": "FAVORABLE",
            "games": 1,
            "average_rushing_yards": 41,
            "games_detail": [
                {"game_date": "2026-09-13", "opponent_abbr": "NYG", "rushing_yards": 41, "attempts": 12}
            ],
        },
        "advanced_efficiency": {
            "status": "VERIFIED_DERIVED",
            "explosive_run_rate": 0.06,
            "stuff_rate": 0.19,
            "success_rate": 0.46,
            "rush_epa_per_attempt": 0.022,
        },
        "personnel": {"status": "PERSONNEL_VERIFICATION_PENDING", "display": "Personnel verification pending"},
        "final_read": {
            "summary": "Kyre projects a controlled workload against a favorable run-defense profile.",
            "supporting_factors": ["Stable workload", "Favorable opponent run-defense grade"],
            "risk_factors": ["Trailing game script can suppress rushing volume"],
            "unresolved": ["Personnel verification is still pending"],
        },
        "source_lineage": {
            "identity": "nflverse weekly roster",
            "workload": "nflverse play-by-play",
            "market": "semantic market state",
            "projection": "NFL RUSHING YARDS PROJECTION V2",
        },
    }


def test_v1_activates_v3_successor_and_v2_remains_preserved() -> None:
    source = (ROOT / "nfl_rushing_yards_professional_v1.py").read_text(encoding="utf-8")
    v2 = (ROOT / "nfl_rushing_yards_professional_v2.py").read_text(encoding="utf-8")
    assert "from nfl_rushing_yards_professional_v3 import" in source
    assert "from nfl_rushing_yards_professional_v2 import" not in source
    assert 'MODEL_VERSION = "NFL RUSHING YARDS PAGE 2 COMMAND CENTER V2"' in v2


def test_v3_renders_complete_s_tier_information_architecture() -> None:
    import nfl_rushing_yards_professional_v3 as page

    html = page.build_rushing_detail_html(_detail())
    for heading in (
        "DECISION COCKPIT",
        "KYRE INSIGHTS",
        "MARKET LAB",
        "RECENT PERFORMANCE",
        "HIT RATE MATRIX",
        "WORKLOAD & ROLE",
        "OPPONENT RUN DEFENSE",
        "TRENCH & PERSONNEL",
        "GAME ENVIRONMENT",
        "AVAILABILITY & PERSONNEL",
        "MATCHUP + COMPARABLE HISTORY",
        "ADVANCED EFFICIENCY",
        "FULL GAME LOG",
        "FINAL KYRE READ",
        "DATA & SOURCES",
    ):
        assert heading in html
    assert "<details" in html
    assert "kry3chart" in html
    assert "kry3tabs" in html


def test_verified_market_drives_decision_chart_and_hit_rates() -> None:
    import nfl_rushing_yards_professional_v3 as page

    html = page.build_rushing_detail_html(_detail(verified_market=True))
    assert "64.5" in html
    assert "-113" in html
    assert "UNDER" in html
    assert "-10.5" in html
    assert "71%" in html
    assert "CURRENT LINE" in html
    assert "1/6" in html
    assert "FanDuel" in html


def test_unverified_market_stays_fail_closed_without_fake_decision_values() -> None:
    import nfl_rushing_yards_professional_v3 as page

    html = page.build_rushing_detail_html(_detail(verified_market=False))
    assert "WAIT" in html
    assert "Market not posted yet" in html
    assert "Pending verification" in html
    assert "-10.5" not in html
    assert "71%" not in html
    assert "1/6" not in html


def test_mobile_css_wraps_values_and_sources_are_collapsed() -> None:
    import nfl_rushing_yards_professional_v3 as page

    assert "text-overflow:ellipsis" not in page.CSS
    assert "white-space:nowrap" not in page.CSS
    assert "overflow-wrap:anywhere" in page.CSS
    html = page.build_rushing_detail_html(_detail())
    assert '<details class="kry3sources"' in html
    assert "Identity: nflverse weekly roster" in html


def test_renderer_has_no_direct_banned_provider_dependency() -> None:
    source = (ROOT / "nfl_rushing_yards_professional_v3.py").read_text(encoding="utf-8").upper()
    for banned in ("ESPN", "ESPN BET", "SGO"):
        assert banned not in source
    assert "REQUESTS.GET" not in source
    assert "HTTPX" not in source
