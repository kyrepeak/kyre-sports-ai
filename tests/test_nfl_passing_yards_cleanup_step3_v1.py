from __future__ import annotations

from pathlib import Path

import nfl_passing_yards_hub_v15 as page


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_step3_summary_promotes_projection_probability_and_market_state() -> None:
    distributions = [
        {
            "ready": True,
            "qb_name": "QB One",
            "location_yards": 271.4,
            "sigma_yards": 42.0,
            "confidence": "HIGH",
            "quantiles": {"p50": 270.8},
        },
        {
            "ready": True,
            "qb_name": "QB Two",
            "location_yards": 238.2,
            "sigma_yards": 35.0,
            "confidence": "MEDIUM",
            "quantiles": {"p50": 237.9},
        },
    ]
    markets = [
        {
            "grade_ready": True,
            "lean": "LEAN OVER",
            "grade": "B",
            "line": 259.5,
            "model_over_probability": 0.61,
            "model_under_probability": 0.39,
        },
        {"grade_ready": False},
    ]
    html = page._summary_html(distributions, markets)
    assert "Game Center — Result First" in html
    assert "QB One" in html and "QB Two" in html
    assert "271.4" in html and "238.2" in html
    assert "P50 Median" in html
    assert "LEAN OVER" in html
    assert "Line 259.5" in html
    assert "61.0%" in html
    assert "MODEL READY • MARKET PENDING" in html
    assert "sportsbook projection influence remains exactly 0.0%" in html


def test_step3_summary_empty_when_no_certified_distribution_was_built() -> None:
    assert page._summary_html([], []) == ""


def test_step3_is_presentation_only_and_restores_capture_hooks() -> None:
    source = _read("nfl_passing_yards_hub_v15.py")
    assert "import nfl_passing_yards_hub_v14 as prior" in source
    assert "original_distribution = step9_ui.distribution.build_distribution" in source
    assert "original_market_card = step10_ui._market_card" in source
    assert "step9_ui.distribution.build_distribution = original_distribution" in source
    assert "step10_ui._market_card = original_market_card" in source
    assert "No loader, projection, distribution, market, or grading math is" in source
    assert "no extra network calls are made" in source


def test_step3_mobile_game_center_stacks_qb_results() -> None:
    css = page._CLEANUP_STEP3_CSS
    assert ".kpy15-grid{display:grid;grid-template-columns:repeat(2" in css
    assert "@media(max-width:700px)" in css
    assert ".kpy15-grid{grid-template-columns:1fr}" in css
    assert ".kpy-final-head{display:none!important}" in css


def test_router_v94_advances_only_passing_yards_cleanup_step3() -> None:
    hub = _read("nfl_hub_v33.py")
    router = _read("streamlit_memory_lazy_router_v94.py")
    app = _read("app.py")

    assert "import nfl_hub_v32 as base" in hub
    assert "nfl_passing_yards_hub_v15" in hub
    assert "import streamlit_memory_lazy_router_v93 as prior" in router
    assert "streamlit_memory_lazy_router_v80 as deepest_nfl_router" in router
    assert 'ACTIVE_NFL_HUB = "nfl_hub_v33"' in router
    assert "deepest_nfl_router._render_nfl_v80 = _render_nfl_v94" in router
    assert "streamlit_memory_lazy_router_v94" in app
    assert "STREAMLIT_MAIN_V93_NFL_PASSING_YARDS_CLEANUP_STEP2_2026-09-11" in app
    assert "STREAMLIT_MAIN_V94_NFL_PASSING_YARDS_CLEANUP_STEP3_2026-09-11" in app
    assert "Sportsbook projection influence remains 0.0%" in app
