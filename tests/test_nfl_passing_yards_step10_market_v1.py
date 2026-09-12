from __future__ import annotations

import math
from pathlib import Path

import nfl_passing_yards_market_v1 as market


ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _step9(confidence: str = "HIGH") -> dict:
    return {
        "ready": True,
        "qb_name": "Verified QB",
        "location_yards": 250.0,
        "sigma_yards": 50.0,
        "confidence": confidence,
    }


def test_step10_american_odds_conversion() -> None:
    assert math.isclose(market.american_implied_probability(-110), 110 / 210)
    assert math.isclose(market.american_implied_probability(+120), 100 / 220)
    assert math.isclose(market.american_decimal_odds(-110), 1 + 100 / 110)
    assert math.isclose(market.american_decimal_odds(+120), 2.2)
    assert math.isnan(market.american_implied_probability(0))
    assert math.isnan(market.american_implied_probability(99))


def test_step10_no_vig_two_way_normalizes_to_one() -> None:
    out = market.no_vig_two_way(-110, -110)
    assert out["ready"] is True
    assert math.isclose(out["over_no_vig"], 0.5)
    assert math.isclose(out["under_no_vig"], 0.5)
    assert math.isclose(out["over_no_vig"] + out["under_no_vig"], 1.0)
    assert out["hold"] > 0.0


def test_step10_probability_to_fair_american_odds() -> None:
    assert math.isclose(market.probability_to_american(0.60), -150.0)
    assert math.isclose(market.probability_to_american(0.40), 150.0)
    assert math.isclose(market.probability_to_american(0.50), -100.0)
    assert math.isnan(market.probability_to_american(0.0))
    assert math.isnan(market.probability_to_american(1.0))


def test_step10_ev_formula_is_per_dollar_comparison() -> None:
    assert math.isclose(market.expected_value_per_dollar(0.55, +100), 0.10)
    assert math.isclose(market.expected_value_per_dollar(0.50, -110), -0.04545454545454547)


def test_step10_grade_thresholds_are_conservative_and_deterministic() -> None:
    assert market.grade_value("HIGH", 8.0, 0.11) == ("A", "STRONG VALUE")
    assert market.grade_value("MEDIUM", 6.0, 0.06) == ("B", "VALUE")
    assert market.grade_value("LOW", 3.0, 0.01) == ("C", "WATCH")
    assert market.grade_value("HIGH", 2.0, 0.20) == ("PASS", "PASS")
    assert market.grade_value("CHECK", 20.0, 0.50) == ("PASS", "PASS")


def test_step10_half_yard_two_way_market_can_grade_without_moving_projection() -> None:
    out = market.evaluate_market(
        _step9("HIGH"),
        249.5,
        +120,
        -140,
        source="Verified Book",
        market_timestamp="2026-09-11 20:00 ET",
    )
    assert out["ready"] is True
    assert out["grade_ready"] is True
    assert out["integer_line_push_risk"] is False
    assert out["no_vig_ready"] is True
    assert math.isclose(out["model_over_probability"] + out["model_under_probability"], 1.0)
    assert math.isclose(out["no_vig_over"] + out["no_vig_under"], 1.0)
    assert out["grade"] in {"A", "B", "C", "PASS"}
    assert out["sportsbook_projection_influence"] == 0.0
    assert out["projection_adjustment_yards"] == 0.0
    assert out["stake_sizing_enabled"] is False


def test_step10_integer_line_withholds_grade_for_push_risk() -> None:
    out = market.evaluate_market(_step9(), 250, -110, -110, source="Verified Book")
    assert out["ready"] is True
    assert out["grade_ready"] is False
    assert out["integer_line_push_risk"] is True
    assert out["grade"] == "CHECK"
    assert out["lean"] == "PASS"
    assert "push risk" in out["reason"]


def test_step10_single_side_price_withholds_no_vig_and_final_grade() -> None:
    out = market.evaluate_market(_step9(), 249.5, -110, "", source="Verified Book")
    assert out["ready"] is True
    assert out["grade_ready"] is False
    assert out["no_vig_ready"] is False
    assert out["grade"] == "CHECK"
    assert "both Over and Under prices" in out["reason"]


def test_step10_missing_or_bad_market_fails_closed() -> None:
    out = market.evaluate_market(_step9(), "", "", "")
    assert out["ready"] is False
    assert out["grade_ready"] is False
    assert "market line" in out["reason"]

    out = market.evaluate_market(_step9(), 249.5, 50, -50)
    assert out["ready"] is False
    assert "valid American price" in out["reason"]


def test_step10_requires_certified_step9_distribution() -> None:
    out = market.evaluate_market({"ready": False, "qb_name": "QB"}, 249.5, -110, -110)
    assert out["ready"] is False
    assert "Step 9 distribution" in out["reason"]
    assert out["sportsbook_projection_influence"] == 0.0


def test_router_v90_advances_only_passing_yards_and_preserves_step9() -> None:
    hub = _read("nfl_hub_v29.py")
    router = _read("streamlit_memory_lazy_router_v90.py")
    app = _read("app.py")
    page = _read("nfl_passing_yards_hub_v11.py")
    engine = _read("nfl_passing_yards_market_v1.py")

    assert "import nfl_hub_v28 as base" in hub
    assert "nfl_passing_yards_hub_v11" in hub
    assert "import streamlit_memory_lazy_router_v89 as prior" in router
    assert 'ACTIVE_NFL_HUB = "nfl_hub_v29"' in router
    assert "streamlit_memory_lazy_router_v90" in app
    assert "STREAMLIT_MAIN_V89_NFL_PASSING_YARDS_STEP9_DISTRIBUTION_PROBABILITY_2026-09-11" in app
    assert "STREAMLIT_MAIN_V90_NFL_PASSING_YARDS_STEP10_MARKET_EDGE_FINAL_2026-09-11" in app
    assert "10 OF 10 STEPS COMPLETE" in page
    assert "sportsbook projection influence 0.0%" in page.lower()
    assert "Stake sizing is OFF" in page
    assert "integer lines are not graded" in page
    assert "No default line or price is fabricated" in page
    assert '"sportsbook_projection_influence": 0.0' in engine
    assert '"projection_adjustment_yards": 0.0' in engine
    assert '"stake_sizing_enabled": False' in engine
    assert "provider-agnostic" in engine
