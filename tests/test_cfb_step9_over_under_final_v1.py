"""Regression checks for College Football Step 9 Over/Under Final V1."""
from __future__ import annotations

import cfb_over_under_final_v1 as final


def _game():
    return {
        "identity_key": "ncaa:123",
        "away_team": "Oklahoma",
        "home_team": "Michigan",
    }


def _raw(
    over=0.61,
    under=0.39,
    push=0.0,
    reliability=0.86,
    coverage=0.90,
):
    return {
        "ready": True,
        "analysis_line": 50.5,
        "projected_total": 55.2,
        "projected_away_points": 26.0,
        "projected_home_points": 29.2,
        "over_probability": over,
        "under_probability": under,
        "push_probability": push,
        "reliability": reliability,
        "feature_coverage": {"score": coverage},
        "confidence": "HIGH",
    }


def test_qualified_over_selection_is_ready_and_price_independent():
    out = final.synthesize(_game(), _raw())

    assert out["ready"] is True
    assert out["selection"] == "OVER"
    assert out["selection_ready"] is True
    assert out["rank_eligible"] is True
    assert out["selection_probability"] == 0.61
    assert out["analysis_line_projection_weight"] == 0.0
    assert out["sportsbook_input_used"] is False
    assert out["market_price_used"] is False
    assert out["market_probability_used"] is False
    assert out["edge_or_ev_used"] is False
    assert out["monte_carlo_used"] is False


def test_under_can_qualify():
    out = final.synthesize(
        _game(),
        _raw(over=0.40, under=0.60, reliability=0.84, coverage=0.86),
    )

    assert out["selection"] == "UNDER"
    assert out["selection_ready"] is True
    assert out["candidate_side"] == "UNDER"
    assert out["selection_probability"] == 0.60


def test_probability_reliability_or_coverage_can_force_pass():
    cases = [
        _raw(over=0.54, under=0.46, reliability=0.90, coverage=0.90),
        _raw(over=0.60, under=0.40, reliability=0.70, coverage=0.90),
        _raw(over=0.60, under=0.40, reliability=0.90, coverage=0.65),
    ]

    for raw in cases:
        out = final.synthesize(_game(), raw)
        assert out["ready"] is True
        assert out["selection"] == "PASS"
        assert out["selection_ready"] is False
        assert out["rank_eligible"] is False
        assert out["grade"] == "PASS"


def test_raw_not_ready_fails_closed():
    out = final.synthesize(
        _game(),
        {"ready": False, "reasons": ["team-data quality is CHECK"]},
    )

    assert out["ready"] is False
    assert out["selection"] == "PASS"
    assert out["rank_eligible"] is False
    assert "team-data quality is CHECK" in out["reasons"]


def test_rank_slate_only_includes_qualified_and_sorts_probability_first():
    rows = [
        {
            "game": {"identity_key": "a", "kickoff_iso": "2026-09-12T12:00:00-04:00"},
            "final": {
                "ready": True,
                "rank_eligible": True,
                "selection_probability": 0.58,
                "reliability": 0.90,
                "feature_coverage": 0.90,
            },
        },
        {
            "game": {"identity_key": "b", "kickoff_iso": "2026-09-12T13:00:00-04:00"},
            "final": {
                "ready": True,
                "rank_eligible": True,
                "selection_probability": 0.64,
                "reliability": 0.80,
                "feature_coverage": 0.80,
            },
        },
        {
            "game": {"identity_key": "c", "kickoff_iso": "2026-09-12T14:00:00-04:00"},
            "final": {
                "ready": True,
                "rank_eligible": False,
                "selection_probability": 0.70,
                "reliability": 0.95,
                "feature_coverage": 0.95,
            },
        },
    ]

    ranked = final.rank_slate(rows, limit=5)

    assert [row["game"]["identity_key"] for row in ranked] == ["b", "a"]
    assert [row["rank"] for row in ranked] == [1, 2]


def test_grade_thresholds_are_transparent():
    strong = final.synthesize(
        _game(),
        _raw(over=0.64, under=0.36, reliability=0.90, coverage=0.90),
    )
    solid = final.synthesize(
        _game(),
        _raw(over=0.59, under=0.41, reliability=0.80, coverage=0.80),
    )
    qualified = final.synthesize(
        _game(),
        _raw(over=0.56, under=0.44, reliability=0.80, coverage=0.80),
    )

    assert (strong["grade"], strong["tier"]) == ("A", "STRONG")
    assert (solid["grade"], solid["tier"]) == ("B", "SOLID")
    assert (qualified["grade"], qualified["tier"]) == ("C", "QUALIFIED")
