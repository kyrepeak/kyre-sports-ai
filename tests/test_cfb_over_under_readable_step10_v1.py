"""Regression checks for the readable CFB O/U Step 10 history adapter."""
from __future__ import annotations

import inspect

import cfb_over_under_clean_page_v27 as page
import cfb_over_under_step10_readable_v1 as readable


def _engine(**overrides):
    value = {
        "model_ready": True,
        "coverage": 1.0,
        "away_team": "Florida A&M",
        "home_team": "Miami (FL)",
        "away_espn_team_id": "50",
        "home_espn_team_id": "2390",
        "away_recent": {
            "games": 8,
            "avg_points_for": 27.1,
            "avg_points_against": 20.2,
            "avg_combined_total": 47.3,
            "wins": 5,
            "losses": 3,
        },
        "home_recent": {
            "games": 8,
            "avg_points_for": 38.4,
            "avg_points_against": 18.6,
            "avg_combined_total": 57.0,
            "wins": 7,
            "losses": 1,
        },
        "head_to_head": {
            "meetings": 1,
            "avg_combined_total": 65.0,
            "latest": {
                "date": "2024-09-08T01:00:00Z",
                "points_for": 9,
                "points_against": 56,
            },
        },
        "future_event_leakage_allowed": False,
        "target_event_excluded": True,
        "historical_roster_continuity_certified": False,
        "opponent_strength_adjusted_history": False,
    }
    value.update(overrides)
    return value


def test_readable_step10_renders_verified_context_and_zero_weight_audit():
    html = readable.render_step10(_engine())
    assert "STEP 10 • HISTORICAL MATCHUP CONTEXT" in html
    assert "Florida A&amp;M" in html
    assert "Miami (FL)" in html
    assert "65.0" in html
    assert "2024-09-08" in html
    assert "Projected total remains unchanged by Step 10" in html
    assert "sportsbook projection weight: <b>0.0%</b>" in html
    assert "no fuzzy matching" in html
    assert "no synthetic IDs" in html
    assert "future-event leakage <strong>BLOCKED</strong>" in html


def test_readable_step10_exposes_limited_h2h_without_recent_math():
    html = readable.render_step10(_engine(
        model_ready=False,
        context_ready=True,
        reason="recent ESPN history is incomplete",
        away_recent={},
        home_recent={},
        head_to_head={},
        all_time_head_to_head={
            "ready": True,
            "meetings": 4,
            "avg_combined_total": 54.5,
            "source": "Winsipedia",
            "latest": {"date": "2024-09-08", "away_points": 9, "home_points": 56},
        },
    ))
    assert "LIMITED" in html
    assert "Winsipedia" in html
    assert "recent ESPN history is incomplete" in html
    assert "Projection mutation: <b>OFF</b>" in html


def test_readable_step10_fails_closed_without_evidence():
    html = readable.render_step10({
        "model_ready": False,
        "reason": "verified completed history is unavailable",
    })
    assert "GATED" in html
    assert "HISTORICAL CONTEXT GATED" in html
    assert "No verified historical matchup evidence is displayed" in html
    assert "projected-total adjustment: <b>0.00 pts</b>" in html


def test_v27_is_additive_over_v26_and_replaces_only_step10():
    assert page.FROZEN_PAGE == "cfb_over_under_clean_page_v26"
    assert page.ACTIVE_MARKET_ADAPTER == page.frozen_page.ACTIVE_MARKET_ADAPTER
    assert page.ACTIVE_MARKET_INTELLIGENCE == page.frozen_page.ACTIVE_MARKET_INTELLIGENCE
    assert page._RENDER_V27.__code__ is page.frozen_page._RENDER_V26.__code__
    for step, title in (
        (4, "PACE"),
        (5, "EXPLOSIVE"),
        (6, "RED ZONE"),
        (7, "THIRD DOWN"),
        (8, "TURNOVER"),
        (9, "ENVIRONMENT"),
    ):
        assert page._PRESENTATION_PROXY._model_step(
            step, title, {}
        ) == page._BASE_PRESENTATION._model_step(step, title, {})
    assert "STEP 10 • HISTORICAL MATCHUP CONTEXT" in page._PRESENTATION_PROXY._model_step(
        10, "HISTORY", _engine()
    )


def test_v27_marker_preserves_prior_safety_contract(monkeypatch):
    seen = []
    monkeypatch.setattr(page.st, "caption", lambda body, *a, **k: seen.append(str(body)))
    page._StreamlitV27Proxy().caption("🟢 CFB O/U • CLEAN PAGE V20 ACTIVE")
    marker = seen[0]
    for token in (
        "CFB O/U • CLEAN PAGE V20 ACTIVE",
        "STEP 6 MARKET INTELLIGENCE LIVE",
        "FRESHNESS FIREWALL ACTIVE",
        "0.0% PROJECTION INFLUENCE",
        "FROZEN PROJECTION MATH PRESERVED",
        "READABLE STEP 9 GAME-DAY ENVIRONMENT ACTIVE",
        "READABLE STEP 10 HISTORICAL MATCHUP ACTIVE",
    ):
        assert token in marker


def test_readable_step10_layer_contains_no_engine_recomputation():
    source = inspect.getsource(readable) + inspect.getsource(page)
    for token in (
        "build_history_engine(",
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
