from __future__ import annotations

import inspect
from pathlib import Path

import nfl_receiving_yards_hub_v8 as prior_page
import nfl_receiving_yards_hub_v9 as page
import streamlit_memory_lazy_router_v120 as router


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
        "opponent_pass_defense": {
            "official_team_id": opponent_id,
            "data_available": True,
            **metrics,
        },
    }


def _favorable_metrics() -> dict:
    return {
        "receptions_allowed_per_game": 25.0,
        "receiving_yards_allowed_per_game": 265.0,
        "yards_per_reception_allowed": 11.8,
        "receiving_touchdowns_allowed_per_game": 1.8,
    }


def _medium_metrics() -> dict:
    return {
        "receptions_allowed_per_game": 21.0,
        "receiving_yards_allowed_per_game": 218.0,
        "yards_per_reception_allowed": 10.2,
        "receiving_touchdowns_allowed_per_game": 1.2,
    }


def _tough_metrics() -> dict:
    return {
        "receptions_allowed_per_game": 17.0,
        "receiving_yards_allowed_per_game": 178.0,
        "yards_per_reception_allowed": 8.9,
        "receiving_touchdowns_allowed_per_game": 0.6,
    }


def test_v9_is_additive_matchup_classification_only() -> None:
    assert page.FROZEN_PRIOR == "nfl_receiving_yards_hub_v8"
    assert page.FROZEN_PROJECTION_ENGINE == "nfl_receiving_yards_projection_v1"
    assert page.PAGE_BUILD_STEP == 9
    assert page.PAGE_BUILD_TOTAL == 10
    assert page.DISPLAY_ONLY is True
    assert page.MATCHUP_CLASSIFICATION_ONLY is True
    assert page.BETTING_GRADE_ENABLED is False
    assert page.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0
    assert page.TIER_ORDER == {"FAVORABLE": 0, "MEDIUM": 1, "TOUGH": 2}


def test_thresholds_are_explicit_and_locked() -> None:
    assert page.FAVORABLE_THRESHOLDS == {
        "receptions_allowed_per_game": 23.0,
        "receiving_yards_allowed_per_game": 240.0,
        "yards_per_reception_allowed": 11.0,
        "receiving_touchdowns_allowed_per_game": 1.5,
    }
    assert page.TOUGH_THRESHOLDS == {
        "receptions_allowed_per_game": 19.0,
        "receiving_yards_allowed_per_game": 195.0,
        "yards_per_reception_allowed": 9.5,
        "receiving_touchdowns_allowed_per_game": 0.9,
    }


def test_matchup_tier_favorable_medium_tough() -> None:
    opponent = _opponent("4", "CIN")

    favorable = page._matchup_tier(_team("27", "4", "TB", _favorable_metrics()), opponent)
    assert favorable["tier"] == "FAVORABLE"
    assert favorable["score"] == 4
    assert favorable["favorable_signals"] == 4

    medium = page._matchup_tier(_team("27", "4", "TB", _medium_metrics()), opponent)
    assert medium["tier"] == "MEDIUM"
    assert medium["score"] == 0

    tough = page._matchup_tier(_team("27", "4", "TB", _tough_metrics()), opponent)
    assert tough["tier"] == "TOUGH"
    assert tough["score"] == -4
    assert tough["tough_signals"] == 4


def test_matchup_tier_requires_exact_opponent_identity() -> None:
    team = _team("27", "4", "TB", _favorable_metrics())
    grade = page._matchup_tier(team, _opponent("5", "BAL"))
    assert grade["tier"] == "MEDIUM"
    assert grade["available"] is False
    assert grade["score"] == 0


def test_incomplete_pass_defense_fails_to_unavailable_medium() -> None:
    metrics = _favorable_metrics()
    metrics.pop("yards_per_reception_allowed")
    grade = page._matchup_tier(_team("27", "4", "TB", metrics), _opponent("4", "CIN"))
    assert grade["tier"] == "MEDIUM"
    assert grade["available"] is False
    assert grade["score"] == 0
    assert "incomplete" in grade["reason"]


def test_targets_are_optional_and_never_required_for_tier() -> None:
    metrics = _favorable_metrics()
    metrics["targets_data_available"] = False
    metrics["targets_allowed_per_game"] = None
    grade = page._matchup_tier(_team("27", "4", "TB", metrics), _opponent("4", "CIN"))
    assert grade["tier"] == "FAVORABLE"
    assert grade["score"] == 4


def test_classified_rows_put_favorable_first_and_keep_market_only(monkeypatch) -> None:
    context = {
        "ready": True,
        "teams": [
            _team("27", "4", "TB", _favorable_metrics()),
            _team("4", "27", "CIN", _tough_metrics()),
        ],
    }
    market = {
        "ready": True,
        "market_available": True,
        "props": [
            {"official_athlete_id": "200", "official_team_id": "4", "player_name": "Tough Receiver", "line": 40.5},
            {"official_athlete_id": "101", "official_team_id": "27", "player_name": "Market Only", "line": 30.5},
            {"official_athlete_id": "100", "official_team_id": "27", "player_name": "Projected Receiver", "line": 60.5},
        ],
    }
    monkeypatch.setattr(page.prior, "_projected_athlete_ids", lambda _context: {"100", "200"})
    rows = page._classified_prop_rows(context, market)
    assert [row["grade"]["tier"] for row in rows] == ["FAVORABLE", "FAVORABLE", "TOUGH"]
    assert [row["market"]["official_athlete_id"] for row in rows[:2]] == ["100", "101"]
    market_only = next(row for row in rows if row["market"]["official_athlete_id"] == "101")
    assert market_only["has_projection"] is False
    assert market_only["grade"]["tier"] == "FAVORABLE"


def test_v9_html_keeps_market_contract_and_adds_tier_badges(monkeypatch) -> None:
    context = {
        "ready": True,
        "teams": [
            _team("27", "4", "TB", _favorable_metrics()),
            _team("4", "27", "CIN", _medium_metrics()),
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
                "player_name": "Medium Receiver",
                "position": "WR",
                "line": 45.5,
                "over_odds": -110,
                "under_odds": -110,
            },
            {
                "official_athlete_id": "100",
                "official_team_id": "27",
                "player_name": "Favorable Receiver",
                "position": "TE",
                "line": 62.5,
                "over_odds": -108,
                "under_odds": -112,
            },
        ],
    }
    monkeypatch.setattr(page.prior, "_projected_athlete_ids", lambda _context: {"100"})
    html = page._lineup_board_html_v9(context, market)
    assert 'aria-label="Full FanDuel Receiving Yards lineup with matchup tiers"' in html
    assert html.count("krecv8-card krecv9-card") == 2
    assert "FAVORABLE" in html
    assert "MEDIUM" in html
    assert "MARKET ONLY • NO PROJECTION" in html
    assert html.index("Favorable Receiver") < html.index("Medium Receiver")
    assert "projection influence <strong>0.0%</strong>" in html


def test_matchup_classification_does_not_read_sportsbook_prices_or_names() -> None:
    source = inspect.getsource(page._matchup_tier)
    for forbidden in ("over_odds", "under_odds", "FanDuel", "player_name"):
        assert forbidden not in source


def test_v9_temporarily_patches_and_restores_v8_board(monkeypatch) -> None:
    original_board = prior_page._lineup_board_html
    original_advance = prior_page._advance_step8_copy
    observed = {"board": False, "advance": False}

    def fake_render() -> None:
        observed["board"] = prior_page._lineup_board_html is page._lineup_board_html_v9
        observed["advance"] = prior_page._advance_step8_copy is page._advance_step9_copy

    monkeypatch.setattr(prior_page, "render_nfl_receiving_yards_hub", fake_render)
    page.render_nfl_receiving_yards_hub()
    assert observed == {"board": True, "advance": True}
    assert prior_page._lineup_board_html is original_board
    assert prior_page._advance_step8_copy is original_advance


def test_router_v120_advances_only_receiving_owner() -> None:
    assert router.FROZEN_ROUTER == "streamlit_memory_lazy_router_v119"
    assert router.ACTIVE_RECEIVING_YARDS_HUB == "nfl_receiving_yards_hub_v9"
    assert router.RECEIVING_YARDS_MARKET == "Receiving Yards"
    assert router.SPORTSBOOK_PROJECTION_INFLUENCE == 0.0


def test_app_activates_v120_and_preserves_v119_heartbeat() -> None:
    text = Path("app.py").read_text(encoding="utf-8")
    assert "from streamlit_memory_lazy_router_v120 import record_bootstrap_import_ms, render_app" in text
    assert "STREAMLIT_MAIN_V119_NFL_RECEIVING_YARDS_STEP8_FANDUEL_FULL_LINEUP_2026-09-13" in text
    assert "STREAMLIT_MAIN_V120_NFL_RECEIVING_YARDS_STEP9_MATCHUP_TIERS_2026-09-13" in text
