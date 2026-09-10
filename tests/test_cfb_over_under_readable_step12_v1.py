"""Regression checks for the readable CFB O/U Step 12 final-certification adapter."""
from __future__ import annotations

import inspect

import cfb_over_under_clean_page_v29 as page
import cfb_over_under_step12_readable_v1 as readable


def _certificate(**overrides):
    value = {
        "status": "CERTIFIED",
        "certified": True,
        "integrity_passed": True,
        "certified_upgrade_steps": list(range(1, 13)),
        "completed_upgrade_count": 12,
        "checks_passed": 17,
        "checks_failed": 0,
        "checks_skipped": 0,
        "projection_fingerprint": "abc123def4567890",
        "projection_math_changed": False,
        "selection_math_changed": False,
        "structural_sigma_changed": False,
        "reliability_changed": False,
        "qualification_thresholds_changed": False,
        "sportsbook_input_used": False,
        "market_price_used": False,
        "market_probability_used": False,
        "edge_or_ev_used": False,
        "monte_carlo_used": False,
    }
    value.update(overrides)
    return value


def _result(**overrides):
    value = {
        "game": {
            "identity_key": "401858213",
            "identity_verified": True,
            "date_matches_query": True,
        },
        "raw": {
            "ready": True,
            "upgrade_step11_applied": False,
        },
        "final": {"ready": True},
        "certification": _certificate(),
    }
    value.update(overrides)
    return value


def test_readable_step12_renders_certified_stack_and_frozen_contract():
    html = readable.render_step12(_result())
    assert "STEP 12 • FINAL CERTIFICATION" in html
    assert "CERTIFIED" in html
    assert "12/12 upgrade stack checked" in html
    assert "abc123def4567890" in html
    assert "Projection math changed: <strong>NO</strong>" in html
    assert "selection math changed: <strong>NO</strong>" in html
    assert "Sportsbook input used: <strong>NO</strong>" in html
    assert "analysis-line/direct-selection weights: <strong>0.0%</strong>" in html
    assert "official ESPN event IDs only" in html
    assert "no fuzzy matching" in html
    assert "no synthetic IDs" in html
    assert "401858213" in html


def test_readable_step12_data_gated_is_safe_and_fail_closed():
    html = readable.render_step12(_result(
        certification=_certificate(
            status="DATA_GATED",
            certified=False,
            checks_passed=10,
            checks_skipped=7,
        ),
        raw={"ready": False},
        final={"ready": False},
    ))
    assert "DATA GATED" in html
    assert "no projection is forced" in html
    assert "raw ready: <strong>NO</strong>" in html


def test_readable_step12_integrity_failure_names_blocker():
    html = readable.render_step12(_result(
        certification=_certificate(
            status="INTEGRITY_FAIL",
            certified=False,
            integrity_passed=False,
            checks_failed=1,
            blocking_failures=[{"name": "probability mass equals 1"}],
        )
    ))
    assert "INTEGRITY FAIL" in html
    assert "FAIL CLOSED" in html
    assert "probability mass equals 1" in html


def test_readable_step12_missing_certificate_makes_no_claim():
    html = readable.render_step12({"raw": {"ready": True}})
    assert "CERTIFICATION PENDING" in html
    assert "no certification claim is made" in html


def test_v29_is_additive_over_v28_and_replaces_only_step12():
    assert page.FROZEN_PAGE == "cfb_over_under_clean_page_v28"
    assert page.ACTIVE_MARKET_ADAPTER == page.frozen_page.ACTIVE_MARKET_ADAPTER
    assert page.ACTIVE_MARKET_INTELLIGENCE == page.frozen_page.ACTIVE_MARKET_INTELLIGENCE
    assert page.ACTIVE_SCHEDULE == page.frozen_page.ACTIVE_SCHEDULE
    assert page.FROZEN_RUNTIME_SLATE == page.frozen_page.FROZEN_RUNTIME_SLATE
    assert page._RENDER_V29.__code__ is page.frozen_page._RENDER_V28.__code__
    assert page._PRESENTATION_PROXY._model_step(11, "FORM", {}) == page._BASE_PRESENTATION._model_step(11, "FORM", {})
    assert "STEP 12 • FINAL CERTIFICATION" in page._PRESENTATION_PROXY._cert_step(_result())


def test_v29_marker_preserves_prior_safety_contract(monkeypatch):
    seen = []
    monkeypatch.setattr(page.st, "caption", lambda body, *a, **k: seen.append(str(body)))
    page._StreamlitV29Proxy().caption("🟢 CFB O/U • CLEAN PAGE V20 ACTIVE")
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
        "READABLE STEP 12 FINAL CERTIFICATION ACTIVE",
    ):
        assert token in marker


def test_readable_step12_layer_contains_no_engine_recomputation():
    source = inspect.getsource(readable) + inspect.getsource(page)
    for token in (
        "certify_result(",
        "analyze_game(",
        "project_matchup(",
        "rank_slate(",
        "build_form_strength_engine(",
    ):
        assert token not in source
    assert readable.PROJECTION_WEIGHT == 0.0
    assert readable.ANALYSIS_LINE_WEIGHT == 0.0
    assert readable.SELECTION_WEIGHT == 0.0
    assert readable.MAY_MODIFY_PROJECTION is False
