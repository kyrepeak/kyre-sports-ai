from __future__ import annotations

from copy import deepcopy

import pytest

from sports_api.mlb_actionability_shadow_v1 import (
    DATA_TYPE,
    MLBActionabilityShadowError,
    SCHEMA_VERSION,
    actionability_shadow_context,
)


def _ctx(
    *,
    freshness="FRESH",
    value="POSITIVE_VALUE",
    health="POSITIVE_VALUE",
    trajectory="NO_COMPARABLE_PRIOR",
    crossing="NOT_COMPARABLE",
    ev=0.05,
    headroom=0.03,
    age=30.0,
):
    return {
        "data_type": "mlb_price_health_context_v1",
        "schema_version": 1,
        "source": "FanDuel",
        "official_game_id": 824911,
        "market": "Moneyline",
        "selected_side": "home",
        "current_market_line": None,
        "current_market_odds": -120,
        "model_probability": 0.60,
        "market_raw_break_even_probability": 0.57,
        "market_no_vig_probability": 0.55,
        "current_expected_value_per_unit": ev,
        "current_value_status": value,
        "value_headroom_probability": headroom,
        "value_headroom_percentage_points": headroom * 100.0,
        "model_zero_ev_american_price_limit": -150,
        "snapshot_age_seconds": age,
        "snapshot_freshness_status": freshness,
        "fresh_max_seconds": 120.0,
        "aging_max_seconds": 300.0,
        "movement_status": "NO_PRIOR_OBSERVATION",
        "value_trajectory": trajectory,
        "zero_ev_crossing_status": crossing,
        "previous_ev_using_current_model": None,
        "price_only_ev_delta": None,
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


def test_fresh_positive_value_is_shadow_playable():
    out = actionability_shadow_context(_ctx())
    assert out["data_type"] == DATA_TYPE
    assert out["schema_version"] == SCHEMA_VERSION
    assert out["shadow_status"] == "SHADOW_PLAYABLE"
    assert out["shadow_action"] == "PLAYABLE_IF_STILL_AVAILABLE"
    assert out["shadow_only"] is True
    assert out["activation_enabled"] is False


def test_fresh_positive_improving_is_shadow_playable_improving():
    out = actionability_shadow_context(
        _ctx(
            health="POSITIVE_VALUE_IMPROVING",
            trajectory="IMPROVING",
            crossing="NO_ZERO_EV_CROSSING",
        )
    )
    assert out["shadow_status"] == "SHADOW_PLAYABLE_IMPROVING"


def test_fresh_positive_compressed_is_shadow_playable_compressed():
    out = actionability_shadow_context(
        _ctx(
            health="POSITIVE_VALUE_COMPRESSED",
            trajectory="DETERIORATING",
            crossing="NO_ZERO_EV_CROSSING",
        )
    )
    assert out["shadow_status"] == "SHADOW_PLAYABLE_COMPRESSED"


def test_fresh_positive_crossed_into_value_is_playable():
    out = actionability_shadow_context(
        _ctx(
            health="POSITIVE_VALUE_IMPROVING",
            trajectory="IMPROVING",
            crossing="CROSSED_INTO_POSITIVE_VALUE",
        )
    )
    assert out["shadow_status"] == "SHADOW_PLAYABLE_IMPROVING"


def test_aging_positive_requires_refresh():
    out = actionability_shadow_context(
        _ctx(freshness="AGING", age=180.0)
    )
    assert out["shadow_status"] == "SHADOW_MONITOR_REFRESH"
    assert out["shadow_action"] == "REFRESH_BEFORE_EXECUTION"


def test_stale_positive_is_blocked_even_if_ev_positive():
    out = actionability_shadow_context(
        _ctx(freshness="STALE", health="STALE_SNAPSHOT", age=450.0)
    )
    assert out["shadow_status"] == "SHADOW_BLOCK_STALE"
    assert out["shadow_action"] == "REFRESH_REQUIRED"


def test_unknown_freshness_is_blocked():
    out = actionability_shadow_context(
        _ctx(freshness="UNKNOWN", health="FRESHNESS_UNAVAILABLE", age=None)
    )
    assert out["shadow_status"] == "SHADOW_BLOCK_UNKNOWN_FRESHNESS"
    assert out["shadow_action"] == "REFRESH_REQUIRED"


def test_line_change_requires_reprice():
    out = actionability_shadow_context(
        _ctx(
            health="LINE_CHANGED_NOT_COMPARABLE",
            trajectory="LINE_CHANGED_NOT_COMPARABLE",
            crossing="NOT_COMPARABLE",
        )
    )
    assert out["shadow_status"] == "SHADOW_REPRICE_LINE_CHANGE"
    assert out["shadow_action"] == "REPRICE_CURRENT_LINE"


def test_negative_value_is_pass():
    out = actionability_shadow_context(
        _ctx(
            value="NEGATIVE_VALUE",
            health="NEGATIVE_VALUE",
            ev=-0.04,
            headroom=-0.02,
        )
    )
    assert out["shadow_status"] == "SHADOW_PASS_NEGATIVE_VALUE"
    assert out["shadow_action"] == "PASS_AT_CURRENT_PRICE"


def test_negative_improving_is_wait_not_playable():
    out = actionability_shadow_context(
        _ctx(
            value="NEGATIVE_VALUE",
            health="NEGATIVE_VALUE_IMPROVING",
            trajectory="IMPROVING",
            crossing="NO_ZERO_EV_CROSSING",
            ev=-0.01,
            headroom=-0.005,
        )
    )
    assert out["shadow_status"] == "SHADOW_WAIT_NEGATIVE_IMPROVING"
    assert out["shadow_action"] == "WAIT_FOR_BETTER_PRICE"


def test_negative_worsening_is_pass():
    out = actionability_shadow_context(
        _ctx(
            value="NEGATIVE_VALUE",
            health="NEGATIVE_VALUE_WORSENING",
            trajectory="DETERIORATING",
            crossing="NO_ZERO_EV_CROSSING",
            ev=-0.08,
            headroom=-0.04,
        )
    )
    assert out["shadow_status"] == "SHADOW_PASS_NEGATIVE_VALUE"


def test_break_even_is_pass():
    out = actionability_shadow_context(
        _ctx(
            value="BREAK_EVEN",
            health="BREAK_EVEN",
            ev=0.0,
            headroom=0.0,
        )
    )
    assert out["shadow_status"] == "SHADOW_PASS_BREAK_EVEN"
    assert out["strict_positive_ev_required"] is True


def test_crossed_out_cannot_be_positive_current_value():
    with pytest.raises(MLBActionabilityShadowError):
        actionability_shadow_context(
            _ctx(
                value="POSITIVE_VALUE",
                health="POSITIVE_VALUE",
                trajectory="DETERIORATING",
                crossing="CROSSED_OUT_OF_POSITIVE_VALUE",
            )
        )


def test_input_is_not_mutated():
    context = _ctx()
    before = deepcopy(context)
    actionability_shadow_context(context)
    assert context == before


def test_output_preserves_identity_and_price_context():
    out = actionability_shadow_context(_ctx())
    assert out["official_game_id"] == 824911
    assert out["market"] == "Moneyline"
    assert out["selected_side"] == "home"
    assert out["current_market_odds"] == -120
    assert out["model_zero_ev_american_price_limit"] == -150


def test_output_protected_flags_all_false():
    out = actionability_shadow_context(_ctx())
    assert out["model_math_impact"] is False
    assert out["pick_strength_impact"] is False
    assert out["selection_impact"] is False
    assert out["ranking_impact"] is False
    assert out["risk_logic_impact"] is False
    assert out["wagering_impact"] is False
    assert out["durable_persistence"] is False


def test_shadow_contract_flags_are_explicit():
    out = actionability_shadow_context(_ctx())
    assert out["fresh_snapshot_required_for_shadow_playable"] is True
    assert out["aging_positive_value_requires_refresh"] is True
    assert out["stale_or_unknown_freshness_never_shadow_playable"] is True
    assert out["line_change_requires_reprice"] is True
    assert out["activation_enabled"] is False


@pytest.mark.parametrize(
    "field,value",
    [
        ("data_type", "wrong"),
        ("schema_version", 2),
        ("source", "OtherBook"),
        ("comparison_only", False),
        ("freshness_bands_are_display_only", False),
        ("ephemeral_session_history", False),
        ("durable_persistence", True),
        ("model_math_impact", True),
        ("pick_strength_impact", True),
        ("selection_impact", True),
        ("ranking_impact", True),
        ("risk_logic_impact", True),
        ("wagering_impact", True),
    ],
)
def test_invalid_step57_contract_fails_closed(field, value):
    context = _ctx()
    context[field] = value
    with pytest.raises(MLBActionabilityShadowError):
        actionability_shadow_context(context)


@pytest.mark.parametrize("freshness", ["", "HOT", "RECENT"])
def test_unknown_freshness_enum_fails_closed(freshness):
    with pytest.raises(MLBActionabilityShadowError):
        actionability_shadow_context(_ctx(freshness=freshness))


@pytest.mark.parametrize("value", ["", "PLUS_EV", "ZERO_EV"])
def test_unknown_value_enum_fails_closed(value):
    with pytest.raises(MLBActionabilityShadowError):
        actionability_shadow_context(_ctx(value=value))


@pytest.mark.parametrize("health", ["", "PLAY", "GOOD_PRICE"])
def test_unknown_health_enum_fails_closed(health):
    with pytest.raises(MLBActionabilityShadowError):
        actionability_shadow_context(_ctx(health=health))


@pytest.mark.parametrize("trajectory", ["", "UP", "DOWN"])
def test_unknown_trajectory_enum_fails_closed(trajectory):
    with pytest.raises(MLBActionabilityShadowError):
        actionability_shadow_context(_ctx(trajectory=trajectory))


@pytest.mark.parametrize("crossing", ["", "IN", "OUT"])
def test_unknown_crossing_enum_fails_closed(crossing):
    with pytest.raises(MLBActionabilityShadowError):
        actionability_shadow_context(_ctx(crossing=crossing))


def test_positive_value_requires_positive_ev():
    with pytest.raises(MLBActionabilityShadowError):
        actionability_shadow_context(_ctx(ev=-0.01, headroom=0.02))


def test_positive_value_requires_positive_headroom():
    with pytest.raises(MLBActionabilityShadowError):
        actionability_shadow_context(_ctx(ev=0.01, headroom=-0.01))


def test_negative_value_requires_negative_ev():
    with pytest.raises(MLBActionabilityShadowError):
        actionability_shadow_context(
            _ctx(value="NEGATIVE_VALUE", health="NEGATIVE_VALUE", ev=0.01, headroom=-0.01)
        )


def test_negative_value_requires_negative_headroom():
    with pytest.raises(MLBActionabilityShadowError):
        actionability_shadow_context(
            _ctx(value="NEGATIVE_VALUE", health="NEGATIVE_VALUE", ev=-0.01, headroom=0.01)
        )


def test_break_even_requires_zero_ev():
    with pytest.raises(MLBActionabilityShadowError):
        actionability_shadow_context(
            _ctx(value="BREAK_EVEN", health="BREAK_EVEN", ev=0.001, headroom=0.0)
        )


def test_break_even_requires_zero_headroom():
    with pytest.raises(MLBActionabilityShadowError):
        actionability_shadow_context(
            _ctx(value="BREAK_EVEN", health="BREAK_EVEN", ev=0.0, headroom=0.001)
        )


def test_negative_snapshot_age_fails_closed():
    with pytest.raises(MLBActionabilityShadowError):
        actionability_shadow_context(_ctx(age=-0.1))


def test_non_numeric_snapshot_age_fails_closed():
    with pytest.raises(MLBActionabilityShadowError):
        actionability_shadow_context(_ctx(age="30"))


def test_non_numeric_ev_fails_closed():
    context = _ctx()
    context["current_expected_value_per_unit"] = "0.05"
    with pytest.raises(MLBActionabilityShadowError):
        actionability_shadow_context(context)


def test_non_numeric_headroom_fails_closed():
    context = _ctx()
    context["value_headroom_probability"] = "0.03"
    with pytest.raises(MLBActionabilityShadowError):
        actionability_shadow_context(context)


def test_stale_overrides_negative_value_pass_with_refresh_required():
    out = actionability_shadow_context(
        _ctx(
            freshness="STALE",
            health="STALE_SNAPSHOT",
            value="NEGATIVE_VALUE",
            ev=-0.05,
            headroom=-0.02,
            age=500.0,
        )
    )
    assert out["shadow_status"] == "SHADOW_BLOCK_STALE"


def test_unknown_freshness_overrides_negative_value_pass_with_refresh_required():
    out = actionability_shadow_context(
        _ctx(
            freshness="UNKNOWN",
            health="FRESHNESS_UNAVAILABLE",
            value="NEGATIVE_VALUE",
            ev=-0.05,
            headroom=-0.02,
            age=None,
        )
    )
    assert out["shadow_status"] == "SHADOW_BLOCK_UNKNOWN_FRESHNESS"


def test_aging_positive_compressed_still_requires_refresh_not_execution():
    out = actionability_shadow_context(
        _ctx(
            freshness="AGING",
            health="POSITIVE_VALUE_COMPRESSED",
            trajectory="DETERIORATING",
            crossing="NO_ZERO_EV_CROSSING",
            age=200.0,
        )
    )
    assert out["shadow_status"] == "SHADOW_MONITOR_REFRESH"


def test_aging_positive_improving_still_requires_refresh_not_execution():
    out = actionability_shadow_context(
        _ctx(
            freshness="AGING",
            health="POSITIVE_VALUE_IMPROVING",
            trajectory="IMPROVING",
            crossing="NO_ZERO_EV_CROSSING",
            age=200.0,
        )
    )
    assert out["shadow_status"] == "SHADOW_MONITOR_REFRESH"
