from __future__ import annotations

import inspect
from pathlib import Path

import nfl_rushing_yards_hub_v12 as prior_page
import nfl_rushing_yards_hub_v13 as page
import streamlit_memory_lazy_router_v109 as router


def _opponent(team_id: str, abbr: str) -> dict:
    return {
        "official_team_id": team_id,
        "team_abbreviation": abbr,
        "team_name": abbr,
    }


def _team(team_id: str, opponent_id: str, abbr: str, metrics: dict) -> dict:
    return {
        "official_team_id": team_id,
        "opponent_official_team_id": opponent_id,
        "team_abbreviation": abbr,
        "team_name": abbr,
        "opponent_run_front": {
            "official_team_id": opponent_id,
            "data_available": True,
            **metrics,
        },
    }


def test_v13_is_additive_matchup_classification_only() -> None:
    assert page.FROZEN_PRIOR == "nfl_rushing_yards_hub_v12"
    assert page.DISPLAY_ONLY is True
    assert page.MATCHUP_CLASSIFICATION_ONLY is True
    assert page.BETTING_GRADE_ENABLED is False
    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert page.TIER_ORDER == {"FAVORABLE": 0, "MEDIUM": 1, "TOUGH": 2}


def test_thresholds_are_explicit_and_locked() -> None:
    assert page.FAVORABLE_THRESHOLDS == {
        "rush_attempts_allowed_per_game": 27.0,
        "rush_yards_allowed_per_game": 120.0,
        "yards_per_carry_allowed": 4.5,
        "rushing_touchdowns_allowed_per_game": 1.0,
    }
    assert page.TOUGH_THRESHOLDS == {
        "rush_attempts_allowed_per_game": 22.0,
        "rush_yards_allowed_per_game": 95.0,
        "yards_per_carry_allowed": 3.9,
        "rushing_touchdowns_allowed_per_game": 0.6,
    }


def test_matchup_tier_favorable_medium_tough() -> None:
    opponent = _opponent("4", "CIN")

    favorable_team = _team(
        "27",
        "4",
        "TB",
        {
            "rush_attempts_allowed_per_game": 29.0,
            "rush_yards_allowed_per_game": 132.0,
            "yards_per_carry_allowed": 4.8,
            "rushing_touchdowns_allowed_per_game": 1.2,
        },
    )
    favorable = page._matchup_tier(favorable_team, opponent)
    assert favorable["tier"] == "FAVORABLE"
    assert favorable["score"] == 4
    assert favorable["favorable_signals"] == 4

    medium_team = _team(
        "27",
        "4",
        "TB",
        {
            "rush_attempts_allowed_per_game": 24.0,
            "rush_yards_allowed_per_game": 108.0,
            "yards_per_carry_allowed": 4.2,
            "rushing_touchdowns_allowed_per_game": 0.8,
        },
    )
    medium = page._matchup_tier(medium_team, opponent)
    assert medium["tier"] == "MEDIUM"
    assert medium["score"] == 0

    tough_team = _team(
        "27",
        "4",
        "TB",
        {
            "rush_attempts_allowed_per_game": 20.0,
            "rush_yards_allowed_per_game": 84.0,
            "yards_per_carry_allowed": 3.6,
            "rushing_touchdowns_allowed_per_game": 0.4,
        },
    )
    tough = page._matchup_tier(tough_team, opponent)
    assert tough["tier"] == "TOUGH"
    assert tough["score"] == -4
    assert tough["tough_signals"] == 4


def test_matchup_tier_requires_exact_opponent_identity() -> None:
    team = _team(
        "27",
        "4",
        "TB",
        {
            "rush_attempts_allowed_per_game": 29.0,
            "rush_yards_allowed_per_game": 132.0,
            "yards_per_carry_allowed": 4.8,
            "rushing_touchdowns_allowed_per_game": 1.2,
        },
    )
    wrong_opponent = _opponent("5", "BAL")
    grade = page._matchup_tier(team, wrong_opponent)
    assert grade["tier"] == "MEDIUM"
    assert grade["available"] is False
    assert grade["score"] == 0


def test_classified_rows_put_favorable_first_and_keep_market_only(monkeypatch) -> None:
    context = {
        "ready": True,
        "teams": [
            _team(
                "27",
                "4",
                "TB",
                {
                    "rush_attempts_allowed_per_game": 29.0,
                    "rush_yards_allowed_per_game": 132.0,
                    "yards_per_carry_allowed": 4.8,
                    "rushing_touchdowns_allowed_per_game": 1.2,
                },
            ),
            _team(
                "4",
                "27",
                "CIN",
                {
                    "rush_attempts_allowed_per_game": 20.0,
                    "rush_yards_allowed_per_game": 84.0,
                    "yards_per_carry_allowed": 3.6,
                    "rushing_touchdowns_allowed_per_game": 0.4,
                },
            ),
        ],
    }
    market = {
        "ready": True,
        "market_available": True,
        "props": [
            {
                "official_athlete_id": "200",
                "official_team_id": "4",
                "player_name": "Tough Player",
                "line": 40.5,
            },
            {
                "official_athlete_id": "100",
                "official_team_id": "27",
                "player_name": "Favorable Player",
                "line": 50.5,
            },
            {
                "official_athlete_id": "101",
                "official_team_id": "27",
                "player_name": "Favorable Market Only",
                "line": 20.5,
            },
        ],
    }
    monkeypatch.setattr(page.prior, "_projected_athlete_ids", lambda _context: {"100", "200"})
    rows = page._classified_prop_rows(context, market)
    assert [row["grade"]["tier"] for row in rows] == ["FAVORABLE", "FAVORABLE", "TOUGH"]
    assert rows[0]["market"]["official_team_id"] == "27"
    market_only = next(row for row in rows if row["market"]["official_athlete_id"] == "101")
    assert market_only["has_projection"] is False
    assert market_only["grade"]["tier"] == "FAVORABLE"


def test_v13_html_keeps_v12_contract_and_adds_tier_badges(monkeypatch) -> None:
    context = {
        "ready": True,
        "teams": [
            _team(
                "27",
                "4",
                "TB",
                {
                    "rush_attempts_allowed_per_game": 29.0,
                    "rush_yards_allowed_per_game": 132.0,
                    "yards_per_carry_allowed": 4.8,
                    "rushing_touchdowns_allowed_per_game": 1.2,
                },
            ),
            _team(
                "4",
                "27",
                "CIN",
                {
                    "rush_attempts_allowed_per_game": 24.0,
                    "rush_yards_allowed_per_game": 108.0,
                    "yards_per_carry_allowed": 4.2,
                    "rushing_touchdowns_allowed_per_game": 0.8,
                },
            ),
        ],
    }
    market = {
        "ready": True,
        "market_available": True,
        "age_seconds": 12,
        "props": [
            {
                "official_athlete_id": "300",
                "official_team_id": "4",
                "player_name": "Medium Player",
                "position": "RB",
                "line": 30.5,
                "over_odds": -110,
                "under_odds": -110,
            },
            {
                "official_athlete_id": "100",
                "official_team_id": "27",
                "player_name": "Favorable Player",
                "position": "RB",
                "line": 60.5,
                "over_odds": -108,
                "under_odds": -112,
            },
        ],
    }
    monkeypatch.setattr(page.prior, "_projected_athlete_ids", lambda _context: {"100"})
    html = page._lineup_board_html_v13(context, market)
    assert 'aria-label="Full FanDuel Rushing Yards lineup"' in html
    assert html.count("krush12-card krush13-card") == 2
    assert "FAVORABLE" in html
    assert "MEDIUM" in html
    assert "MARKET ONLY • NO PROJECTION" in html
    assert html.index("Favorable Player") < html.index("Medium Player")
    assert "projection influence <strong>0.0%</strong>" in html


def test_matchup_classification_does_not_read_sportsbook_prices() -> None:
    source = inspect.getsource(page._matchup_tier)
    assert "over_odds" not in source
    assert "under_odds" not in source
    assert "FanDuel" not in source


def test_v13_temporarily_patches_and_restores_v12_board(monkeypatch) -> None:
    original = prior_page._lineup_board_html
    observed = {"patched": False}

    def fake_render() -> None:
        observed["patched"] = prior_page._lineup_board_html is page._lineup_board_html_v13

    monkeypatch.setattr(prior_page, "render_nfl_rushing_yards_hub", fake_render)
    page.render_nfl_rushing_yards_hub()
    assert observed["patched"] is True
    assert prior_page._lineup_board_html is original


def test_router_v109_advances_only_rushing_owner() -> None:
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v108"
    assert router.ACTIVE_PAGE == "nfl_rushing_yards_hub_v13"
    assert router.RUSHING_YARDS_MARKET == "Rushing Yards"


def test_app_activates_v109_and_preserves_v108_heartbeat() -> None:
    text = Path("app.py").read_text(encoding="utf-8")
    assert "from streamlit_memory_lazy_router_v109 import record_bootstrap_import_ms, render_app" in text
    assert "STREAMLIT_MAIN_V108_NFL_RUSHING_YARDS_FANDUEL_FULL_LINEUP_2026-09-12" in text
    assert "STREAMLIT_MAIN_V109_NFL_RUSHING_YARDS_MATCHUP_TIERS_2026-09-12" in text
