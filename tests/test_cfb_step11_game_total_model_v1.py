"""Regression checks for College Football Step 11 Game Total Model V1."""
from __future__ import annotations

import inspect

import cfb_game_total_model_v1 as model


def _game(status="Scheduled"):
    return {
        "identity_verified": True,
        "date_matches_query": True,
        "status": status,
        "away_team": "Oklahoma",
        "home_team": "Michigan",
    }


def _profile(
    team,
    ppg,
    allowed,
    recent_ppg=None,
    recent_allowed=None,
    games=4,
    grade="READY",
):
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


def test_distribution_model_returns_complete_independent_total_shape():
    away = _profile("Oklahoma", 34.0, 18.0, 36.0, 17.0)
    home = _profile("Michigan", 29.0, 14.0, 31.0, 13.0)

    out = model.project_distribution(_game(), away, home)

    assert out["ready"] is True
    assert out["projected_combined_total_ready"] is True
    assert out["distribution_ready"] is True
    assert out["median_or_mode_ready"] is True
    assert out["exact_total_probability_ready"] is True
    assert out["total_band_probability_ready"] is True
    assert out["percentile_distribution_ready"] is True

    assert 0 < out["projected_combined_total"] <= model.MAX_PROJECTED_TOTAL
    assert isinstance(out["median_total"], int)
    assert isinstance(out["mode_total"], int)
    assert 0 < out["mode_probability"] < 1

    mass = sum(row["probability"] for row in out["distribution"])
    assert abs(mass - 1.0) < 1e-12

    assert len(out["standard_bands"]) == 5
    band_mass = sum(row["probability"] for row in out["standard_bands"])
    assert abs(band_mass - 1.0) < 1e-12

    assert len(out["top_exact_totals"]) == 7
    assert out["sportsbook_input_used"] is False
    assert out["market_price_used"] is False
    assert out["market_probability_used"] is False
    assert out["edge_or_ev_used"] is False
    assert out["final_pick_ready"] is False
    assert out["slate_ranking_ready"] is False
    assert out["monte_carlo_used"] is False
    assert out["empirical_calibration_claimed"] is False


def test_percentiles_are_ordered_and_intervals_are_structural():
    away = _profile("Oklahoma", 34.0, 18.0)
    home = _profile("Michigan", 29.0, 14.0)

    out = model.project_distribution(_game(), away, home)
    p = out["percentiles"]

    assert p["p10"] <= p["p25"] <= p["p50"] <= p["p75"] <= p["p90"]
    assert out["structural_interval_80"]["low"] == p["p10"]
    assert out["structural_interval_80"]["high"] == p["p90"]
    assert out["structural_interval_90"]["low"] <= p["p10"]
    assert out["structural_interval_90"]["high"] >= p["p90"]


def test_probability_around_projection_expands_monotonically():
    away = _profile("Oklahoma", 34.0, 18.0)
    home = _profile("Michigan", 29.0, 14.0)

    out = model.project_distribution(_game(), away, home)
    around = out["around_projection"]

    assert 0 < around["within_3"]["probability"] < 1
    assert around["within_3"]["probability"] <= around["within_7"]["probability"]
    assert around["within_7"]["probability"] <= around["within_10"]["probability"]


def test_discrete_distribution_normalizes():
    rows = model._discrete_distribution(mean=52.4, sigma=14.2)
    assert len(rows) == model.MAX_DISTRIBUTION_TOTAL + 1
    assert abs(sum(row["probability"] for row in rows) - 1.0) < 1e-12
    assert max(rows, key=lambda r: r["probability"])["total"] in {52, 53}


def test_range_probability_matches_direct_sum():
    rows = model._discrete_distribution(mean=50.0, sigma=10.0)
    direct = sum(row["probability"] for row in rows if 45 <= row["total"] <= 55)
    assert abs(model._range_probability(rows, 45, 55) - direct) < 1e-15


def test_started_or_completed_games_fail_closed():
    away = _profile("Oklahoma", 34.0, 18.0)
    home = _profile("Michigan", 29.0, 14.0)

    for status in ("In Progress", "Halftime", "Final", "Completed"):
        out = model.project_distribution(_game(status), away, home)
        assert out["ready"] is False
        assert "game is not verified pregame" in out["reasons"]


def test_bad_identity_quality_or_sample_fail_closed():
    away = _profile("Oklahoma", 34.0, 18.0)
    home = _profile("Michigan", 29.0, 14.0)

    bad_game = _game()
    bad_game["identity_verified"] = False
    assert model.project_distribution(bad_game, away, home)["ready"] is False

    check_home = _profile("Michigan", 29.0, 14.0, grade="CHECK")
    assert model.project_distribution(_game(), away, check_home)["ready"] is False

    no_sample = _profile("Michigan", 29.0, 14.0, games=0)
    assert model.project_distribution(_game(), away, no_sample)["ready"] is False


def test_step11_model_has_no_market_line_simulation_or_cross_market_dependency():
    source = inspect.getsource(model).lower()

    assert model.MODEL_VERSION == "CFB GAME TOTAL MODEL V1 • STEP 11 DISTRIBUTION"

    forbidden = (
        "cfb_over_under_model_v1",
        "cfb_moneyline_model_v1",
        "analysis_line",
        "sportsbook_total",
        "sportsbook_price",
        "expected_value",
        "import numpy",
        "np.random",
        "import random",
        "random.",
        "def simulate",
    )
    for token in forbidden:
        assert token not in source
