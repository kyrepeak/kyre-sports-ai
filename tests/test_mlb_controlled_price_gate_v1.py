from __future__ import annotations

from copy import deepcopy

import pytest

from sports_api.mlb_controlled_price_gate_v1 import (
    DATA_TYPE,
    MLBControlledPriceGateError,
    SCHEMA_VERSION,
    controlled_price_gate,
)


def _shadow(*, market="Moneyline", status="SHADOW_PLAYABLE", action="PLAYABLE_IF_STILL_AVAILABLE"):
    return {
        "data_type": "mlb_actionability_shadow_v1",
        "schema_version": 1,
        "source": "FanDuel",
        "official_game_id": 824911,
        "market": market,
        "selected_side": "home" if market != "Total" else "over",
        "current_market_line": None if market == "Moneyline" else 1.5 if market == "Run Line" else 8.5,
        "current_market_odds": -120,
        "model_probability": 0.60,
        "current_expected_value_per_unit": 0.10,
        "model_zero_ev_american_price_limit": -150,
        "snapshot_freshness_status": "FRESH",
        "shadow_status": status,
        "shadow_action": action,
        "shadow_reason": "test",
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


def test_disabled_gate_is_passthrough():
    out = controlled_price_gate(_shadow(), activation_requested=False)
    assert out["data_type"] == DATA_TYPE
    assert out["schema_version"] == SCHEMA_VERSION
    assert out["gate_status"] == "CONTROL_DISABLED"
    assert out["final_card_price_eligible"] is True
    assert out["selection_eligibility_impact"] is False


@pytest.mark.parametrize("status", [
    "SHADOW_PLAYABLE",
    "SHADOW_PLAYABLE_IMPROVING",
    "SHADOW_PLAYABLE_COMPRESSED",
])
def test_active_gate_allows_only_shadow_playable_states(status):
    out = controlled_price_gate(_shadow(status=status), activation_requested=True)
    assert out["gate_status"] == "GATE_ALLOW"
    assert out["final_card_price_eligible"] is True
    assert out["selection_eligibility_impact"] is True


@pytest.mark.parametrize("status,action", [
    ("SHADOW_MONITOR_REFRESH", "REFRESH_BEFORE_EXECUTION"),
    ("SHADOW_REPRICE_LINE_CHANGE", "REPRICE_CURRENT_LINE"),
    ("SHADOW_WAIT_NEGATIVE_IMPROVING", "WAIT_FOR_BETTER_PRICE"),
    ("SHADOW_PASS_BREAK_EVEN", "PASS_AT_CURRENT_PRICE"),
    ("SHADOW_PASS_NEGATIVE_VALUE", "PASS_AT_CURRENT_PRICE"),
    ("SHADOW_BLOCK_STALE", "REFRESH_REQUIRED"),
    ("SHADOW_BLOCK_UNKNOWN_FRESHNESS", "REFRESH_REQUIRED"),
])
def test_active_gate_blocks_every_nonplayable_shadow_state(status, action):
    out = controlled_price_gate(_shadow(status=status, action=action), activation_requested=True)
    assert out["gate_status"] == "GATE_BLOCK"
    assert out["final_card_price_eligible"] is False
    assert out["selection_eligibility_impact"] is True


def test_input_is_not_mutated():
    ctx = _shadow()
    before = deepcopy(ctx)
    controlled_price_gate(ctx, activation_requested=True)
    assert ctx == before


@pytest.mark.parametrize("market", ["Moneyline", "Run Line", "Total"])
def test_supported_markets(market):
    out = controlled_price_gate(_shadow(market=market), activation_requested=True)
    assert out["market"] == market


@pytest.mark.parametrize("market", ["1+ Hit", "Home Run", "H+R+RBI", "Player Prop", ""])
def test_uncertified_markets_fail_closed_in_core(market):
    with pytest.raises(MLBControlledPriceGateError):
        controlled_price_gate(_shadow(market=market), activation_requested=True)


def test_activation_must_be_boolean():
    with pytest.raises(MLBControlledPriceGateError):
        controlled_price_gate(_shadow(), activation_requested=1)


@pytest.mark.parametrize("field,value", [
    ("data_type", "wrong"),
    ("schema_version", 2),
    ("source", "OtherBook"),
    ("shadow_only", False),
    ("activation_enabled", True),
    ("durable_persistence", True),
    ("model_math_impact", True),
    ("pick_strength_impact", True),
    ("ranking_impact", True),
    ("risk_logic_impact", True),
    ("wagering_impact", True),
])
def test_invalid_step58_contract_fails_closed(field, value):
    ctx = _shadow()
    ctx[field] = value
    with pytest.raises(MLBControlledPriceGateError):
        controlled_price_gate(ctx, activation_requested=True)


def test_missing_shadow_status_fails_closed():
    ctx = _shadow()
    ctx["shadow_status"] = ""
    with pytest.raises(MLBControlledPriceGateError):
        controlled_price_gate(ctx, activation_requested=True)


def test_missing_shadow_action_fails_closed():
    ctx = _shadow()
    ctx["shadow_action"] = ""
    with pytest.raises(MLBControlledPriceGateError):
        controlled_price_gate(ctx, activation_requested=True)


def test_active_gate_never_changes_model_or_pick_strength_contract():
    out = controlled_price_gate(_shadow(), activation_requested=True)
    assert out["model_math_impact"] is False
    assert out["pick_strength_impact"] is False
    assert out["ranking_math_impact"] is False
    assert out["risk_logic_impact"] is False
    assert out["wagering_impact"] is False
    assert out["durable_persistence"] is False


def test_gate_preserves_market_identity_and_price():
    ctx = _shadow(market="Total")
    out = controlled_price_gate(ctx, activation_requested=True)
    assert out["official_game_id"] == ctx["official_game_id"]
    assert out["selected_side"] == ctx["selected_side"]
    assert out["current_market_line"] == ctx["current_market_line"]
    assert out["current_market_odds"] == ctx["current_market_odds"]
    assert out["model_probability"] == ctx["model_probability"]
    assert out["current_expected_value_per_unit"] == ctx["current_expected_value_per_unit"]


def test_disabled_gate_does_not_block_even_nonplayable_shadow_state():
    out = controlled_price_gate(
        _shadow(status="SHADOW_PASS_NEGATIVE_VALUE", action="PASS_AT_CURRENT_PRICE"),
        activation_requested=False,
    )
    assert out["gate_status"] == "CONTROL_DISABLED"
    assert out["final_card_price_eligible"] is True


def test_controlled_gate_scope_is_explicit():
    out = controlled_price_gate(_shadow(), activation_requested=True)
    assert out["price_gate_scope"] == "FULL_GAME_CERTIFIED_MARKETS_ONLY"
