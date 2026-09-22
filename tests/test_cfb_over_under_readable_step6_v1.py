"""Regression tests for readable CFB O/U Step 6 red-zone presentation."""
from __future__ import annotations

import inspect

import cfb_over_under_clean_page_v23 as page
import cfb_over_under_step6_readable_v1 as readable


def _side(name, opp, adjustment):
    return {
        "offense_team": name,
        "defense_team": opp,
        "offense_division": "FBS",
        "defense_division": "FBS",
        "label": "RED-ZONE EDGE" if adjustment > 0 else "RED-ZONE SUPPRESSION" if adjustment < 0 else "BALANCED",
        "points_adjustment": adjustment,
        "coverage": 1.0,
        "sample_factor": 0.75,
        "offense": {
            "ready": True,
            "touchdown_rate": 0.70,
            "scoring_rate": 0.90,
            "points_per_trip": 5.8,
            "attempts": 10,
        },
        "defense": {
            "ready": True,
            "touchdown_rate": 0.55,
            "scoring_rate": 0.82,
            "points_per_trip": 4.9,
            "attempts": 11,
        },
    }


def _engine(a=0.75, h=-0.25):
    return {
        "ready": True,
        "model_ready": True,
        "away_offense": _side("Florida A&M", "Miami", a),
        "home_offense": _side("Miami", "Florida A&M", h),
    }


def test_readable_step6_explains_direct_red_zone_output():
    html = readable.render_step6(_engine())
    assert "STEP 6 • RED ZONE" in html
    assert "Florida A&amp;M" in html
    assert "Touchdown" in html or "TD rate" in html
    assert "70.0%" in html
    assert "5.80" in html
    assert "RED ZONE FAVORS MORE SCORING" in html
    assert "sportsbook projection weight: <b>0.0%</b>" in html


def test_readable_step6_uses_only_existing_adjustment_sign_for_verdict():
    assert "RED ZONE FAVORS MORE SCORING" in readable.render_step6(_engine(0.2, 0.1))
    assert "RED ZONE FAVORS FEWER POINTS" in readable.render_step6(_engine(-0.2, -0.1))
    assert "RED ZONE IS NEUTRAL" in readable.render_step6(_engine(0.2, -0.2))


def test_readable_step6_fails_closed_when_not_ready():
    html = readable.render_step6({"model_ready": False, "reason": "direct NCAA red-zone defense row is unavailable"})
    assert "GATED" in html
    assert "direct NCAA red-zone defense row is unavailable" in html
    assert "falls back safely" in html


def test_v23_is_additive_over_v22_and_preserves_steps4_5():
    assert page.FROZEN_PAGE == "cfb_over_under_clean_page_v22"
    assert page.ACTIVE_MARKET_ADAPTER == page.frozen_page.ACTIVE_MARKET_ADAPTER
    assert page.ACTIVE_MARKET_INTELLIGENCE == page.frozen_page.ACTIVE_MARKET_INTELLIGENCE
    assert page._RENDER_V23.__code__ is page.frozen_page._RENDER_V22.__code__
    assert page._PRESENTATION_PROXY._model_step(4, "PACE", {}) == page._BASE_PRESENTATION._model_step(4, "PACE", {})
    assert page._PRESENTATION_PROXY._model_step(5, "EXPLOSIVE", {}) == page._BASE_PRESENTATION._model_step(5, "EXPLOSIVE", {})
    assert "STEP 6 • RED ZONE" in page._PRESENTATION_PROXY._model_step(6, "RED ZONE", _engine())


def test_v23_preserves_all_production_markers(monkeypatch):
    seen = []
    monkeypatch.setattr(page.st, "caption", lambda body, *a, **k: seen.append(str(body)))
    page._StreamlitV23Proxy().caption("🟢 CFB O/U • CLEAN PAGE V20 ACTIVE")
    marker = seen[0]
    for token in (
        "CFB O/U • CLEAN PAGE V20 ACTIVE",
        "STEP 6 MARKET INTELLIGENCE LIVE",
        "FRESHNESS FIREWALL ACTIVE",
        "0.0% PROJECTION INFLUENCE",
        "FROZEN PROJECTION MATH PRESERVED",
        "READABLE STEP 4 PACE ACTIVE",
        "READABLE STEP 5 EXPLOSIVE ACTIVE",
        "READABLE STEP 6 RED ZONE ACTIVE",
    ):
        assert token in marker


def test_step6_readable_layer_contains_no_projection_reimplementation():
    source = inspect.getsource(readable) + inspect.getsource(page)
    for token in (
        "build_red_zone_engine(", "apply_to_raw(", "project_matchup(",
        "runtime_slate.analyze_game(", "rank_slate(",
    ):
        assert token not in source
    assert readable.PROJECTION_WEIGHT == 0.0
    assert readable.MAY_MODIFY_PROJECTION is False
