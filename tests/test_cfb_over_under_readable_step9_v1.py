"""Regression tests for readable CFB O/U Step 9 game-day environment presentation."""
from __future__ import annotations

import inspect

import cfb_over_under_clean_page_v26 as page
import cfb_over_under_step9_readable_v1 as readable


def _engine(*, sigma: float = 0.75, indoor: bool = False) -> dict:
    return {
        "model_ready": True,
        "event_id": "401858213",
        "same_date_event_identity_verified": True,
        "away_espn_team_id": "50",
        "home_espn_team_id": "2390",
        "away_event_team": "Florida A&M Rattlers",
        "home_event_team": "Miami Hurricanes",
        "coverage": 1.0,
        "roster_audit_coverage": 1.0,
        "sigma_adjustment": sigma,
        "weather": {
            "ready": True,
            "temperature_f": 84,
            "gust_mph": 18,
            "precipitation_pct": 62,
            "fields_available": 3,
        },
        "venue": {
            "ready": True,
            "name": "Hard Rock Stadium",
            "city": "Miami Gardens",
            "state": "FL",
            "indoor": indoor,
        },
        "weather_stress": {
            "gust_stress": 0.15,
            "precipitation_stress": 0.24,
            "temperature_stress": 0.0,
            "total_stress": 0.18,
            "sigma_adjustment": sigma,
            "indoor_weather_neutralized": indoor,
        },
        "away_availability": {
            "ready": True,
            "roster_total": 99,
            "active_count": 97,
            "flagged_count": 2,
            "timestamp": "2026-09-09T00:50:05Z",
        },
        "home_availability": {
            "ready": True,
            "roster_total": 100,
            "active_count": 98,
            "flagged_count": 0,
            "timestamp": "2026-09-09T00:52:18Z",
        },
        "injury_reporting_completeness_certified": False,
        "injury_model_weight": 0.0,
        "sportsbook_input_used": False,
        "market_price_used": False,
        "market_probability_used": False,
        "edge_or_ev_used": False,
        "monte_carlo_used": False,
    }


def test_readable_step9_explains_identity_weather_and_audit():
    html = readable.render_step9(_engine())
    assert "STEP 9 • GAME-DAY ENVIRONMENT" in html
    assert "401858213" in html
    assert "Hard Rock Stadium" in html
    assert "84°F" in html
    assert "WEATHER INCREASES GAME UNCERTAINTY" in html
    assert "Zero reported flags" in html
    assert "Projected total remains unchanged by Step 9" in html
    assert "sportsbook projection weight: <b>0.0%</b>" in html
    assert "no fuzzy matching" in html
    assert "no synthetic IDs" in html


def test_indoor_weather_is_presented_as_neutral():
    html = readable.render_step9(_engine(sigma=0.0, indoor=True))
    assert "INDOOR / WEATHER NEUTRAL" in html
    assert "weather neutralized" in html


def test_readable_step9_fails_closed_without_official_event_identity():
    html = readable.render_step9(
        {"model_ready": False, "reason": "weather fields are incomplete"}
    )
    assert "GATED" in html
    assert "Official ESPN event ID is unavailable" in html
    assert "weather fields are incomplete" in html
    assert "projected-total adjustment: <b>0.00 pts</b>" in html


def test_v26_is_additive_over_v25_and_replaces_only_step9():
    assert page.FROZEN_PAGE == "cfb_over_under_clean_page_v25"
    assert page.ACTIVE_MARKET_ADAPTER == page.frozen_page.ACTIVE_MARKET_ADAPTER
    assert page.ACTIVE_MARKET_INTELLIGENCE == page.frozen_page.ACTIVE_MARKET_INTELLIGENCE
    assert page._RENDER_V26.__code__ is page.frozen_page._RENDER_V25.__code__
    for step, title in (
        (4, "PACE"),
        (5, "EXPLOSIVE"),
        (6, "RED ZONE"),
        (7, "THIRD DOWN"),
        (8, "TURNOVER"),
    ):
        assert page._PRESENTATION_PROXY._model_step(
            step, title, {}
        ) == page._BASE_PRESENTATION._model_step(step, title, {})
    assert "STEP 9 • GAME-DAY ENVIRONMENT" in page._PRESENTATION_PROXY._model_step(
        9, "ENVIRONMENT", _engine()
    )


def test_v26_marker_preserves_prior_safety_contract(monkeypatch):
    seen = []
    monkeypatch.setattr(page.st, "caption", lambda body, *a, **k: seen.append(str(body)))
    page._StreamlitV26Proxy().caption("🟢 CFB O/U • CLEAN PAGE V20 ACTIVE")
    marker = seen[0]
    for token in (
        "CFB O/U • CLEAN PAGE V20 ACTIVE",
        "STEP 6 MARKET INTELLIGENCE LIVE",
        "FRESHNESS FIREWALL ACTIVE",
        "0.0% PROJECTION INFLUENCE",
        "FROZEN PROJECTION MATH PRESERVED",
        "READABLE STEP 8 TURNOVER VOLATILITY ACTIVE",
        "READABLE STEP 9 GAME-DAY ENVIRONMENT ACTIVE",
    ):
        assert token in marker


def test_readable_step9_layer_contains_no_engine_recomputation():
    source = inspect.getsource(readable) + inspect.getsource(page)
    for token in (
        "build_environment_engine(",
        "apply_to_raw(",
        "runtime_slate.analyze_game(",
        "project_matchup(",
        "rank_slate(",
    ):
        assert token not in source
    assert readable.PROJECTION_WEIGHT == 0.0
    assert readable.MAY_MODIFY_PROJECTION is False
