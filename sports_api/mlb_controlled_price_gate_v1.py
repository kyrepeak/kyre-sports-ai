"""Step 5.9 controlled MLB price-aware Final Card gate.

Consumes certified Step 5.8 shadow-actionability output. The gate can affect Final
Card eligibility only when an explicit activation flag is true. Production default
is OFF. Even when active, it never changes projections, probabilities, Pick
Strength, ranking math, risk logic, persistence, or wagering.
"""
from __future__ import annotations

from typing import Any, Mapping

from sports_api.mlb_actionability_shadow_v1 import DATA_TYPE as STEP5_8_DATA_TYPE

DATA_TYPE = "mlb_controlled_price_gate_v1"
SCHEMA_VERSION = 1
SOURCE = "FanDuel"
SUPPORTED_MARKETS = {"Moneyline", "Run Line", "Total"}
PLAYABLE_SHADOW_STATUSES = {
    "SHADOW_PLAYABLE",
    "SHADOW_PLAYABLE_IMPROVING",
    "SHADOW_PLAYABLE_COMPRESSED",
}


class MLBControlledPriceGateError(ValueError):
    pass


def controlled_price_gate(
    step5_8_context: Mapping[str, Any],
    *,
    activation_requested: bool,
) -> dict[str, Any]:
    if not isinstance(step5_8_context, Mapping):
        raise MLBControlledPriceGateError("Step 5.8 context must be a mapping")
    if step5_8_context.get("data_type") != STEP5_8_DATA_TYPE:
        raise MLBControlledPriceGateError("Step 5.9 requires certified Step 5.8 context")
    if step5_8_context.get("schema_version") != 1:
        raise MLBControlledPriceGateError("unsupported Step 5.8 schema")
    if str(step5_8_context.get("source") or "") != SOURCE:
        raise MLBControlledPriceGateError("Step 5.9 accepts FanDuel context only")
    if not isinstance(activation_requested, bool):
        raise MLBControlledPriceGateError("activation_requested must be boolean")
    if step5_8_context.get("shadow_only") is not True:
        raise MLBControlledPriceGateError("Step 5.8 shadow-only invariant missing")
    if step5_8_context.get("activation_enabled") is not False:
        raise MLBControlledPriceGateError("Step 5.8 activation invariant missing")
    if step5_8_context.get("durable_persistence") is not False:
        raise MLBControlledPriceGateError("durable persistence is forbidden")
    for field in (
        "model_math_impact",
        "pick_strength_impact",
        "ranking_impact",
        "risk_logic_impact",
        "wagering_impact",
    ):
        if step5_8_context.get(field) is not False:
            raise MLBControlledPriceGateError(f"Step 5.8 {field} invariant missing")

    market = str(step5_8_context.get("market") or "")
    if market not in SUPPORTED_MARKETS:
        raise MLBControlledPriceGateError("Step 5.9 gate supports certified full-game markets only")

    shadow_status = str(step5_8_context.get("shadow_status") or "")
    shadow_action = str(step5_8_context.get("shadow_action") or "")
    if not shadow_status or not shadow_action:
        raise MLBControlledPriceGateError("Step 5.8 shadow decision is incomplete")

    if not activation_requested:
        gate_status = "CONTROL_DISABLED"
        eligible = True
        reason = "Controlled price gate is disabled; existing Final Card selection behavior is preserved."
        selection_impact = False
    elif shadow_status in PLAYABLE_SHADOW_STATUSES:
        gate_status = "GATE_ALLOW"
        eligible = True
        reason = "Certified fresh positive-EV price is allowed through the controlled gate."
        selection_impact = True
    else:
        gate_status = "GATE_BLOCK"
        eligible = False
        reason = f"Controlled gate blocks this candidate because Step 5.8 says {shadow_status}."
        selection_impact = True

    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "source": SOURCE,
        "official_game_id": step5_8_context.get("official_game_id"),
        "market": market,
        "selected_side": step5_8_context.get("selected_side"),
        "current_market_line": step5_8_context.get("current_market_line"),
        "current_market_odds": step5_8_context.get("current_market_odds"),
        "model_probability": step5_8_context.get("model_probability"),
        "current_expected_value_per_unit": step5_8_context.get("current_expected_value_per_unit"),
        "model_zero_ev_american_price_limit": step5_8_context.get("model_zero_ev_american_price_limit"),
        "snapshot_freshness_status": step5_8_context.get("snapshot_freshness_status"),
        "shadow_status": shadow_status,
        "shadow_action": shadow_action,
        "activation_requested": activation_requested,
        "gate_status": gate_status,
        "final_card_price_eligible": eligible,
        "gate_reason": reason,
        "price_gate_scope": "FULL_GAME_CERTIFIED_MARKETS_ONLY",
        "model_math_impact": False,
        "pick_strength_impact": False,
        "ranking_math_impact": False,
        "risk_logic_impact": False,
        "selection_eligibility_impact": selection_impact,
        "wagering_impact": False,
        "durable_persistence": False,
    }


__all__ = [
    "DATA_TYPE",
    "MLBControlledPriceGateError",
    "PLAYABLE_SHADOW_STATUSES",
    "SCHEMA_VERSION",
    "SUPPORTED_MARKETS",
    "controlled_price_gate",
]
