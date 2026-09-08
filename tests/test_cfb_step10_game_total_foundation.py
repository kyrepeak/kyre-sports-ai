"""Regression checks for College Football Step 10 Game Total foundation."""
from __future__ import annotations

import inspect

import pytest

import cfb_game_total_hub_v1 as hub


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


def _profile(team, ppg=30.0, allowed=20.0, recent_ppg=31.0, recent_allowed=19.0, games=3, grade="READY"):
    return {
        "team": team,
        "conference": "sec" if team == "Oklahoma" else "big-ten",
        "ap_rank": 9 if team == "Oklahoma" else 12,
        "record_text": "2-0",
        "record": {"games": games},
        "ppg": ppg,
        "points_allowed_pg": allowed,
        "recent_ppg": recent_ppg,
        "recent_points_allowed_pg": recent_allowed,
        "official_stats": {},
        "data_quality": {"grade": grade},
    }


def test_foundation_ready_requires_identity_scoring_sample_and_quality():
    away = _profile("Oklahoma")
    home = _profile("Michigan")
    assert hub._foundation_ready(_game(), away, home) is True

    home["ppg"] = None
    assert hub._foundation_ready(_game(), away, home) is False

    home["ppg"] = 29.0
    home["data_quality"]["grade"] = "CHECK"
    assert hub._foundation_ready(_game(), away, home) is False


def test_descriptive_combined_context_is_plain_arithmetic_only():
    away = _profile("Oklahoma", ppg=34.0, allowed=18.0, recent_ppg=36.0, recent_allowed=17.0)
    home = _profile("Michigan", ppg=29.0, allowed=14.0, recent_ppg=31.0, recent_allowed=13.0)

    out = hub._descriptive_combined_context(away, home)

    assert out["season_offense_sum"] == 63.0
    assert out["season_allowance_sum"] == 32.0
    assert out["recent_offense_sum"] == 67.0
    assert out["recent_allowance_sum"] == 30.0


def test_hero_has_verified_matchup_identity():
    html = hub._hero(_game(), _profile("Oklahoma"), _profile("Michigan"))

    assert "SELECTED GAME TOTAL MATCHUP" in html
    assert "IDENTITY VERIFIED" in html
    assert "Oklahoma" in html
    assert "Michigan" in html
    assert "7:30 PM ET" in html
    assert "Michigan Stadium" in html


def test_environment_panel_labels_sums_as_descriptive_not_projection():
    html = hub._environment_panel(
        _profile("Oklahoma", ppg=34.0, allowed=18.0),
        _profile("Michigan", ppg=29.0, allowed=14.0),
    )

    assert "COMBINED-SCORE EVIDENCE" in html
    assert "Season offense sum 63.0" in html
    assert "Season allowance sum 32.0" in html
    assert "descriptive arithmetic" in html
    assert "not a projected game total" in html


def test_distribution_locked_panel_reserves_steps_11_and_12():
    html = hub._distribution_locked_panel()

    assert "GAME TOTAL DISTRIBUTION OUTPUT RESERVED" in html
    assert "Projected combined total" in html
    assert "exact-total probabilities" in html
    assert "Monte Carlo" in html
    assert "Step 11" in html
    assert "Step 12" in html


def test_non_game_total_market_is_rejected():
    with pytest.raises(ValueError):
        hub.render_cfb_hub("Moneyline")
    with pytest.raises(ValueError):
        hub.render_cfb_hub("Over/Under")


def test_step10_uses_certified_data_and_has_no_model_or_distribution():
    source = inspect.getsource(hub).lower()

    assert hub.MARKET == "Game Total"
    assert hub.SCHEDULE_PROVIDER == "cfb_schedule_v3"
    assert hub.TEAM_DATA_PROVIDER == "cfb_team_data_v2"

    required = (
        "schedule.load_with_diagnostics",
        "team_data.load_matchup_team_data",
        "team_ui._team_card",
        "team_ui._team_data_diagnostics",
    )
    original = inspect.getsource(hub)
    for token in required:
        assert token in original

    forbidden = (
        "cfb_over_under_model_v1",
        "cfb_moneyline_model_v1",
        "projected_total =",
        "exact_total_probability",
        "percentile",
        "def simulate",
        "np.random",
        "import numpy",
        "sportsbook_price",
        "expected_value",
    )
    for token in forbidden:
        assert token not in source
