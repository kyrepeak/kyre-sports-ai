"""Regression tests for readable CFB O/U Step 8 turnover-volatility presentation."""
from __future__ import annotations

import inspect

import cfb_over_under_clean_page_v25 as page
import cfb_over_under_step8_readable_v1 as readable


def _metrics(giveaways=1.2, takeaways=1.4):
    return {
        "ready": True,
        "games": 3,
        "turnovers_gained": 4,
        "turnovers_lost": 3,
        "turnover_margin": 1,
        "giveaways_per_game": giveaways,
        "takeaways_per_game": takeaways,
    }


def _side(name, opp, signal):
    return {
        "offense_team": name,
        "defense_team": opp,
        "offense_division": "FBS",
        "defense_division": "FBS",
        "label": "HIGH TURNOVER VOLATILITY" if signal > 0 else "LOW TURNOVER VOLATILITY" if signal < 0 else "NEUTRAL TURNOVER VOLATILITY",
        "shrunk_signal": signal,
        "coverage": 1.0,
        "sample_factor": 0.5,
        "expected_giveaways_per_game": 1.3,
        "baseline_expected_giveaways_per_game": 1.0,
        "offense": _metrics(),
        "defense": _metrics(),
    }


def _engine(sigma=0.25):
    return {
        "ready": True,
        "model_ready": True,
        "away_offense": _side("Florida A&M", "Miami", 0.2),
        "home_offense": _side("Miami", "Florida A&M", -0.1),
        "coverage": 1.0,
        "sigma_adjustment": sigma,
        "projected_total_turnover_weight": 0.0,
        "analysis_line_turnover_weight": 0.0,
    }


def test_readable_step8_explains_direct_turnover_evidence():
    html = readable.render_step8(_engine())
    assert "STEP 8 • TURNOVER VOLATILITY" in html
    assert "Florida A&amp;M" in html
    assert "Giveaways/game" in html
    assert "Takeaways/game" in html
    assert "Expected giveaways" in html
    assert "TURNOVERS RAISE GAME VOLATILITY" in html
    assert "Projected total remains unchanged by Step 8" in html
    assert "sportsbook projection weight: <b>0.0%</b>" in html


def test_readable_step8_verdict_uses_only_existing_sigma_adjustment_sign():
    assert "TURNOVERS RAISE GAME VOLATILITY" in readable.render_step8(_engine(0.2))
    assert "TURNOVERS LOWER GAME VOLATILITY" in readable.render_step8(_engine(-0.2))
    assert "TURNOVER VOLATILITY IS NEUTRAL" in readable.render_step8(_engine(0.0))


def test_readable_step8_fails_closed_when_not_ready():
    html = readable.render_step8({"model_ready": False, "reason": "direct NCAA turnover row is unavailable"})
    assert "GATED" in html
    assert "direct NCAA turnover row is unavailable" in html
    assert "instead of inventing turnover or field-position data" in html


def test_v25_is_additive_over_v24_and_preserves_steps4_7():
    assert page.FROZEN_PAGE == "cfb_over_under_clean_page_v24"
    assert page.ACTIVE_MARKET_ADAPTER == page.frozen_page.ACTIVE_MARKET_ADAPTER
    assert page.ACTIVE_MARKET_INTELLIGENCE == page.frozen_page.ACTIVE_MARKET_INTELLIGENCE
    assert page._RENDER_V25.__code__ is page.frozen_page._RENDER_V24.__code__
    for step, title in ((4, "PACE"), (5, "EXPLOSIVE"), (6, "RED ZONE"), (7, "THIRD DOWN")):
        assert page._PRESENTATION_PROXY._model_step(step, title, {}) == page._BASE_PRESENTATION._model_step(step, title, {})
    assert "STEP 8 • TURNOVER VOLATILITY" in page._PRESENTATION_PROXY._model_step(8, "TURNOVER", _engine())


def test_v25_preserves_production_safety_markers(monkeypatch):
    seen = []
    monkeypatch.setattr(page.st, "caption", lambda body, *a, **k: seen.append(str(body)))
    page._StreamlitV25Proxy().caption("🟢 CFB O/U • CLEAN PAGE V20 ACTIVE")
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
        "READABLE STEP 8 TURNOVER VOLATILITY ACTIVE",
    ):
        assert token in marker


def test_step8_readable_layer_contains_no_engine_recomputation():
    source = inspect.getsource(readable) + inspect.getsource(page)
    for token in (
        "build_turnover_engine(", "apply_to_raw(", "project_matchup(",
        "runtime_slate.analyze_game(", "rank_slate(",
    ):
        assert token not in source
    assert readable.PROJECTION_WEIGHT == 0.0
    assert readable.MAY_MODIFY_PROJECTION is False
