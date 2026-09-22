from __future__ import annotations

from pathlib import Path

import nfl_passing_yards_hub_v16 as page


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_logo_url_is_display_only_espn_nfl_asset() -> None:
    assert page._logo_url("ARI") == "https://a.espncdn.com/i/teamlogos/nfl/500/ari.png"
    assert page._logo_url("") == ""


def test_matchup_spotlight_pairs_each_qb_with_opponent_defense() -> None:
    identity = {
        "ready": True,
        "away": {"abbr": "ARI", "team": "Arizona Cardinals", "qb1": {"name": "Away QB"}},
        "home": {"abbr": "LV", "team": "Las Vegas Raiders", "qb1": {"name": "Home QB"}},
    }
    baselines = [
        {"expected_attempts": 34.5, "expected_ypa": 7.2, "projection_yards": 248.4},
        {"expected_attempts": 31.0, "expected_ypa": 7.5, "projection_yards": 232.5},
    ]
    html = page._matchup_html(identity, baselines)
    assert "Matchup Spotlight" in html
    assert "Arizona Cardinals" in html
    assert "Las Vegas Raiders" in html
    assert "Away QB" in html
    assert "Home QB" in html
    assert "Arizona Cardinals</b> pass defense" in html
    assert "Las Vegas Raiders</b> pass defense" in html
    assert "ari.png" in html
    assert "lv.png" in html
    assert "248.4" in html
    assert "232.5" in html


def test_why_projection_promotes_existing_certified_drivers_only() -> None:
    baseline = {
        "qb_name": "Verified QB",
        "expected_attempts": 36.2,
        "expected_ypa": 7.45,
    }
    context = {
        "qb_name": "Verified QB",
        "context_projection_yards": 273.1,
        "pressure_adjustment_yards": 3.8,
        "personnel_context": "NEUTRAL",
        "weather_context": "NORMAL",
        "confidence": "HIGH",
    }
    dist = {
        "qb_name": "Verified QB",
        "ready": True,
        "location_yards": 273.1,
        "sigma_yards": 42.0,
        "confidence": "HIGH",
    }
    html = page._why_html([baseline], [context], [dist], [])
    assert "Why This Projection" in html
    assert "Verified QB" in html
    assert "36.2" in html
    assert "7.45" in html
    assert "+3.8" in html
    assert "NEUTRAL" in html
    assert "NORMAL" in html
    assert "42.0" in html
    assert "Projection: 273.1 yds" in html
    assert "MODEL READY • MARKET PENDING" in html
    assert "Sportsbook projection influence remains exactly 0.0%" in html


def test_why_projection_promotes_verified_market_state_without_recomputing() -> None:
    market = {
        "grade_ready": True,
        "lean": "LEAN OVER",
        "grade": "B",
        "line": 259.5,
        "model_over_probability": 0.612,
        "model_under_probability": 0.388,
    }
    html = page._why_html(
        [{"qb_name": "Verified QB", "expected_attempts": 35.0, "expected_ypa": 7.5}],
        [{"qb_name": "Verified QB", "context_projection_yards": 270.0, "pressure_adjustment_yards": 0.0}],
        [{"qb_name": "Verified QB", "location_yards": 270.0, "sigma_yards": 40.0, "confidence": "MEDIUM"}],
        [market],
    )
    assert "LEAN OVER" in html
    assert "259.5" in html
    assert "61.2%" in html
    assert "38.8%" in html
    assert ">B<" in html


def test_cleanup_step4_source_restores_all_capture_hooks() -> None:
    source = _read("nfl_passing_yards_hub_v16.py")
    assert "step7_ui.identity.resolve_matchup_identity = original_identity" in source
    assert "step7_ui.projection.build_baseline_projection = original_baseline" in source
    assert "step8_ui.context.build_context_projection = original_context" in source
    assert "step9_ui.distribution.build_distribution = original_distribution" in source
    assert "step10_ui._market_card = original_market_card" in source
    assert "No new server-side data requests are made" in source


def test_router_v95_advances_only_passing_yards_cleanup_step4() -> None:
    hub = _read("nfl_hub_v34.py")
    router = _read("streamlit_memory_lazy_router_v95.py")
    app = _read("app.py")
    page_source = _read("nfl_passing_yards_hub_v16.py")

    assert "import nfl_hub_v33 as base" in hub
    assert "nfl_passing_yards_hub_v16" in hub
    assert "import streamlit_memory_lazy_router_v94 as prior" in router
    assert "streamlit_memory_lazy_router_v80 as deepest_nfl_router" in router
    assert 'ACTIVE_NFL_HUB = "nfl_hub_v34"' in router
    assert "streamlit_memory_lazy_router_v95" in app
    assert "STREAMLIT_MAIN_V94_NFL_PASSING_YARDS_CLEANUP_STEP3_2026-09-11" in app
    assert "STREAMLIT_MAIN_V95_NFL_PASSING_YARDS_CLEANUP_STEP4_2026-09-11" in app
    assert "Matchup Spotlight" in page_source
    assert "Why This Projection" in page_source
    assert "sportsbook projection influence remains exactly 0.0%" in page_source.lower()
    assert "stake sizing remains OFF" in app
