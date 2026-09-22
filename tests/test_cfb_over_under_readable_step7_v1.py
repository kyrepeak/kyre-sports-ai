"""Regression tests for readable CFB O/U Step 7 third-down presentation."""
from __future__ import annotations

import inspect

import cfb_over_under_clean_page_v24 as page
import cfb_over_under_step7_readable_v1 as readable


def _side(name, opp, adjustment):
    return {
        "offense_team": name,
        "defense_team": opp,
        "offense_division": "FBS",
        "defense_division": "FBS",
        "label": "DRIVE-SUSTAIN EDGE" if adjustment > 0 else "DRIVE-SUPPRESSION" if adjustment < 0 else "BALANCED",
        "points_adjustment": adjustment,
        "coverage": 1.0,
        "sample_factor": 0.75,
        "matchup_conversion_rate": 0.42,
        "expected_third_down_attempts_per_game": 13.0,
        "expected_third_down_conversions_per_game": 5.46,
        "offense": {
            "ready": True,
            "conversion_rate": 0.46,
            "attempts": 30,
            "conversions": 14,
            "attempts_per_game": 15.0,
        },
        "defense": {
            "ready": True,
            "conversion_rate": 0.38,
            "attempts": 22,
            "conversions": 8,
            "attempts_per_game": 11.0,
        },
    }


def _engine(a=0.50, h=-0.20):
    return {
        "ready": True,
        "model_ready": True,
        "away_offense": _side("Florida A&M", "Miami", a),
        "home_offense": _side("Miami", "Florida A&M", h),
    }


def test_readable_step7_explains_direct_third_down_output():
    html = readable.render_step7(_engine())
    assert "STEP 7 • THIRD DOWN" in html
    assert "Florida A&amp;M" in html
    assert "46.0%" in html
    assert "30" in html
    assert "42.0%" in html
    assert "THIRD DOWN FAVORS LONGER DRIVES / MORE SCORING CHANCES" in html
    assert "sportsbook projection weight: <b>0.0%</b>" in html


def test_readable_step7_uses_only_existing_adjustment_sign_for_verdict():
    assert "THIRD DOWN FAVORS LONGER DRIVES / MORE SCORING CHANCES" in readable.render_step7(_engine(0.2, 0.1))
    assert "THIRD DOWN FAVORS MORE DRIVE STOPS / FEWER SCORING CHANCES" in readable.render_step7(_engine(-0.2, -0.1))
    assert "THIRD DOWN IS NEUTRAL" in readable.render_step7(_engine(0.2, -0.2))


def test_readable_step7_fails_closed_when_not_ready():
    html = readable.render_step7({"model_ready": False, "reason": "direct NCAA third-down defense row is unavailable"})
    assert "GATED" in html
    assert "direct NCAA third-down defense row is unavailable" in html
    assert "falls back safely" in html


def test_v24_is_additive_over_v23_and_preserves_steps4_6():
    assert page.FROZEN_PAGE == "cfb_over_under_clean_page_v23"
    assert page.ACTIVE_MARKET_ADAPTER == page.frozen_page.ACTIVE_MARKET_ADAPTER
    assert page.ACTIVE_MARKET_INTELLIGENCE == page.frozen_page.ACTIVE_MARKET_INTELLIGENCE
    assert page._RENDER_V24.__code__ is page.frozen_page._RENDER_V23.__code__
    for step, title in ((4, "PACE"), (5, "EXPLOSIVE"), (6, "RED ZONE")):
        assert page._PRESENTATION_PROXY._model_step(step, title, {}) == page._BASE_PRESENTATION._model_step(step, title, {})
    assert "STEP 7 • THIRD DOWN" in page._PRESENTATION_PROXY._model_step(7, "THIRD DOWN", _engine())


def test_v24_preserves_all_production_markers(monkeypatch):
    seen = []
    monkeypatch.setattr(page.st, "caption", lambda body, *a, **k: seen.append(str(body)))
    page._StreamlitV24Proxy().caption("🟢 CFB O/U • CLEAN PAGE V20 ACTIVE")
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
        "READABLE STEP 7 THIRD DOWN ACTIVE",
    ):
        assert token in marker


def test_step7_readable_layer_contains_no_projection_reimplementation():
    source = inspect.getsource(readable) + inspect.getsource(page)
    for token in (
        "build_third_down_engine(", "apply_to_raw(", "project_matchup(",
        "runtime_slate.analyze_game(", "rank_slate(",
    ):
        assert token not in source
    assert readable.PROJECTION_WEIGHT == 0.0
    assert readable.MAY_MODIFY_PROJECTION is False
