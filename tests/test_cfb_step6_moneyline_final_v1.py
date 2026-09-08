"""Regression checks for College Football Step 6 final synthesis."""
from __future__ import annotations

import inspect

import pytest

import cfb_moneyline_final_v1 as final
import cfb_moneyline_hub_v5 as hub


def _raw(
    home_p=.70,
    reliability=.90,
    coverage=.90,
    sample=1.0,
    confidence="HIGH",
):
    return {
        "version": "CFB MONEYLINE MODEL V1",
        "ready": True,
        "raw_probability_ready": True,
        "home_win_probability_raw": home_p,
        "away_win_probability_raw": 1.0 - home_p,
        "projected_home_points_raw": 31.0,
        "projected_away_points_raw": 24.0,
        "projected_margin_home_raw": 7.0,
        "projected_total_raw": 55.0,
        "reliability": reliability,
        "sample_factor": sample,
        "feature_coverage": {"score": coverage},
        "confidence": confidence,
    }


def _game():
    return {
        "identity_key": "ncaa:1",
        "away_team": "Away",
        "home_team": "Home",
        "kickoff_iso": "2026-09-12T12:00:00-04:00",
    }


def _teams():
    return {"team": "Away"}, {"team": "Home"}


def test_even_raw_probability_stays_exactly_even():
    away, home = _teams()
    out = final.synthesize(_game(), away, home, _raw(home_p=.50))

    assert out["ready"] is True
    assert out["home_win_probability_final"] == pytest.approx(.50, abs=1e-12)
    assert out["away_win_probability_final"] == pytest.approx(.50, abs=1e-12)
    assert out["home_fair_moneyline"] == -100
    assert out["away_fair_moneyline"] == -100


def test_structural_calibration_shrinks_raw_edge_toward_fifty():
    away, home = _teams()
    raw = _raw(home_p=.80, reliability=.80, coverage=.70, sample=.60, confidence="MEDIUM")
    out = final.synthesize(_game(), away, home, raw)

    assert .50 < out["home_win_probability_final"] < .80
    assert out["away_win_probability_final"] == pytest.approx(
        1.0 - out["home_win_probability_final"]
    )
    assert out["calibration_temperature"] > 1.0


def test_lower_quality_creates_stronger_probability_shrink():
    away, home = _teams()
    high = final.synthesize(
        _game(), away, home,
        _raw(home_p=.75, reliability=.95, coverage=.95, sample=1.0, confidence="HIGH"),
    )
    low = final.synthesize(
        _game(), away, home,
        _raw(home_p=.75, reliability=.60, coverage=.45, sample=.20, confidence="LOW"),
    )

    assert low["calibration_temperature"] > high["calibration_temperature"]
    assert low["home_win_probability_final"] < high["home_win_probability_final"]


def test_fair_moneyline_is_model_derived_and_complementary():
    away, home = _teams()
    out = final.synthesize(_game(), away, home, _raw(home_p=.72))

    assert out["home_fair_moneyline"] < -100
    assert out["away_fair_moneyline"] > 100
    assert out["fair_moneyline_ready"] is True
    assert out["market_weight"] == 0.0
    assert out["market_probability_used"] is False


def test_structural_uncertainty_widens_for_lower_quality():
    away, home = _teams()
    high = final.synthesize(
        _game(), away, home,
        _raw(home_p=.70, reliability=.95, coverage=.95, sample=1.0),
    )
    low = final.synthesize(
        _game(), away, home,
        _raw(home_p=.70, reliability=.60, coverage=.40, sample=.20, confidence="LOW"),
    )

    high_width = (
        high["home_probability_uncertainty"]["p90_high"]
        - high["home_probability_uncertainty"]["p90_low"]
    )
    low_width = (
        low["home_probability_uncertainty"]["p90_high"]
        - low["home_probability_uncertainty"]["p90_low"]
    )
    assert low_width > high_width


def test_final_synthesis_fails_closed_when_raw_model_is_gated():
    away, home = _teams()
    out = final.synthesize(
        _game(),
        away,
        home,
        {
            "ready": False,
            "raw_probability_ready": False,
            "reasons": ["team data CHECK"],
        },
    )

    assert out["ready"] is False
    assert out["fair_moneyline_ready"] is False
    assert out["final_pick_ready"] is False
    assert "home_win_probability_final" not in out


def test_rank_slate_is_pure_final_probability_not_price():
    rows = []
    for game_id, p, grade in (
        ("1", .66, "A+"),
        ("2", .74, "B"),
        ("3", .70, "A"),
    ):
        rows.append({
            "game": {"identity_key": f"ncaa:{game_id}", "kickoff_iso": game_id},
            "final": {
                "ready": True,
                "winner_probability_final": p,
                "model_grade": grade,
                "reliability": .80,
                "feature_coverage": .80,
            },
        })

    ranked = final.rank_slate(rows, limit=3)

    assert [r["game"]["identity_key"] for r in ranked] == [
        "ncaa:2", "ncaa:3", "ncaa:1"
    ]
    assert [r["rank"] for r in ranked] == [1, 2, 3]


def test_calibration_is_explicitly_not_empirical_or_market_fit():
    away, home = _teams()
    out = final.synthesize(_game(), away, home, _raw())

    assert out["calibration_method"] == "STRUCTURAL_RELIABILITY_TEMPERATURE_V1"
    assert out["empirical_backtest_calibrated"] is False
    assert final.MARKET_WEIGHT == 0.0


def test_final_model_source_has_no_sportsbook_or_network_dependency():
    source = inspect.getsource(final).lower()

    forbidden = (
        "requests.",
        "urllib",
        "sportsbook_price",
        "market_probability =",
        "expected_value",
        "numpy",
        "np.random",
    )
    for token in forbidden:
        assert token not in source


def test_final_ui_labels_structural_calibration_and_zero_market_weight():
    away, home = _teams()
    out = final.synthesize(_game(), away, home, _raw())
    html = hub._final_card(_game(), away, home, out)

    assert "FINAL MODEL" in html
    assert "fair ML" in html
    assert "Sportsbook probability weight" in html
    assert "0%" in html
    assert "structural reliability/coverage shrink" in html
