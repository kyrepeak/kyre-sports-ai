"""Regression checks for College Football Step 8 Over/Under Model V1."""
from __future__ import annotations

import inspect

import cfb_over_under_model_v1 as model


def _game(status="Scheduled"):
    return {
        "identity_verified": True,
        "date_matches_query": True,
        "status": status,
        "away_team": "Oklahoma",
        "home_team": "Michigan",
    }


def _profile(team, ppg, allowed, recent_ppg=None, recent_allowed=None, games=4, grade="READY"):
    return {
        "team": team,
        "record": {"games": games},
        "ppg": ppg,
        "points_allowed_pg": allowed,
        "recent_ppg": recent_ppg if recent_ppg is not None else ppg,
        "recent_points_allowed_pg": recent_allowed if recent_allowed is not None else allowed,
        "official_stats": {},
        "data_quality": {"grade": grade},
    }


def test_raw_total_model_returns_projection_and_probabilities():
    away = _profile("Oklahoma", 34.0, 18.0, 36.0, 17.0)
    home = _profile("Michigan", 29.0, 14.0, 31.0, 13.0)

    out = model.project_matchup(_game(), away, home, 50.5)

    assert out["ready"] is True
    assert out["projected_total_ready"] is True
    assert out["over_under_probability_ready"] is True
    assert out["projected_total"] > 0
    assert out["projected_away_points"] > 0
    assert out["projected_home_points"] > 0
    assert 0 <= out["over_probability"] <= 1
    assert 0 <= out["under_probability"] <= 1
    assert out["push_probability"] == 0.0
    assert abs(
        out["over_probability"]
        + out["under_probability"]
        + out["push_probability"]
        - 1.0
    ) < 1e-12
    assert out["analysis_line_projection_weight"] == 0.0
    assert out["sportsbook_input_used"] is False
    assert out["market_price_used"] is False
    assert out["monte_carlo_used"] is False
    assert out["slate_ranking_ready"] is False
    assert out["final_pick_ready"] is False


def test_analysis_line_never_changes_projection():
    away = _profile("Oklahoma", 34.0, 18.0, 36.0, 17.0)
    home = _profile("Michigan", 29.0, 14.0, 31.0, 13.0)

    low = model.project_matchup(_game(), away, home, 42.5)
    high = model.project_matchup(_game(), away, home, 64.5)

    assert low["ready"] is True
    assert high["ready"] is True
    assert low["projected_total"] == high["projected_total"]
    assert low["projected_away_points"] == high["projected_away_points"]
    assert low["projected_home_points"] == high["projected_home_points"]
    assert low["components"] == high["components"]
    assert low["over_probability"] > high["over_probability"]
    assert low["under_probability"] < high["under_probability"]


def test_integer_total_line_has_explicit_push_probability():
    over, under, push = model._line_probabilities(
        projected_total=50.0,
        sigma=12.0,
        analysis_line=50.0,
    )

    assert over > 0
    assert under > 0
    assert push > 0
    assert abs(over + under + push - 1.0) < 1e-12


def test_half_point_line_has_zero_push_probability():
    over, under, push = model._line_probabilities(
        projected_total=50.0,
        sigma=12.0,
        analysis_line=50.5,
    )

    assert push == 0.0
    assert abs(over + under - 1.0) < 1e-12


def test_started_or_completed_games_fail_closed():
    away = _profile("Oklahoma", 34.0, 18.0)
    home = _profile("Michigan", 29.0, 14.0)

    for status in ("In Progress", "Halftime", "Final", "Completed"):
        out = model.project_matchup(_game(status), away, home, 50.5)
        assert out["ready"] is False
        assert "game is not verified pregame" in out["reasons"]


def test_unverified_identity_check_data_and_invalid_line_fail_closed():
    away = _profile("Oklahoma", 34.0, 18.0)
    home = _profile("Michigan", 29.0, 14.0)

    bad_game = _game()
    bad_game["identity_verified"] = False
    assert model.project_matchup(bad_game, away, home, 50.5)["ready"] is False

    check_home = dict(home)
    check_home["data_quality"] = {"grade": "CHECK"}
    assert model.project_matchup(_game(), away, check_home, 50.5)["ready"] is False

    assert model.project_matchup(_game(), away, home, 0.0)["ready"] is False
    assert model.project_matchup(_game(), away, home, 121.0)["ready"] is False


def test_step8_model_firewall_has_no_market_or_simulation_dependency():
    source = inspect.getsource(model).lower()

    assert model.ANALYSIS_LINE_PROJECTION_WEIGHT == 0.0
    assert model.MODEL_VERSION == "CFB OVER/UNDER MODEL V1 • STEP 8 RAW TOTAL MODEL"

    forbidden = (
        "import numpy",
        "np.random",
        "import requests",
        "urllib",
        "sportsbook_price",
        "sportsbook_total",
        "market_probability",
        "expected_value",
        "def simulate",
        "import random",
        "random.",
    )
    for token in forbidden:
        assert token not in source

    assert '"monte_carlo_used": false' not in source
    assert '"monte_carlo_used": False'.lower() in source
