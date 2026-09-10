"""Regression checks for the readable CFB O/U Step 11 form-strength adapter."""
from __future__ import annotations

import inspect

import cfb_over_under_clean_page_v28 as page
import cfb_over_under_step11_readable_v1 as readable


def _form(*, games=5, avg_for=31.4, avg_against=20.8, opp_pct=0.62, coverage=1.0):
    return {
        "ready": True,
        "games": games,
        "avg_points_for": avg_for,
        "avg_points_against": avg_against,
        "avg_opponent_win_pct": opp_pct,
        "opponent_record_coverage": coverage,
        "sos_adjusted_points_for": avg_for + 1.75,
        "sos_adjusted_points_against": avg_against - 1.75,
        "sample_factor": 1.0,
        "quality_factor": 0.9,
        "sample": [],
    }


def _engine(**overrides):
    value = {
        "model_ready": True,
        "coverage": 1.0,
        "season": 2026,
        "away_team": "Florida A&M",
        "home_team": "Miami (FL)",
        "away_espn_team_id": "50",
        "home_espn_team_id": "2390",
        "away_form": _form(opp_pct=0.62),
        "home_form": _form(avg_for=38.4, avg_against=18.6, opp_pct=0.48),
        "current_season_only": True,
        "future_event_leakage_allowed": False,
        "target_event_excluded": True,
        "empirical_calibration_claimed": False,
    }
    value.update(overrides)
    return value


def test_readable_step11_renders_current_form_sos_and_zero_weight_audit():
    html = readable.render_step11(_engine())
    assert "STEP 11 • CURRENT FORM + SCHEDULE STRENGTH" in html
    assert "Florida A&amp;M" in html
    assert "Miami (FL)" in html
    assert "CURRENT SEASON ONLY" in html
    assert "Projection blend 18%" in html
    assert "TOUGHER OPPONENT SET" in html
    assert "BALANCED OPPONENT SET" in html
    assert "33.2" in html
    assert "16.9" in html
    assert "sportsbook projection weight: <b>0.0%</b>" in html
    assert "ESPN team IDs 50 / 2390" in html
    assert "future-event leakage <strong>BLOCKED</strong>" in html
    assert "no fuzzy matching" in html
    assert "no synthetic IDs" in html


def test_readable_step11_fails_closed_without_form_evidence():
    html = readable.render_step11({
        "model_ready": False,
        "coverage": 0.0,
        "reason": "sample below minimum",
    })
    assert "FORM GATED" in html
    assert "sample below minimum" in html
    assert "no projection is forced" in html
    assert "Step 10 output remains available" in html


def test_readable_step11_exposes_limited_partial_evidence():
    html = readable.render_step11(_engine(
        model_ready=False,
        coverage=0.5,
        reason="one side is below opponent-record coverage",
        away_form=_form(coverage=0.5),
    ))
    assert "LIMITED" in html
    assert "one side is below opponent-record coverage" in html
    assert "certified engine exposes context" in html


def test_v28_is_additive_over_v27_and_replaces_only_step11():
    assert page.FROZEN_PAGE == "cfb_over_under_clean_page_v27"
    assert page.ACTIVE_MARKET_ADAPTER == page.frozen_page.ACTIVE_MARKET_ADAPTER
    assert page.ACTIVE_MARKET_INTELLIGENCE == page.frozen_page.ACTIVE_MARKET_INTELLIGENCE
    assert page.ACTIVE_SCHEDULE == page.frozen_page.ACTIVE_SCHEDULE
    assert page.FROZEN_RUNTIME_SLATE == page.frozen_page.FROZEN_RUNTIME_SLATE
    assert page._RENDER_V28.__code__ is page.frozen_page._RENDER_V27.__code__
    for step, title in (
        (4, "PACE"),
        (5, "EXPLOSIVE"),
        (6, "RED ZONE"),
        (7, "THIRD DOWN"),
        (8, "TURNOVER"),
        (9, "ENVIRONMENT"),
        (10, "HISTORY"),
    ):
        assert page._PRESENTATION_PROXY._model_step(
            step, title, {}
        ) == page._BASE_PRESENTATION._model_step(step, title, {})
    assert "STEP 11 • CURRENT FORM + SCHEDULE STRENGTH" in (
        page._PRESENTATION_PROXY._model_step(11, "FORM", _engine())
    )


def test_v28_marker_preserves_prior_safety_contract(monkeypatch):
    seen = []
    monkeypatch.setattr(page.st, "caption", lambda body, *a, **k: seen.append(str(body)))
    page._StreamlitV28Proxy().caption("🟢 CFB O/U • CLEAN PAGE V20 ACTIVE")
    marker = seen[0]
    for token in (
        "CFB O/U • CLEAN PAGE V20 ACTIVE",
        "STEP 6 MARKET INTELLIGENCE LIVE",
        "FRESHNESS FIREWALL ACTIVE",
        "0.0% PROJECTION INFLUENCE",
        "FROZEN PROJECTION MATH PRESERVED",
        "READABLE STEP 9 GAME-DAY ENVIRONMENT ACTIVE",
        "READABLE STEP 10 HISTORICAL MATCHUP ACTIVE",
        "READABLE STEP 11 CURRENT FORM + SCHEDULE STRENGTH ACTIVE",
    ):
        assert token in marker


def test_readable_step11_layer_contains_no_engine_recomputation():
    source = inspect.getsource(readable) + inspect.getsource(page)
    for token in (
        "build_form_strength_engine(",
        "apply_to_raw(",
        "runtime_slate.analyze_game(",
        "project_matchup(",
        "rank_slate(",
    ):
        assert token not in source
    assert readable.PROJECTION_WEIGHT == 0.0
    assert readable.ANALYSIS_LINE_WEIGHT == 0.0
    assert readable.SELECTION_WEIGHT == 0.0
    assert readable.MAY_MODIFY_PROJECTION is False
