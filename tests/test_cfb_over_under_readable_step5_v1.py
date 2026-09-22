"""Regression tests for readable CFB O/U Step 5 explosive presentation."""
from __future__ import annotations

import inspect

import cfb_over_under_clean_page_v22 as page
import cfb_over_under_step5_readable_v1 as readable


def _engine(away_adj=0.80, home_adj=0.55):
    return {
        "model_ready": True,
        "away_offense": {
            "offense_team": "Florida A&M",
            "defense_team": "Miami",
            "label": "EXPLOSIVE",
            "points_adjustment": away_adj,
            "coverage": 1.0,
            "sample_factor": 0.70,
            "pass": {
                "ready": True,
                "signal": 0.42,
                "offense_yards_per_attempt": 8.1,
                "defense_yards_per_attempt_allowed": 6.7,
                "offense_yards_per_completion": 12.4,
                "defense_yards_per_completion_allowed": 10.9,
            },
            "rush": {
                "ready": True,
                "signal": 0.25,
                "offense_yards_per_rush": 5.2,
                "defense_yards_per_rush_allowed": 4.1,
            },
        },
        "home_offense": {
            "offense_team": "Miami",
            "defense_team": "Florida A&M",
            "label": "FAVORABLE",
            "points_adjustment": home_adj,
            "coverage": 1.0,
            "sample_factor": 0.80,
            "pass": {
                "ready": True,
                "signal": 0.31,
                "offense_yards_per_attempt": 9.0,
                "defense_yards_per_attempt_allowed": 7.5,
                "offense_yards_per_completion": 13.2,
                "defense_yards_per_completion_allowed": 11.8,
            },
            "rush": {
                "ready": True,
                "signal": 0.18,
                "offense_yards_per_rush": 5.0,
                "defense_yards_per_rush_allowed": 4.6,
            },
        },
    }


def test_readable_step5_explains_existing_explosive_output():
    html = readable.render_step5(_engine())
    assert "STEP 5 • EXPLOSIVE PLAY PROFILE" in html
    assert "Florida A&amp;M offense vs Miami defense" in html
    assert "Miami offense vs Florida A&amp;M defense" in html
    assert "Offense Y/A 8.10 vs allowed 6.70" in html
    assert "Offense Y/Rush 5.20 vs allowed 4.10" in html
    assert "EXPLOSIVE PROFILE FAVORS MORE SCORING POTENTIAL" in html
    assert "sportsbook projection weight: <b>0.0%</b>" in html


def test_readable_step5_verdict_uses_existing_adjustment_sign_only():
    assert "MORE SCORING POTENTIAL" in readable.render_step5(_engine(0.20, 0.10))
    assert "FEWER SCORING OPPORTUNITIES" in readable.render_step5(_engine(-0.20, -0.10))
    assert "EXPLOSIVE PROFILE IS NEUTRAL" in readable.render_step5(_engine(0.20, -0.20))


def test_readable_step5_fails_closed_when_engine_not_ready():
    html = readable.render_step5({"model_ready": False, "reason": "explosive evidence unavailable"})
    assert "GATED" in html
    assert "explosive evidence unavailable" in html
    assert "falls back safely" in html


def test_v22_is_additive_over_certified_v21():
    assert page.FROZEN_PAGE == "cfb_over_under_clean_page_v21"
    assert page.ACTIVE_MARKET_ADAPTER == page.frozen_page.ACTIVE_MARKET_ADAPTER
    assert page.ACTIVE_MARKET_INTELLIGENCE == page.frozen_page.ACTIVE_MARKET_INTELLIGENCE
    assert page._RENDER_V22.__code__ is page.frozen_page._RENDER_V21.__code__


def test_v22_preserves_readable_step4_and_replaces_only_step5():
    html5 = page._PRESENTATION_PROXY._model_step(5, "EXPLOSIVE PLAY PROFILE", _engine())
    assert "EXPLOSIVE VERDICT" in html5

    pace = {
        "model_ready": True,
        "pace_label": "FAST",
        "away": {},
        "home": {},
        "expected_combined_plays": 140,
        "division_baseline_combined_plays": 136,
        "total_points_adjustment": 1.0,
        "coverage": 1.0,
    }
    html4 = page._PRESENTATION_PROXY._model_step(4, "PACE / EXPECTED POSSESSIONS", pace)
    assert "PACE VERDICT" in html4

    html6 = page._PRESENTATION_PROXY._model_step(6, "RED ZONE", {})
    frozen6 = page._BASE_PRESENTATION._model_step(6, "RED ZONE", {})
    assert html6 == frozen6


def test_v22_preserves_all_existing_safety_markers(monkeypatch):
    seen = []
    monkeypatch.setattr(page.st, "caption", lambda body, *a, **k: seen.append(str(body)))
    page._StreamlitV22Proxy().caption("🟢 CFB O/U • CLEAN PAGE V20 ACTIVE")
    marker = seen[0]
    assert "STEP 6 MARKET INTELLIGENCE LIVE" in marker
    assert "FRESHNESS FIREWALL ACTIVE" in marker
    assert "0.0% PROJECTION INFLUENCE" in marker
    assert "FROZEN PROJECTION MATH PRESERVED" in marker
    assert "READABLE STEP 4 PACE ACTIVE" in marker
    assert "READABLE STEP 5 EXPLOSIVE ACTIVE" in marker


def test_readable_step5_and_v22_do_not_call_projection_engines():
    source = inspect.getsource(readable) + inspect.getsource(page)
    for token in (
        "runtime_slate.analyze_game(",
        "project_matchup(",
        "build_explosive_engine(",
        "apply_to_raw(",
        "rank_slate(",
    ):
        assert token not in source
    assert readable.PROJECTION_WEIGHT == 0.0
    assert readable.MAY_MODIFY_PROJECTION is False
