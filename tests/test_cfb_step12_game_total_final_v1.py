"""Regression checks for College Football Step 12 Game Total Final V1."""
from __future__ import annotations

import cfb_game_total_final_v1 as final


def _game(identity="g1"):
    return {
        "identity_key": identity,
        "away_team": "Oklahoma",
        "home_team": "Michigan",
        "kickoff_iso": "2026-09-12T19:30:00-04:00",
    }


def _raw(rel=0.86, cov=0.90, within7=0.40):
    return {
        "ready": True,
        "projected_combined_total": 54.2,
        "median_total": 54,
        "mode_total": 54,
        "mode_probability": 0.031,
        "structural_interval_80": {"low": 37, "high": 72},
        "structural_interval_90": {"low": 32, "high": 77},
        "percentiles": {"p10": 37, "p25": 45, "p50": 54, "p75": 63, "p90": 72},
        "standard_bands": [
            {"label": "0-39", "low": 0, "high": 39, "probability": 0.16},
            {"label": "40-49", "low": 40, "high": 49, "probability": 0.22},
            {"label": "50-59", "low": 50, "high": 59, "probability": 0.28},
            {"label": "60-69", "low": 60, "high": 69, "probability": 0.22},
            {"label": "70+", "low": 70, "high": 140, "probability": 0.12},
        ],
        "around_projection": {
            "within_7": {"low": 47, "high": 61, "probability": within7},
        },
        "reliability": rel,
        "feature_coverage": {"score": cov},
        "confidence": "HIGH",
    }


def test_final_forecast_qualifies_and_preserves_market_firewall():
    out = final.synthesize(_game(), _raw())

    assert out["ready"] is True
    assert out["forecast_status"] == "QUALIFIED"
    assert out["forecast_ready"] is True
    assert out["rank_eligible"] is True
    assert out["projected_combined_total"] == 54.2
    assert out["core_50_range"] == {"low": 45, "high": 63}
    assert out["most_likely_band"]["label"] == "50-59"
    assert out["final_forecast_active"] is True
    assert out["betting_pick_active"] is False
    assert out["sportsbook_input_used"] is False
    assert out["market_price_used"] is False
    assert out["market_probability_used"] is False
    assert out["edge_or_ev_used"] is False
    assert out["monte_carlo_used"] is False


def test_low_reliability_coverage_or_concentration_forces_pass():
    cases = [
        _raw(rel=0.70, cov=0.90, within7=0.40),
        _raw(rel=0.86, cov=0.65, within7=0.40),
        _raw(rel=0.86, cov=0.90, within7=0.25),
    ]

    for raw in cases:
        out = final.synthesize(_game(), raw)
        assert out["ready"] is True
        assert out["forecast_status"] == "PASS"
        assert out["rank_eligible"] is False
        assert out["grade"] == "PASS"


def test_raw_not_ready_fails_closed():
    out = final.synthesize(
        _game(),
        {"ready": False, "reasons": ["team-data quality is CHECK"]},
    )
    assert out["ready"] is False
    assert out["forecast_status"] == "PASS"
    assert out["rank_eligible"] is False
    assert "team-data quality is CHECK" in out["reasons"]


def test_strength_formula_is_deterministic():
    raw = _raw(rel=0.80, cov=0.75, within7=0.35)
    out = final.synthesize(_game(), raw)
    expected = 0.45 * 0.80 + 0.35 * 0.75 + 0.20 * 0.35
    assert abs(out["forecast_strength"] - expected) < 1e-12


def test_rank_slate_uses_strength_then_quality():
    rows = [
        {"game": _game("a"), "final": {**final.synthesize(_game("a"), _raw(rel=0.80, cov=0.80, within7=0.35))}},
        {"game": _game("b"), "final": {**final.synthesize(_game("b"), _raw(rel=0.90, cov=0.90, within7=0.45))}},
        {"game": _game("c"), "final": {**final.synthesize(_game("c"), _raw(rel=0.70, cov=0.90, within7=0.45))}},
    ]

    ranked = final.rank_slate(rows, limit=5)
    assert [row["game"]["identity_key"] for row in ranked] == ["b", "a"]
    assert [row["rank"] for row in ranked] == [1, 2]
