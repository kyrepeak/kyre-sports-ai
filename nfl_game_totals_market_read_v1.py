"""Comparison-only NFL Game Totals market read for page Step 9.

The projection is already complete before this helper receives it. The sportsbook
line is used only to compare against the frozen model total/range; it never feeds
back into projection math, stake sizing, or wager execution.
"""
from __future__ import annotations

import math
from typing import Any

SPORTSBOOK_PROJECTION_WEIGHT = 0.0
STAKE_SIZING_ENABLED = False
WAGER_ACTIONS_ENABLED = False


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _unavailable(reason: str) -> dict[str, Any]:
    return {
        "ready": False,
        "final_read": "UNAVAILABLE",
        "model_total": None,
        "market_total": None,
        "edge_points": None,
        "range_low": None,
        "range_high": None,
        "over_price": None,
        "under_price": None,
        "comparison_only": True,
        "sportsbook_projection_weight": SPORTSBOOK_PROJECTION_WEIGHT,
        "stake_sizing_enabled": STAKE_SIZING_ENABLED,
        "wager_actions_enabled": WAGER_ACTIONS_ENABLED,
        "diagnostics": [reason],
    }


def build_market_final_read(
    projection: dict[str, Any] | None,
    market_snapshot: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return OVER/UNDER/PASS from model range vs exact active market total.

    OVER means the market total sits below the model's certified range.
    UNDER means it sits above that range. A line inside the range is PASS.
    """
    projection = projection or {}
    snapshot = market_snapshot or {}
    if projection.get("ready") is not True:
        return _unavailable("Certified Step 8 projection unavailable.")
    if _finite(projection.get("sportsbook_projection_weight")) != 0.0:
        return _unavailable("Projection firewall violation: sportsbook weight must remain 0.0%.")

    model_total = _finite(projection.get("projected_total"))
    range_low = _finite(projection.get("range_low"))
    range_high = _finite(projection.get("range_high"))
    if model_total is None or range_low is None or range_high is None or range_low > range_high:
        return _unavailable("Certified model total/range is incomplete.")

    markets = snapshot.get("markets") if isinstance(snapshot.get("markets"), list) else []
    if snapshot.get("ready") is not True or snapshot.get("market_available") is not True or len(markets) != 1:
        return _unavailable("Exact FanDuel total market unavailable or ambiguous.")
    market = markets[0] if isinstance(markets[0], dict) else {}
    if market.get("active") is not True:
        return _unavailable("Exact FanDuel total market is not active.")

    market_total = _finite(market.get("total"))
    if market_total is None or market_total <= 0.0:
        return _unavailable("Exact FanDuel total line is invalid.")

    edge = model_total - market_total
    if market_total < range_low:
        final_read = "OVER"
        clearance = range_low - market_total
        rationale = "Market total is below the certified model range."
    elif market_total > range_high:
        final_read = "UNDER"
        clearance = market_total - range_high
        rationale = "Market total is above the certified model range."
    else:
        final_read = "PASS"
        clearance = 0.0
        rationale = "Market total sits inside the certified model range."

    return {
        "ready": True,
        "final_read": final_read,
        "model_total": round(model_total, 3),
        "market_total": round(market_total, 3),
        "edge_points": round(edge, 3),
        "range_low": round(range_low, 3),
        "range_high": round(range_high, 3),
        "range_clearance": round(clearance, 3),
        "over_price": market.get("over_price"),
        "under_price": market.get("under_price"),
        "market_id": str(market.get("market_id") or ""),
        "comparison_only": True,
        "sportsbook_projection_weight": SPORTSBOOK_PROJECTION_WEIGHT,
        "stake_sizing_enabled": STAKE_SIZING_ENABLED,
        "wager_actions_enabled": WAGER_ACTIONS_ENABLED,
        "rationale": rationale,
        "diagnostics": [],
    }
