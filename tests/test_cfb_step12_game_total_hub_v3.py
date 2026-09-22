"""Regression checks for College Football Step 12 Game Total Hub V3."""
from __future__ import annotations

import inspect

import cfb_game_total_hub_v3 as hub


def _game():
    return {"away_team": "Oklahoma", "home_team": "Michigan"}


def _final():
    return {
        "ready": True,
        "forecast_status": "QUALIFIED",
        "grade": "B",
        "tier": "STRONG FORECAST",
        "forecast_strength": 0.78,
        "projected_combined_total": 54.2,
        "median_total": 54,
        "mode_total": 54,
        "core_50_range": {"low": 45, "high": 63},
        "structural_interval_80": {"low": 37, "high": 72},
        "most_likely_band": {"label": "50-59", "probability": 0.28},
        "within_7_probability": 0.40,
        "reliability": 0.86,
    }


def test_final_card_shows_projection_grade_and_ranges():
    html = hub._final_card(_game(), _final())
    assert "FINAL GAME TOTAL FORECAST" in html
    assert "54.2" in html
    assert "Core 50% range 45–63" in html
    assert "50-59" in html
    assert "STRONG FORECAST" in html
    assert "Forecast strength" in html


def test_gated_card_fails_closed():
    html = hub._final_card(
        _game(),
        {"ready": False, "reasons": ["game is not verified pregame"]},
    )
    assert "FINAL GAME TOTAL GATED" in html
    assert "game is not verified pregame" in html


def test_top_card_contains_rank_matchup_and_total():
    html = hub._top_card(
        {"rank": 1, "game": _game(), "final": _final()}
    )
    assert "#1" in html
    assert "Oklahoma @ Michigan" in html
    assert "54.2" in html
    assert "45–63" in html


def test_hub_completes_cfb_and_has_no_betting_market_layer():
    source = inspect.getsource(hub).lower()
    assert hub.FROZEN_GAME_TOTAL_HUB == "cfb_game_total_hub_v2"
    assert hub.MARKET == "Game Total"
    assert "final_model.rank_slate" in source
    assert "slate.scan_slate" in source
    assert "college football steps 1–12 are complete" in source

    forbidden = (
        "sportsbook_price",
        "market_probability",
        "expected_value",
        "analysis_line",
        "import numpy",
        "np.random",
    )
    for token in forbidden:
        assert token not in source
