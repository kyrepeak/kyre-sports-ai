"""Regression tests for readable CFB O/U Step 4 pace presentation."""
from __future__ import annotations

import inspect

import cfb_over_under_clean_page_v21 as page
import cfb_over_under_step4_readable_v1 as readable


def _pace(adjustment=1.25):
    return {
        "model_ready": True,
        "pace_label": "FAST",
        "away": {
            "team": "Florida A&M",
            "division": "FCS",
            "plays_per_game": 67.2,
            "seconds_per_offensive_play": 27.4,
            "pace_index": 1.03,
        },
        "home": {
            "team": "Miami",
            "division": "FBS",
            "plays_per_game": 72.8,
            "seconds_per_offensive_play": 25.8,
            "pace_index": 1.08,
        },
        "expected_combined_plays": 142.0,
        "division_baseline_combined_plays": 136.5,
        "direct_possessions_available": False,
        "expected_combined_possessions": None,
        "total_points_adjustment": adjustment,
        "historical_combined_plays_per_game": 140.1,
        "clock_implied_combined_plays": 143.2,
        "sample_factor": 0.75,
        "coverage": 1.0,
    }


def test_readable_step4_explains_existing_pace_output():
    html = readable.render_step4(_pace())
    assert "STEP 4 • PACE / EXPECTED POSSESSIONS" in html
    assert "Florida A&amp;M" in html
    assert "Miami" in html
    assert "142.0" in html
    assert "136.5" in html
    assert "+1.25" in html
    assert "PACE FAVORS MORE SCORING OPPORTUNITY" in html
    assert "sportsbook projection weight: <b>0.0%</b>" in html


def test_readable_step4_uses_adjustment_sign_only_for_plain_language_verdict():
    assert "PACE FAVORS MORE SCORING OPPORTUNITY" in readable.render_step4(_pace(0.25))
    assert "PACE FAVORS FEWER SCORING OPPORTUNITIES" in readable.render_step4(_pace(-0.25))
    assert "PACE IS NEUTRAL" in readable.render_step4(_pace(0.0))


def test_readable_step4_fails_closed_when_engine_not_ready():
    html = readable.render_step4({"model_ready": False, "reason": "pace evidence unavailable"})
    assert "GATED" in html
    assert "pace evidence unavailable" in html
    assert "falls back safely" in html


def test_v21_is_additive_over_certified_v20():
    assert page.FROZEN_PAGE == "cfb_over_under_clean_page_v20"
    assert page.ACTIVE_MARKET_ADAPTER == page.frozen_page.ACTIVE_MARKET_ADAPTER
    assert page.ACTIVE_MARKET_INTELLIGENCE == page.frozen_page.ACTIVE_MARKET_INTELLIGENCE
    assert page._RENDER_V21.__code__ is page.frozen_page._RENDER_V20.__code__


def test_v21_replaces_only_generic_step4_presentation():
    sentinel = {"model_ready": True, "total_points_adjustment": 0.0}
    html4 = page._PRESENTATION_PROXY._model_step(4, "PACE / EXPECTED POSSESSIONS", sentinel)
    assert "PACE VERDICT" in html4

    html5 = page._PRESENTATION_PROXY._model_step(5, "EXPLOSIVE PLAY PROFILE", {})
    frozen5 = page._BASE_PRESENTATION._model_step(5, "EXPLOSIVE PLAY PROFILE", {})
    assert html5 == frozen5


def test_v21_preserves_step6_production_markers_and_adds_readable_marker(monkeypatch):
    seen = []
    monkeypatch.setattr(page.st, "caption", lambda body, *a, **k: seen.append(str(body)))
    proxy = page._StreamlitV21Proxy()
    proxy.caption("🟢 CFB O/U • CLEAN PAGE V18 ACTIVE • LIVE ODDS CONNECTED • FROZEN PROJECTION MATH PRESERVED")
    marker = seen[0]
    assert "CFB O/U • CLEAN PAGE V20 ACTIVE" in marker
    assert "STEP 6 MARKET INTELLIGENCE LIVE" in marker
    assert "FRESHNESS FIREWALL ACTIVE" in marker
    assert "0.0% PROJECTION INFLUENCE" in marker
    assert "FROZEN PROJECTION MATH PRESERVED" in marker
    assert "READABLE STEP 4 PACE ACTIVE" in marker


def test_readable_step4_and_v21_do_not_call_projection_engines():
    source = inspect.getsource(readable) + inspect.getsource(page)
    forbidden = (
        "runtime_slate.analyze_game(",
        "project_matchup(",
        "build_pace_engine(",
        "apply_to_raw(",
        "rank_slate(",
    )
    for token in forbidden:
        assert token not in source
    assert readable.PROJECTION_WEIGHT == 0.0
    assert readable.MAY_MODIFY_PROJECTION is False
