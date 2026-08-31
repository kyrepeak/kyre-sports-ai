"""Step 5.8 read-only MLB actionability shadow policy.

Consumes the certified Step 5.7 price-health context and answers one narrow
question: if price health were allowed to influence execution later, what would
the policy say right now?

This module is deliberately SHADOW ONLY. It does not alter model math, Pick
Strength, ranking, selection, risk logic, persistence, or wagering. The point of
Step 5.8 is to prove the actionability policy before any future activation step.
"""
from __future__ import annotations

import math
from typing import Any, Mapping

from sports_api.mlb_price_health_v1 import DATA_TYPE as STEP5_7_DATA_TYPE

DATA_TYPE = "mlb_actionability_shadow_v1"
SCHEMA_VERSION = 1
SOURCE = "FanDuel"


class MLBActionabilityShadowError(ValueError):
    """Raised when Step 5.8 cannot prove a shadow actionability state safely."""


def _finite(value: Any, *, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MLBActionabilityShadowError(f"{field} must be numeric")
    out = float(value)
    if not math.isfinite(out):
        raise MLBActionabilityShadowError(f"{field} must be finite")
    return out


def _validate(context: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(context, Mapping):
        raise MLBActionabilityShadowError("Step 5.7 context must be a mapping")
    if context.get("data_type") != STEP5_7_DATA_TYPE:
        raise MLBActionabilityShadowError("Step 5.8 requires certified Step 5.7 context")
    if context.get("schema_version") != 1:
        raise MLBActionabilityShadowError("Step 5.7 schema version is unsupported")
    if str(context.get("source") or "") != SOURCE:
        raise MLBActionabilityShadowError("Step 5.8 accepts FanDuel context only")

    protected_false = (
        "model_math_impact",
        "pick_strength_impact",
        "selection_impact",
        "ranking_impact",
        "risk_logic_impact",
        "wagering_impact",
    )
    for field in protected_false:
        if context.get(field) is not False:
            raise MLBActionabilityShadowError(f"Step 5.7 {field} invariant is missing")
    if context.get("comparison_only") is not True:
        raise MLBActionabilityShadowError("Step 5.7 comparison-only invariant is missing")
    if context.get("freshness_bands_are_display_only") is not True:
        raise MLBActionabilityShadowError("Step 5.7 display-only freshness invariant is missing")
    if context.get("ephemeral_session_history") is not True:
        raise MLBActionabilityShadowError("Step 5.7 ephemeral-history invariant is missing")
    if context.get("durable_persistence") is not False:
        raise MLBActionabilityShadowError("Step 5.8 does not accept durable market-history writes")

    freshness = str(context.get("snapshot_freshness_status") or "")
    if freshness not in {"FRESH", "AGING", "STALE", "UNKNOWN"}:
        raise MLBActionabilityShadowError("snapshot freshness status is unsupported")

    value_status = str(context.get("current_value_status") or "")
    if value_status not in {"POSITIVE_VALUE", "BREAK_EVEN", "NEGATIVE_VALUE"}:
        raise MLBActionabilityShadowError("current value status is unsupported")

    health = str(context.get("price_health_status") or "")
    allowed_health = {
        "POSITIVE_VALUE_IMPROVING",
        "POSITIVE_VALUE_COMPRESSED",
        "POSITIVE_VALUE",
        "BREAK_EVEN",
        "NEGATIVE_VALUE_IMPROVING",
        "NEGATIVE_VALUE_WORSENING",
        "NEGATIVE_VALUE",
        "STALE_SNAPSHOT",
        "FRESHNESS_UNAVAILABLE",
        "LINE_CHANGED_NOT_COMPARABLE",
    }
    if health not in allowed_health:
        raise MLBActionabilityShadowError("price health status is unsupported")

    trajectory = str(context.get("value_trajectory") or "")
    if trajectory not in {
        "NO_COMPARABLE_PRIOR",
        "LINE_CHANGED_NOT_COMPARABLE",
        "IMPROVING",
        "DETERIORATING",
        "UNCHANGED",
    }:
        raise MLBActionabilityShadowError("value trajectory is unsupported")

    crossing = str(context.get("zero_ev_crossing_status") or "")
    if crossing not in {
        "NOT_COMPARABLE",
        "CROSSED_INTO_POSITIVE_VALUE",
        "CROSSED_OUT_OF_POSITIVE_VALUE",
        "NO_ZERO_EV_CROSSING",
    }:
        raise MLBActionabilityShadowError("zero-EV crossing status is unsupported")

    ev = _finite(context.get("current_expected_value_per_unit"), field="current_expected_value_per_unit")
    headroom = _finite(context.get("value_headroom_probability"), field="value_headroom_probability")
    if value_status == "POSITIVE_VALUE" and not (ev > 0 and headroom > 0):
        raise MLBActionabilityShadowError("positive-value status does not reconcile")
    if value_status == "BREAK_EVEN" and not (abs(ev) <= 1e-12 and abs(headroom) <= 1e-12):
        raise MLBActionabilityShadowError("break-even status does not reconcile")
    if value_status == "NEGATIVE_VALUE" and not (ev < 0 and headroom < 0):
        raise MLBActionabilityShadowError("negative-value status does not reconcile")

    age = context.get("snapshot_age_seconds")
    if age is not None:
        age = _finite(age, field="snapshot_age_seconds")
        if age < 0:
            raise MLBActionabilityShadowError("snapshot age cannot be negative")

    return {
        "official_game_id": context.get("official_game_id"),
        "market": context.get("market"),
        "selected_side": context.get("selected_side"),
        "current_market_line": context.get("current_market_line"),
        "current_market_odds": context.get("current_market_odds"),
        "model_probability": context.get("model_probability"),
        "current_expected_value_per_unit": ev,
        "value_headroom_probability": headroom,
        "model_zero_ev_american_price_limit": context.get("model_zero_ev_american_price_limit"),
        "snapshot_age_seconds": age,
        "snapshot_freshness_status": freshness,
        "current_value_status": value_status,
        "price_health_status": health,
        "value_trajectory": trajectory,
        "zero_ev_crossing_status": crossing,
    }


def actionability_shadow_context(step5_7_context: Mapping[str, Any]) -> dict[str, Any]:
    """Return the future-action policy result without changing any decision state."""
    current = _validate(step5_7_context)
    freshness = current["snapshot_freshness_status"]
    value = current["current_value_status"]
    health = current["price_health_status"]
    trajectory = current["value_trajectory"]
    crossing = current["zero_ev_crossing_status"]

    if freshness == "STALE" or health == "STALE_SNAPSHOT":
        shadow_status = "SHADOW_BLOCK_STALE"
        shadow_action = "REFRESH_REQUIRED"
        reason = "The market snapshot is stale, so the price should be refreshed before any future execution decision."
    elif freshness == "UNKNOWN" or health == "FRESHNESS_UNAVAILABLE":
        shadow_status = "SHADOW_BLOCK_UNKNOWN_FRESHNESS"
        shadow_action = "REFRESH_REQUIRED"
        reason = "Snapshot age cannot be proven, so Step 5.8 refuses to call the price actionable."
    elif health == "LINE_CHANGED_NOT_COMPARABLE" or trajectory == "LINE_CHANGED_NOT_COMPARABLE":
        shadow_status = "SHADOW_REPRICE_LINE_CHANGE"
        shadow_action = "REPRICE_CURRENT_LINE"
        reason = "The betting line changed, so the previous price comparison is not the same wager and must not be reused."
    elif value == "NEGATIVE_VALUE":
        if trajectory == "IMPROVING":
            shadow_status = "SHADOW_WAIT_NEGATIVE_IMPROVING"
            shadow_action = "WAIT_FOR_BETTER_PRICE"
            reason = "The price is improving but remains below the model's zero-EV threshold."
        else:
            shadow_status = "SHADOW_PASS_NEGATIVE_VALUE"
            shadow_action = "PASS_AT_CURRENT_PRICE"
            reason = "The current FanDuel price is negative EV versus the unchanged production model."
    elif value == "BREAK_EVEN":
        shadow_status = "SHADOW_PASS_BREAK_EVEN"
        shadow_action = "PASS_AT_CURRENT_PRICE"
        reason = "The current price is only break-even; Step 5.8 requires strictly positive EV for a shadow-playable state."
    elif crossing == "CROSSED_OUT_OF_POSITIVE_VALUE":
        raise MLBActionabilityShadowError("crossed-out state cannot coexist with current positive value")
    elif freshness == "AGING":
        shadow_status = "SHADOW_MONITOR_REFRESH"
        shadow_action = "REFRESH_BEFORE_EXECUTION"
        reason = "The price remains positive EV, but the snapshot is aging and should be refreshed before any future execution."
    elif freshness == "FRESH" and value == "POSITIVE_VALUE":
        if trajectory == "DETERIORATING" or health == "POSITIVE_VALUE_COMPRESSED":
            shadow_status = "SHADOW_PLAYABLE_COMPRESSED"
            shadow_action = "PLAYABLE_IF_STILL_AVAILABLE"
            reason = "The fresh price remains positive EV, but value has compressed versus the comparable prior same-line quote."
        elif trajectory == "IMPROVING" or health == "POSITIVE_VALUE_IMPROVING":
            shadow_status = "SHADOW_PLAYABLE_IMPROVING"
            shadow_action = "PLAYABLE_IF_STILL_AVAILABLE"
            reason = "The fresh price is positive EV and improved versus the comparable prior same-line quote."
        else:
            shadow_status = "SHADOW_PLAYABLE"
            shadow_action = "PLAYABLE_IF_STILL_AVAILABLE"
            reason = "The fresh current FanDuel price is strictly positive EV versus the unchanged production model."
    else:
        raise MLBActionabilityShadowError("Step 5.8 could not prove a safe shadow actionability state")

    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        **current,
        "shadow_status": shadow_status,
        "shadow_action": shadow_action,
        "shadow_reason": reason,
        "strict_positive_ev_required": True,
        "fresh_snapshot_required_for_shadow_playable": True,
        "aging_positive_value_requires_refresh": True,
        "stale_or_unknown_freshness_never_shadow_playable": True,
        "line_change_requires_reprice": True,
        "shadow_only": True,
        "activation_enabled": False,
        "comparison_only": True,
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
    "DATA_TYPE",
    "MLBActionabilityShadowError",
    "SCHEMA_VERSION",
    "actionability_shadow_context",
]
