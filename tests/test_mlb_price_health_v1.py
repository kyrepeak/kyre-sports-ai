from __future__ import annotations

from copy import deepcopy

import pytest

from sports_api.mlb_price_discipline_v1 import american_odds_implied_probability
from sports_api.mlb_price_health_v1 import (
    AGING_MAX_SECONDS,
    DATA_TYPE,
    FRESH_MAX_SECONDS,
    MLBPriceHealthError,
    SCHEMA_VERSION,
    price_health_context,
)


def _fair_odds(p: float) -> float:
    return -(100.0 * p / (1.0 - p)) if p >= 0.5 else 100.0 * (1.0 - p) / p


def _profit(odds: float) -> float:
    return odds / 100.0 if odds > 0 else 100.0 / (-odds)


def _ev(p: float, odds: float) -> float:
    return p * _profit(float(odds)) - (1.0 - p)


def _step56(
    *,
    game_id=824911,
    market="Moneyline",
    side="home",
    line=None,
    current_odds=-120,
    previous_odds=None,
    model_p=0.60,
    no_vig=0.55,
    age=30.0,
    movement_status="NO_PRIOR_OBSERVATION",
):
    current_ev = _ev(model_p, current_odds)
    movement_available = movement_status not in {"NO_PRIOR_OBSERVATION", "NO_NEW_OBSERVATION"}
    comparable = movement_status in {"BETTER_PRICE", "MORE_EXPENSIVE", "UNCHANGED"}
    previous_ev = _ev(model_p, previous_odds) if comparable and previous_odds is not None else None
    ev_delta = current_ev - previous_ev if previous_ev is not None else None
    return {
        "data_type": "mlb_market_movement_context_v1",
        "schema_version": 1,
        "source": "FanDuel",
        "official_game_id": game_id,
        "match_method": "official_mlb_game_id_exact",
        "fallback_matching_used": False,
        "market": market,
        "selected_side": side,
        "current_market_line": line,
        "current_market_odds": current_odds,
        "current_raw_break_even_probability": american_odds_implied_probability(current_odds),
        "current_no_vig_probability": no_vig,
        "current_model_probability": model_p,
        "current_expected_value_per_unit": current_ev,
        "current_zero_ev_american_price_limit": _fair_odds(model_p),
        "current_price_status": "POSITIVE_VALUE" if current_ev > 1e-12 else "NEGATIVE_VALUE" if current_ev < -1e-12 else "BREAK_EVEN",
        "current_collected_at_utc": "2026-08-31T07:00:00+00:00",
        "snapshot_age_seconds": age,
        "movement_available": movement_available,
        "price_comparison_comparable": comparable,
        "movement_status": movement_status,
        "previous_market_odds": previous_odds,
        "previous_market_line": line,
        "price_only_previous_ev_using_current_model": previous_ev,
        "price_only_ev_delta": ev_delta,
        "comparison_only": True,
        "ephemeral_session_history": True,
        "durable_persistence": False,
        "selection_impact": False,
        "ranking_impact": False,
        "wagering_impact": False,
    }


def test_baseline_positive_value_price_health_contract():
    result = price_health_context(_step56())
    assert result["data_type"] == DATA_TYPE
    assert result["schema_version"] == SCHEMA_VERSION
    assert result["source"] == "FanDuel"
    assert result["current_value_status"] == "POSITIVE_VALUE"
    assert result["value_trajectory"] == "NO_COMPARABLE_PRIOR"
    assert result["zero_ev_crossing_status"] == "NOT_COMPARABLE"
    assert result["price_health_status"] == "POSITIVE_VALUE"
    assert result["snapshot_freshness_status"] == "FRESH"
    assert result["comparison_only"] is True
    assert result["freshness_bands_are_display_only"] is True
    assert result["durable_persistence"] is False
    assert result["selection_impact"] is False
    assert result["ranking_impact"] is False
    assert result["wagering_impact"] is False


def test_input_is_not_mutated():
    context = _step56()
    before = deepcopy(context)
    price_health_context(context)
    assert context == before


def test_headroom_reconciles_model_minus_raw_break_even():
    context = _step56(current_odds=-120, model_p=0.60)
    result = price_health_context(context)
    expected = 0.60 - american_odds_implied_probability(-120)
    assert result["value_headroom_probability"] == pytest.approx(expected)
    assert result["value_headroom_percentage_points"] == pytest.approx(expected * 100.0)


@pytest.mark.parametrize(
    "age,expected",
    [
        (0.0, "FRESH"),
        (FRESH_MAX_SECONDS, "FRESH"),
        (FRESH_MAX_SECONDS + 0.001, "AGING"),
        (AGING_MAX_SECONDS, "AGING"),
        (AGING_MAX_SECONDS + 0.001, "STALE"),
    ],
)
def test_snapshot_freshness_bands(age, expected):
    result = price_health_context(_step56(age=age))
    assert result["snapshot_freshness_status"] == expected
    assert result["fresh_max_seconds"] == FRESH_MAX_SECONDS
    assert result["aging_max_seconds"] == AGING_MAX_SECONDS


def test_unknown_snapshot_age_fails_open_for_display_but_not_for_freshness_claim():
    result = price_health_context(_step56(age=None))
    assert result["snapshot_freshness_status"] == "UNKNOWN"
    assert result["snapshot_age_seconds"] is None
    assert result["price_health_status"] == "FRESHNESS_UNAVAILABLE"


def test_negative_snapshot_age_fails_closed():
    with pytest.raises(MLBPriceHealthError):
        price_health_context(_step56(age=-1.0))


def test_stale_snapshot_overrides_positive_value_display_status():
    result = price_health_context(_step56(age=AGING_MAX_SECONDS + 1.0))
    assert result["current_value_status"] == "POSITIVE_VALUE"
    assert result["price_health_status"] == "STALE_SNAPSHOT"


def test_better_price_classifies_improving_positive_value():
    result = price_health_context(
        _step56(
            current_odds=-110,
            previous_odds=-120,
            movement_status="BETTER_PRICE",
            model_p=0.60,
        )
    )
    assert result["value_trajectory"] == "IMPROVING"
    assert result["price_only_ev_delta"] > 0
    assert result["current_value_status"] == "POSITIVE_VALUE"
    assert result["price_health_status"] == "POSITIVE_VALUE_IMPROVING"


def test_more_expensive_price_classifies_compressed_positive_value():
    result = price_health_context(
        _step56(
            current_odds=-130,
            previous_odds=-120,
            movement_status="MORE_EXPENSIVE",
            model_p=0.60,
        )
    )
    assert result["value_trajectory"] == "DETERIORATING"
    assert result["price_only_ev_delta"] < 0
    assert result["current_value_status"] == "POSITIVE_VALUE"
    assert result["price_health_status"] == "POSITIVE_VALUE_COMPRESSED"


def test_unchanged_same_line_price_has_unchanged_trajectory():
    result = price_health_context(
        _step56(
            current_odds=-120,
            previous_odds=-120,
            movement_status="UNCHANGED",
            model_p=0.60,
        )
    )
    assert result["value_trajectory"] == "UNCHANGED"
    assert result["price_only_ev_delta"] == pytest.approx(0.0)
    assert result["price_health_status"] == "POSITIVE_VALUE"


def test_line_change_is_never_treated_as_same_price_comparison():
    context = _step56(
        market="Run Line",
        side="away",
        line=1.5,
        current_odds=-160,
        movement_status="LINE_CHANGED",
    )
    context["previous_market_line"] = 2.5
    result = price_health_context(context)
    assert result["value_trajectory"] == "LINE_CHANGED_NOT_COMPARABLE"
    assert result["zero_ev_crossing_status"] == "NOT_COMPARABLE"
    assert result["previous_ev_using_current_model"] is None
    assert result["price_only_ev_delta"] is None
    assert result["price_health_status"] == "LINE_CHANGED_NOT_COMPARABLE"


def test_line_change_marked_comparable_fails_closed():
    context = _step56(market="Total", side="over", line=8.5, movement_status="LINE_CHANGED")
    context["price_comparison_comparable"] = True
    with pytest.raises(MLBPriceHealthError):
        price_health_context(context)


def test_same_line_movement_without_comparable_prior_fails_closed():
    context = _step56(current_odds=-110, previous_odds=-120, movement_status="BETTER_PRICE")
    context["movement_available"] = False
    with pytest.raises(MLBPriceHealthError):
        price_health_context(context)


def test_crosses_into_positive_value_when_price_improves_through_zero_ev():
    result = price_health_context(
        _step56(
            current_odds=105,
            previous_odds=-120,
            movement_status="BETTER_PRICE",
            model_p=0.50,
            no_vig=0.48,
        )
    )
    assert result["previous_ev_using_current_model"] < 0
    assert result["current_expected_value_per_unit"] > 0
    assert result["zero_ev_crossing_status"] == "CROSSED_INTO_POSITIVE_VALUE"
    assert result["current_value_status"] == "POSITIVE_VALUE"


def test_crosses_out_of_positive_value_when_price_deteriorates_through_zero_ev():
    result = price_health_context(
        _step56(
            current_odds=-120,
            previous_odds=105,
            movement_status="MORE_EXPENSIVE",
            model_p=0.50,
            no_vig=0.52,
        )
    )
    assert result["previous_ev_using_current_model"] > 0
    assert result["current_expected_value_per_unit"] < 0
    assert result["zero_ev_crossing_status"] == "CROSSED_OUT_OF_POSITIVE_VALUE"
    assert result["current_value_status"] == "NEGATIVE_VALUE"
    assert result["price_health_status"] == "NEGATIVE_VALUE_WORSENING"


def test_negative_value_can_be_improving_without_becoming_positive():
    result = price_health_context(
        _step56(
            current_odds=-125,
            previous_odds=-140,
            movement_status="BETTER_PRICE",
            model_p=0.50,
            no_vig=0.50,
        )
    )
    assert result["current_value_status"] == "NEGATIVE_VALUE"
    assert result["value_trajectory"] == "IMPROVING"
    assert result["zero_ev_crossing_status"] == "NO_ZERO_EV_CROSSING"
    assert result["price_health_status"] == "NEGATIVE_VALUE_IMPROVING"


def test_break_even_current_price_is_classified():
    result = price_health_context(
        _step56(
            current_odds=100,
            movement_status="NO_PRIOR_OBSERVATION",
            model_p=0.50,
            no_vig=0.50,
        )
    )
    assert result["current_expected_value_per_unit"] == pytest.approx(0.0)
    assert result["current_value_status"] == "BREAK_EVEN"
    assert result["price_health_status"] == "BREAK_EVEN"


def test_no_new_observation_does_not_invent_trajectory():
    result = price_health_context(_step56(movement_status="NO_NEW_OBSERVATION"))
    assert result["value_trajectory"] == "NO_COMPARABLE_PRIOR"
    assert result["zero_ev_crossing_status"] == "NOT_COMPARABLE"


def test_ev_delta_must_reconcile_to_current_minus_previous_ev():
    context = _step56(current_odds=-110, previous_odds=-120, movement_status="BETTER_PRICE")
    context["price_only_ev_delta"] += 0.01
    with pytest.raises(MLBPriceHealthError):
        price_health_context(context)


def test_current_ev_must_reconcile_to_model_probability_and_price():
    context = _step56()
    context["current_expected_value_per_unit"] += 0.01
    with pytest.raises(MLBPriceHealthError):
        price_health_context(context)


@pytest.mark.parametrize(
    "field,value",
    [
        ("data_type", "wrong"),
        ("schema_version", 2),
        ("source", "OtherBook"),
        ("fallback_matching_used", True),
        ("comparison_only", False),
        ("ephemeral_session_history", False),
        ("durable_persistence", True),
        ("selection_impact", True),
        ("ranking_impact", True),
        ("wagering_impact", True),
    ],
)
def test_invalid_step56_contract_fails_closed(field, value):
    context = _step56()
    context[field] = value
    with pytest.raises(MLBPriceHealthError):
        price_health_context(context)


@pytest.mark.parametrize(
    "field,value",
    [
        ("official_game_id", None),
        ("official_game_id", 0),
        ("market", "Player Prop"),
        ("selected_side", "over"),
        ("current_market_odds", 50),
        ("current_model_probability", 1.0),
        ("current_raw_break_even_probability", 0.0),
        ("current_no_vig_probability", 1.0),
        ("current_zero_ev_american_price_limit", -50),
        ("movement_status", "FABRICATED_MOVE"),
    ],
)
def test_invalid_market_or_numeric_fields_fail_closed(field, value):
    context = _step56()
    context[field] = value
    with pytest.raises(MLBPriceHealthError):
        price_health_context(context)


def test_total_side_is_supported():
    result = price_health_context(
        _step56(market="Total", side="over", line=8.5, current_odds=-110, no_vig=0.50)
    )
    assert result["market"] == "Total"
    assert result["selected_side"] == "over"


def test_run_line_side_is_supported():
    result = price_health_context(
        _step56(market="Run Line", side="away", line=1.5, current_odds=-110, no_vig=0.50)
    )
    assert result["market"] == "Run Line"
    assert result["selected_side"] == "away"


def test_all_protected_impact_flags_remain_false():
    result = price_health_context(_step56())
    assert result["model_math_impact"] is False
    assert result["pick_strength_impact"] is False
    assert result["selection_impact"] is False
    assert result["ranking_impact"] is False
    assert result["risk_logic_impact"] is False
    assert result["wagering_impact"] is False
