"""Step 5.7 read-only MLB price-health and edge-retention layer.

Consumes the certified Step 5.6 market-movement context and combines three facts
that are already proven upstream:
- current exact FanDuel price versus the unchanged production model probability,
- snapshot age from the certified production collection timestamp,
- same-line price-only EV movement when a comparable prior observation exists.

Step 5.7 does not create a new model, alter a projection, change Pick Strength,
rank selections, place wagers, or persist market history. It only classifies the
health of the currently displayed price and whether positive value improved,
compressed, crossed zero EV, or cannot be compared safely.
"""
from __future__ import annotations

import math
from typing import Any, Mapping

from sports_api.mlb_market_movement_v1 import (
    DATA_TYPE as STEP5_6_DATA_TYPE,
    SOURCE,
    SUPPORTED_MARKETS,
)
from sports_api.mlb_model_market_edge_v1 import expected_value_per_unit

DATA_TYPE = "mlb_price_health_context_v1"
SCHEMA_VERSION = 1
FRESH_MAX_SECONDS = 120.0
AGING_MAX_SECONDS = 300.0
TOLERANCE = 1e-12


class MLBPriceHealthError(ValueError):
    """Raised when Step 5.7 cannot prove a price-health classification safely."""


def _finite(value: Any, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MLBPriceHealthError(f"{field} must be numeric")
    out = float(value)
    if not math.isfinite(out):
        raise MLBPriceHealthError(f"{field} must be finite")
    return out


def _probability(value: Any, *, field: str) -> float:
    out = _finite(value, field=field)
    if not (0.0 < out < 1.0):
        raise MLBPriceHealthError(f"{field} must be strictly between 0 and 1")
    return out


def _american_odds(value: Any, *, field: str) -> float:
    out = _finite(value, field=field)
    if abs(out) < 100.0:
        raise MLBPriceHealthError(f"{field} must be valid American odds")
    return out


def _value_status(ev: float) -> str:
    if ev > TOLERANCE:
        return "POSITIVE_VALUE"
    if ev < -TOLERANCE:
        return "NEGATIVE_VALUE"
    return "BREAK_EVEN"


def _freshness_status(age_seconds: Any) -> tuple[str, float | None]:
    if age_seconds is None:
        return "UNKNOWN", None
    age = _finite(age_seconds, field="snapshot_age_seconds")
    if age < 0:
        raise MLBPriceHealthError("snapshot_age_seconds cannot be negative")
    if age <= FRESH_MAX_SECONDS:
        return "FRESH", age
    if age <= AGING_MAX_SECONDS:
        return "AGING", age
    return "STALE", age


def _validate_step5_6_context(context: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(context, Mapping):
        raise MLBPriceHealthError("Step 5.6 context must be a mapping")
    if context.get("data_type") != STEP5_6_DATA_TYPE:
        raise MLBPriceHealthError("Step 5.7 requires the certified Step 5.6 data type")
    if context.get("schema_version") != 1:
        raise MLBPriceHealthError("Step 5.6 schema version is unsupported")
    if str(context.get("source") or "") != SOURCE:
        raise MLBPriceHealthError("Step 5.7 accepts FanDuel context only")
    if context.get("fallback_matching_used") is not False:
        raise MLBPriceHealthError("Step 5.7 requires exact-ID context with no fallback")
    if context.get("comparison_only") is not True:
        raise MLBPriceHealthError("Step 5.6 comparison-only invariant is missing")
    if context.get("ephemeral_session_history") is not True:
        raise MLBPriceHealthError("Step 5.6 ephemeral-history invariant is missing")
    if context.get("durable_persistence") is not False:
        raise MLBPriceHealthError("Step 5.7 does not accept durable market-history writes")
    for field in ("selection_impact", "ranking_impact", "wagering_impact"):
        if context.get(field) is not False:
            raise MLBPriceHealthError(f"Step 5.6 {field} invariant is missing")

    market = str(context.get("market") or "").strip()
    side = str(context.get("selected_side") or "").strip().lower()
    if market not in SUPPORTED_MARKETS:
        raise MLBPriceHealthError("market is unsupported")
    allowed_sides = {
        "Moneyline": {"away", "home"},
        "Run Line": {"away", "home"},
        "Total": {"over", "under"},
    }
    if side not in allowed_sides[market]:
        raise MLBPriceHealthError("selected_side is unsupported for market")

    game_id = context.get("official_game_id")
    if isinstance(game_id, bool):
        raise MLBPriceHealthError("official_game_id is invalid")
    try:
        game_id = int(game_id)
    except Exception as exc:
        raise MLBPriceHealthError("official_game_id is invalid") from exc
    if game_id <= 0:
        raise MLBPriceHealthError("official_game_id is invalid")

    model_p = _probability(context.get("current_model_probability"), field="current_model_probability")
    raw_break_even = _probability(
        context.get("current_raw_break_even_probability"),
        field="current_raw_break_even_probability",
    )
    no_vig = _probability(context.get("current_no_vig_probability"), field="current_no_vig_probability")
    odds = _american_odds(context.get("current_market_odds"), field="current_market_odds")
    current_ev = _finite(context.get("current_expected_value_per_unit"), field="current_expected_value_per_unit")
    zero_ev = _american_odds(
        context.get("current_zero_ev_american_price_limit"),
        field="current_zero_ev_american_price_limit",
    )

    expected_ev = expected_value_per_unit(model_p, odds)
    if not math.isclose(expected_ev, current_ev, rel_tol=0.0, abs_tol=1e-12):
        raise MLBPriceHealthError("current EV does not reconcile with model probability and FanDuel odds")

    movement_status = str(context.get("movement_status") or "").strip()
    if movement_status not in {
        "NO_PRIOR_OBSERVATION",
        "NO_NEW_OBSERVATION",
        "BETTER_PRICE",
        "MORE_EXPENSIVE",
        "UNCHANGED",
        "LINE_CHANGED",
    }:
        raise MLBPriceHealthError("Step 5.6 movement_status is unsupported")

    freshness, age = _freshness_status(context.get("snapshot_age_seconds"))

    return {
        "official_game_id": game_id,
        "market": market,
        "selected_side": side,
        "current_market_line": context.get("current_market_line"),
        "current_market_odds": odds,
        "current_raw_break_even_probability": raw_break_even,
        "current_no_vig_probability": no_vig,
        "current_model_probability": model_p,
        "current_expected_value_per_unit": current_ev,
        "current_zero_ev_american_price_limit": zero_ev,
        "current_collected_at_utc": context.get("current_collected_at_utc"),
        "snapshot_age_seconds": age,
        "snapshot_freshness_status": freshness,
        "movement_status": movement_status,
        "movement_available": context.get("movement_available") is True,
        "price_comparison_comparable": context.get("price_comparison_comparable") is True,
        "price_only_previous_ev_using_current_model": context.get("price_only_previous_ev_using_current_model"),
        "price_only_ev_delta": context.get("price_only_ev_delta"),
        "previous_market_odds": context.get("previous_market_odds"),
        "previous_market_line": context.get("previous_market_line"),
    }


def price_health_context(step5_6_context: Mapping[str, Any]) -> dict[str, Any]:
    """Classify current price health without changing any production decision state."""
    current = _validate_step5_6_context(step5_6_context)
    current_ev = current["current_expected_value_per_unit"]
    current_value_status = _value_status(current_ev)
    headroom = current["current_model_probability"] - current["current_raw_break_even_probability"]

    movement_status = current["movement_status"]
    comparable = current["price_comparison_comparable"]
    movement_available = current["movement_available"]

    previous_ev = None
    ev_delta = None
    if movement_status in {"NO_PRIOR_OBSERVATION", "NO_NEW_OBSERVATION"}:
        trajectory = "NO_COMPARABLE_PRIOR"
        crossing = "NOT_COMPARABLE"
    elif movement_status == "LINE_CHANGED":
        if comparable:
            raise MLBPriceHealthError("line-changed observations cannot be price-comparable")
        trajectory = "LINE_CHANGED_NOT_COMPARABLE"
        crossing = "NOT_COMPARABLE"
    else:
        if not movement_available or not comparable:
            raise MLBPriceHealthError("same-line movement requires a comparable prior observation")
        previous_ev = _finite(
            current["price_only_previous_ev_using_current_model"],
            field="price_only_previous_ev_using_current_model",
        )
        ev_delta = _finite(current["price_only_ev_delta"], field="price_only_ev_delta")
        if not math.isclose(current_ev - previous_ev, ev_delta, rel_tol=0.0, abs_tol=1e-12):
            raise MLBPriceHealthError("price-only EV delta does not reconcile")

        if ev_delta > TOLERANCE:
            trajectory = "IMPROVING"
        elif ev_delta < -TOLERANCE:
            trajectory = "DETERIORATING"
        else:
            trajectory = "UNCHANGED"

        previous_value_status = _value_status(previous_ev)
        if previous_value_status != "POSITIVE_VALUE" and current_value_status == "POSITIVE_VALUE":
            crossing = "CROSSED_INTO_POSITIVE_VALUE"
        elif previous_value_status == "POSITIVE_VALUE" and current_value_status != "POSITIVE_VALUE":
            crossing = "CROSSED_OUT_OF_POSITIVE_VALUE"
        else:
            crossing = "NO_ZERO_EV_CROSSING"

    freshness = current["snapshot_freshness_status"]
    if freshness == "STALE":
        health = "STALE_SNAPSHOT"
    elif freshness == "UNKNOWN":
        health = "FRESHNESS_UNAVAILABLE"
    elif movement_status == "LINE_CHANGED":
        health = "LINE_CHANGED_NOT_COMPARABLE"
    elif current_value_status == "POSITIVE_VALUE":
        if trajectory == "IMPROVING":
            health = "POSITIVE_VALUE_IMPROVING"
        elif trajectory == "DETERIORATING":
            health = "POSITIVE_VALUE_COMPRESSED"
        else:
            health = "POSITIVE_VALUE"
    elif current_value_status == "BREAK_EVEN":
        health = "BREAK_EVEN"
    else:
        if trajectory == "IMPROVING":
            health = "NEGATIVE_VALUE_IMPROVING"
        elif trajectory == "DETERIORATING":
            health = "NEGATIVE_VALUE_WORSENING"
        else:
            health = "NEGATIVE_VALUE"

    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        "official_game_id": current["official_game_id"],
        "market": current["market"],
        "selected_side": current["selected_side"],
        "current_market_line": current["current_market_line"],
        "current_market_odds": current["current_market_odds"],
        "model_probability": current["current_model_probability"],
        "market_raw_break_even_probability": current["current_raw_break_even_probability"],
        "market_no_vig_probability": current["current_no_vig_probability"],
        "current_expected_value_per_unit": current_ev,
        "current_value_status": current_value_status,
        "value_headroom_probability": headroom,
        "value_headroom_percentage_points": headroom * 100.0,
        "model_zero_ev_american_price_limit": current["current_zero_ev_american_price_limit"],
        "snapshot_age_seconds": current["snapshot_age_seconds"],
        "snapshot_freshness_status": freshness,
        "fresh_max_seconds": FRESH_MAX_SECONDS,
        "aging_max_seconds": AGING_MAX_SECONDS,
        "movement_status": movement_status,
        "value_trajectory": trajectory,
        "zero_ev_crossing_status": crossing,
        "previous_ev_using_current_model": previous_ev,
        "price_only_ev_delta": ev_delta,
        "price_health_status": health,
        "comparison_only": True,
        "freshness_bands_are_display_only": True,
        "ephemeral_session_history": True,
        "durable_persistence": False,
        "model_math_impact": False,
        "pick_strength_impact": False,
        "selection_impact": False,
        "ranking_impact": False,
        "risk_logic_impact": False,
        "wagering_impact": False,
    }


__all__ = [
    "AGING_MAX_SECONDS",
    "DATA_TYPE",
    "FRESH_MAX_SECONDS",
    "MLBPriceHealthError",
    "SCHEMA_VERSION",
    "price_health_context",
]
