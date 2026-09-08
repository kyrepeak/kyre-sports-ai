"""Regression checks for College Football Step 7 Over/Under foundation."""
from __future__ import annotations

import inspect

import pytest

import cfb_over_under_hub_v1 as hub


def _profile(team, conference, rank, record, grade="READY", games=3):
    return {
        "team": team,
        "conference": conference,
        "ap_rank": rank,
        "record_text": record,
        "record": {"games": games},
        "ppg": 31.4,
        "points_allowed_pg": 18.7,
        "recent_ppg": 33.0,
        "recent_points_allowed_pg": 17.0,
        "data_quality": {"grade": grade},
    }


def _game():
    return {
        "identity_verified": True,
        "date_matches_query": True,
        "away_team": "Oklahoma",
        "away_conference": "sec",
        "home_team": "Michigan",
        "home_conference": "big-ten",
        "kickoff_et": "7:30 PM ET",
        "venue": "Michigan Stadium",
        "status": "Scheduled",
        "broadcast": "ABC",
    }


def test_hero_has_verified_identity_and_both_teams():
    html = hub._hero(
        _game(),
        _profile("Oklahoma", "sec", 9, "2-0"),
        _profile("Michigan", "big-ten", 12, "2-0"),
    )

    assert "SELECTED OVER/UNDER MATCHUP" in html
    assert "IDENTITY VERIFIED" in html
    assert "#9 AP" in html
    assert "Oklahoma" in html
    assert "#12 AP" in html
    assert "Michigan" in html
    assert "7:30 PM ET" in html
    assert "Michigan Stadium" in html


def test_foundation_readiness_requires_verified_scoring_inputs_and_samples():
    away = _profile("Oklahoma", "sec", 9, "2-0", "READY", 2)
    home = _profile("Michigan", "big-ten", 12, "2-0", "LIMITED", 2)

    assert hub._foundation_ready(_game(), away, home) is True

    home["ppg"] = None
    assert hub._foundation_ready(_game(), away, home) is False

    home["ppg"] = 28.0
    home["data_quality"]["grade"] = "CHECK"
    assert hub._foundation_ready(_game(), away, home) is False


def test_environment_panel_is_descriptive_not_a_projection():
    away = _profile("Oklahoma", "sec", 9, "2-0")
    home = _profile("Michigan", "big-ten", 12, "2-0")
    away["ppg"] = 35.2
    away["points_allowed_pg"] = 17.4
    home["ppg"] = 29.8
    home["points_allowed_pg"] = 14.1

    html = hub._environment_panel(away, home)

    assert "SCORING ENVIRONMENT EVIDENCE" in html
    assert "35.2" in html
    assert "17.4" in html
    assert "29.8" in html
    assert "14.1" in html
    assert "not a projected game total" in html
    assert "not an Over/Under recommendation" in html


def test_model_locked_panel_reserves_steps_8_and_9():
    html = hub._model_locked_panel()
    assert "OVER/UNDER OUTPUT RESERVED" in html
    assert "projected game total" in html
    assert "Over/Under probability" in html
    assert "sportsbook total/price" in html
    assert "Monte Carlo simulation" in html
    assert "Step 8" in html
    assert "Step 9" in html


def test_non_over_under_market_is_rejected():
    with pytest.raises(ValueError):
        hub.render_cfb_hub("Moneyline")
    with pytest.raises(ValueError):
        hub.render_cfb_hub("Game Total")


def test_step7_uses_current_certified_data_but_has_no_total_model():
    source = inspect.getsource(hub)

    assert hub.MARKET == "Over/Under"
    assert hub.SCHEDULE_PROVIDER == "cfb_schedule_v3"
    assert hub.TEAM_DATA_PROVIDER == "cfb_team_data_v2"

    required = (
        "schedule.load_with_diagnostics",
        "team_data.load_matchup_team_data",
        "frozen_team_ui._team_card",
        "frozen_team_ui._team_data_diagnostics",
    )
    for token in required:
        assert token in source

    forbidden = (
        "import numpy",
        "np.random",
        "def simulate",
        "over_probability =",
        "under_probability =",
        "projected_total =",
        "fair_total =",
        "sportsbook_total =",
        "expected_value =",
        "cfb_moneyline_final_v1",
        "cfb_moneyline_model_v1",
    )
    for token in forbidden:
        assert token not in source
