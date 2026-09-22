"""Step 5.5 read-only MLB price-discipline layer.

Consumes the certified Step 5.4 model-vs-market edge context and separates two ideas
that must not be conflated:

1. handicap edge: production model probability minus FanDuel no-vig probability;
2. price edge: production model probability minus the raw break-even probability
   implied by the exact FanDuel price actually being offered.

The difference between those two is the selected-side vig drag. Step 5.5 also exposes
the model's zero-EV American price limit (identical to model fair odds) and a simple
current-price status. This module is comparison/presentation only: it never mutates
model probability, projection, Pick Strength, simulation, ranking, selection, risk,
persistence, or wagering state.
"""
from __future__ import annotations

import math
from typing import Any, Mapping

from sports_api.mlb_model_market_edge_v1 import (
    DATA_TYPE as STEP5_4_DATA_TYPE,
    MLBModelMarketEdgeError,
    expected_value_per_unit,
    probability_to_american_odds,
)
from sports_api.mlb_official_game_id_join_v1 import canonical_official_game_id

DATA_TYPE = "mlb_price_discipline_context_v1"
SCHEMA_VERSION = 1
SOURCE = "FanDuel"
EV_TOLERANCE = 1e-12


class MLBPriceDisciplineError(ValueError):
    """Raised when Step 5.5 cannot prove its price-discipline derivation safely."""


def _finite_number(value: Any, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MLBPriceDisciplineError(f"{field} must be numeric")
    out = float(value)
    if not math.isfinite(out):
        raise MLBPriceDisciplineError(f"{field} must be finite")
    return out


def _probability(value: Any, *, field: str) -> float:
    out = _finite_number(value, field=field)
    if not (0.0 < out < 1.0):
        raise MLBPriceDisciplineError(f"{field} must be strictly between 0 and 1")
    return out


def american_odds_implied_probability(odds: Any) -> float:
    """Return the raw break-even probability implied by American odds."""
    value = _finite_number(odds, field="market_odds")
    if abs(value) < 100.0:
        raise MLBPriceDisciplineError("American odds absolute value must be at least 100")
    if value > 0:
        return 100.0 / (value + 100.0)
    return (-value) / ((-value) + 100.0)


def current_price_status(expected_value: Any, *, tolerance: float = EV_TOLERANCE) -> str:
    """Classify the exact offered price strictly by EV sign; no arbitrary grading bands."""
    ev = _finite_number(expected_value, field="expected_value_per_unit")
    tol = abs(float(tolerance))
    if ev > tol:
        return "POSITIVE_VALUE"
    if ev < -tol:
        return "NEGATIVE_VALUE"
    return "BREAK_EVEN"


def price_discipline_context(step5_4_context: Mapping[str, Any]) -> dict[str, Any]:
    """Derive Step 5.5 price discipline from one certified Step 5.4 context."""
    if not isinstance(step5_4_context, Mapping):
        raise MLBPriceDisciplineError("Step 5.4 context must be a mapping")
    if step5_4_context.get("data_type") != STEP5_4_DATA_TYPE:
        raise MLBPriceDisciplineError("Step 5.5 requires the certified Step 5.4 data type")
    if step5_4_context.get("schema_version") != 1:
        raise MLBPriceDisciplineError("Step 5.4 schema version is unsupported")
    if str(step5_4_context.get("source") or "") != SOURCE:
        raise MLBPriceDisciplineError("Step 5.5 accepts FanDuel context only")
    if step5_4_context.get("fallback_matching_used") is not False:
        raise MLBPriceDisciplineError("Step 5.5 requires exact-ID context with no fallback")
    if step5_4_context.get("comparison_only") is not True:
        raise MLBPriceDisciplineError("Step 5.4 comparison-only invariant is missing")

    try:
        game_id = canonical_official_game_id(step5_4_context.get("official_game_id"))
    except Exception as exc:
        raise MLBPriceDisciplineError("official_game_id is invalid") from exc

    model_p = _probability(step5_4_context.get("model_probability"), field="model_probability")
    market_no_vig_p = _probability(
        step5_4_context.get("market_no_vig_probability"),
        field="market_no_vig_probability",
    )
    market_odds = _finite_number(step5_4_context.get("market_odds"), field="market_odds")
    if abs(market_odds) < 100.0:
        raise MLBPriceDisciplineError("American odds absolute value must be at least 100")

    raw_break_even_p = american_odds_implied_probability(market_odds)
    pricing_margin = model_p - raw_break_even_p
    handicap_edge = model_p - market_no_vig_p
    vig_drag = raw_break_even_p - market_no_vig_p

    recomputed_ev = expected_value_per_unit(model_p, market_odds)
    supplied_ev = _finite_number(
        step5_4_context.get("expected_value_per_unit"),
        field="Step 5.4 expected_value_per_unit",
    )
    if not math.isclose(recomputed_ev, supplied_ev, rel_tol=0.0, abs_tol=1e-12):
        raise MLBPriceDisciplineError("Step 5.4 EV does not reconcile with model probability and market odds")

    zero_ev_price = probability_to_american_odds(model_p)
    supplied_fair_price = _finite_number(
        step5_4_context.get("model_fair_american_odds"),
        field="Step 5.4 model_fair_american_odds",
    )
    if not math.isclose(zero_ev_price, supplied_fair_price, rel_tol=0.0, abs_tol=1e-10):
        raise MLBPriceDisciplineError("Step 5.4 model fair odds do not reconcile with model probability")

    supplied_edge = _finite_number(
        step5_4_context.get("edge_probability"),
        field="Step 5.4 edge_probability",
    )
    if not math.isclose(handicap_edge, supplied_edge, rel_tol=0.0, abs_tol=1e-12):
        raise MLBPriceDisciplineError("Step 5.4 model-minus-no-vig edge does not reconcile")

    status = current_price_status(recomputed_ev)
    result = {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        "official_game_id": game_id,
        "match_method": step5_4_context.get("match_method") or "official_mlb_game_id_exact",
        "fallback_matching_used": False,
        "market": step5_4_context.get("market"),
        "selected_side": step5_4_context.get("selected_side"),
        "market_line": step5_4_context.get("market_line"),
        "model_probability": model_p,
        "market_no_vig_probability": market_no_vig_p,
        "market_raw_break_even_probability": raw_break_even_p,
        "handicap_edge_probability": handicap_edge,
        "handicap_edge_percentage_points": handicap_edge * 100.0,
        "vig_drag_probability": vig_drag,
        "vig_drag_percentage_points": vig_drag * 100.0,
        "pricing_margin_probability": pricing_margin,
        "pricing_margin_percentage_points": pricing_margin * 100.0,
        "market_odds": market_odds,
        "zero_ev_american_price_limit": zero_ev_price,
        "expected_value_per_unit": recomputed_ev,
        "expected_value_percent": recomputed_ev * 100.0,
        "current_price_status": status,
        "positive_expected_value": status == "POSITIVE_VALUE",
        "current_price_meets_model_fair_limit": status != "NEGATIVE_VALUE",
        "comparison_only": True,
        "selection_impact": False,
        "ranking_impact": False,
        "wagering_impact": False,
    }
    return result


__all__ = [
    "DATA_TYPE",
    "EV_TOLERANCE",
    "MLBPriceDisciplineError",
    "SCHEMA_VERSION",
    "SOURCE",
    "american_odds_implied_probability",
    "current_price_status",
    "price_discipline_context",
]
