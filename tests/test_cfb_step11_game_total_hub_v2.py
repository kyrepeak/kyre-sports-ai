"""Regression checks for College Football Step 11 Game Total Hub V2."""
from __future__ import annotations

import inspect

import cfb_game_total_hub_v2 as hub


def _output():
    return {
        "ready": True,
        "projected_combined_total": 54.2,
        "median_total": 54,
        "mode_total": 54,
        "mode_probability": 0.031,
        "structural_total_sigma": 13.7,
        "reliability": 0.84,
        "sample_factor": 0.8,
        "confidence": "MEDIUM",
        "feature_coverage": {"score": 0.85},
        "percentiles": {"p10": 37, "p25": 45, "p50": 54, "p75": 63, "p90": 72},
        "structural_interval_80": {"low": 37, "high": 72},
        "structural_interval_90": {"low": 32, "high": 77},
        "standard_bands": [
            {"label": "0-39", "probability": 0.16},
            {"label": "40-49", "probability": 0.22},
            {"label": "50-59", "probability": 0.28},
            {"label": "60-69", "probability": 0.22},
            {"label": "70+", "probability": 0.12},
        ],
        "around_projection": {
            "within_3": {"low": 51, "high": 57, "probability": 0.20},
            "within_7": {"low": 47, "high": 61, "probability": 0.40},
            "within_10": {"low": 44, "high": 64, "probability": 0.55},
        },
        "top_exact_totals": [
            {"total": 54, "probability": 0.031},
            {"total": 55, "probability": 0.030},
        ],
        "components": {
            "away_base_points": 26.0,
            "home_base_points": 27.0,
            "base_combined_total": 53.0,
            "recent_total_adjustment": 0.7,
            "efficiency_total_adjustment": 0.8,
        },
        "distribution": [
            {"total": 53, "probability": 0.03},
            {"total": 54, "probability": 0.031},
            {"total": 55, "probability": 0.03},
        ],
    }


def test_distribution_card_shows_core_shape_and_uncertainty():
    html = hub._distribution_card(_output())

    assert "Projected combined score" in html
    assert "54.2" in html
    assert "Median 54" in html
    assert "Mode 54" in html
    assert "Structural 80%" in html
    assert "37–72" in html
    assert "Structural 90%" in html
    assert "32–77" in html
    assert "NOT FINAL RANKING" in html


def test_band_exact_and_around_panels_render_probabilities():
    out = _output()

    band = hub._band_panel(out)
    around = hub._around_projection_panel(out)
    exact = hub._exact_panel(out)

    assert "STANDARD TOTAL-BAND PROBABILITIES" in band
    assert "28.0%" in band
    assert "Total 50-59" in band

    assert "PROBABILITY AROUND PROJECTED TOTAL" in around
    assert "Within ±7" in around
    assert "40.0%" in around

    assert "MOST LIKELY EXACT COMBINED TOTALS" in exact
    assert "54" in exact
    assert "3.1% exact" in exact


def test_distribution_rows_exposes_nontrivial_mass_only():
    rows = hub._distribution_rows(_output())
    assert len(rows) == 3
    assert rows[1]["Combined Total"] == 54
    assert rows[1]["Probability %"] == 3.1


def test_gated_card_fails_closed():
    html = hub._distribution_card(
        {"ready": False, "reasons": ["game is not verified pregame"]}
    )
    assert "GAME TOTAL MODEL GATED" in html
    assert "game is not verified pregame" in html
    assert "No projected combined total" in html


def test_step11_hub_uses_frozen_step10_and_no_final_or_market_layer():
    source = inspect.getsource(hub).lower()

    assert hub.FROZEN_GAME_TOTAL_HUB == "cfb_game_total_hub_v1"
    assert hub.MARKET == "Game Total"

    required = (
        "model.project_distribution",
        "full step-11 integer total distribution",
        "step 12 owns final synthesis",
    )
    for token in required:
        assert token.lower() in source

    forbidden = (
        "sportsbook_price",
        "market_probability",
        "expected_value",
        "rank_slate",
        "top-5",
        "import numpy",
        "np.random",
    )
    for token in forbidden:
        assert token not in source
