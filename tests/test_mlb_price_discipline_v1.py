from __future__ import annotations

from copy import deepcopy

import pytest

from sports_api.mlb_price_discipline_v1 import (
    DATA_TYPE,
    MLBPriceDisciplineError,
    SCHEMA_VERSION,
    american_odds_implied_probability,
    current_price_status,
    price_discipline_context,
)


def _ctx(
    *,
    game_id=824911,
    model_probability=0.60,
    market_no_vig_probability=0.56,
    market_odds=-142,
    market="Moneyline",
    selected_side="home",
    market_line=None,
):
    # These fields intentionally mirror the certified Step 5.4 contract.
    if model_probability >= 0.5:
        fair = -(100.0 * model_probability / (1.0 - model_probability))
    else:
        fair = 100.0 * (1.0 - model_probability) / model_probability
    if market_odds > 0:
        profit = market_odds / 100.0
    else:
        profit = 100.0 / (-market_odds)
    ev = model_probability * profit - (1.0 - model_probability)
    return {
        "data_type": "mlb_model_market_edge_context_v1",
        "schema_version": 1,
        "source": "FanDuel",
        "official_game_id": game_id,
        "match_method": "official_mlb_game_id_exact",
        "fallback_matching_used": False,
        "market": market,
        "selected_side": selected_side,
        "market_line": market_line,
        "model_probability": model_probability,
        "market_no_vig_probability": market_no_vig_probability,
        "edge_probability": model_probability - market_no_vig_probability,
        "edge_percentage_points": (model_probability - market_no_vig_probability) * 100.0,
        "market_odds": market_odds,
        "model_fair_american_odds": fair,
        "expected_value_per_unit": ev,
        "expected_value_percent": ev * 100.0,
        "comparison_only": True,
    }


def test_positive_american_implied_probability():
    assert american_odds_implied_probability(150) == pytest.approx(0.4)


def test_negative_american_implied_probability():
    assert american_odds_implied_probability(-150) == pytest.approx(0.6)


def test_even_money_positive():
    assert american_odds_implied_probability(100) == pytest.approx(0.5)


def test_even_money_negative():
    assert american_odds_implied_probability(-100) == pytest.approx(0.5)


@pytest.mark.parametrize("odds", [None, True, False, 0, 99, -99, float("nan")])
def test_invalid_american_odds_fail_closed(odds):
    with pytest.raises(MLBPriceDisciplineError):
        american_odds_implied_probability(odds)


def test_current_price_status_positive():
    assert current_price_status(0.01) == "POSITIVE_VALUE"


def test_current_price_status_negative():
    assert current_price_status(-0.01) == "NEGATIVE_VALUE"


def test_current_price_status_break_even():
    assert current_price_status(0.0) == "BREAK_EVEN"


def test_current_price_status_respects_tolerance():
    assert current_price_status(5e-13) == "BREAK_EVEN"
    assert current_price_status(-5e-13) == "BREAK_EVEN"


def test_price_discipline_contract_positive_value():
    ctx = _ctx(model_probability=0.60, market_no_vig_probability=0.56, market_odds=-142)
    result = price_discipline_context(ctx)
    raw = 142.0 / 242.0
    assert result["data_type"] == DATA_TYPE
    assert result["schema_version"] == SCHEMA_VERSION
    assert result["source"] == "FanDuel"
    assert result["official_game_id"] == 824911
    assert result["market"] == "Moneyline"
    assert result["selected_side"] == "home"
    assert result["market_raw_break_even_probability"] == pytest.approx(raw)
    assert result["handicap_edge_probability"] == pytest.approx(0.04)
    assert result["vig_drag_probability"] == pytest.approx(raw - 0.56)
    assert result["pricing_margin_probability"] == pytest.approx(0.60 - raw)
    assert result["zero_ev_american_price_limit"] == pytest.approx(-150.0)
    assert result["current_price_status"] == "POSITIVE_VALUE"
    assert result["positive_expected_value"] is True
    assert result["current_price_meets_model_fair_limit"] is True
    assert result["comparison_only"] is True
    assert result["selection_impact"] is False
    assert result["ranking_impact"] is False
    assert result["wagering_impact"] is False


def test_negative_value_status_when_price_is_too_expensive():
    ctx = _ctx(model_probability=0.55, market_no_vig_probability=0.52, market_odds=-150)
    result = price_discipline_context(ctx)
    assert result["market_raw_break_even_probability"] == pytest.approx(0.60)
    assert result["pricing_margin_probability"] == pytest.approx(-0.05)
    assert result["current_price_status"] == "NEGATIVE_VALUE"
    assert result["positive_expected_value"] is False
    assert result["current_price_meets_model_fair_limit"] is False


def test_break_even_status_exact_model_fair_price_favorite():
    ctx = _ctx(model_probability=0.60, market_no_vig_probability=0.58, market_odds=-150)
    result = price_discipline_context(ctx)
    assert result["market_raw_break_even_probability"] == pytest.approx(0.60)
    assert result["expected_value_per_unit"] == pytest.approx(0.0)
    assert result["current_price_status"] == "BREAK_EVEN"
    assert result["current_price_meets_model_fair_limit"] is True


def test_break_even_status_exact_model_fair_price_underdog():
    ctx = _ctx(model_probability=0.40, market_no_vig_probability=0.38, market_odds=150)
    result = price_discipline_context(ctx)
    assert result["market_raw_break_even_probability"] == pytest.approx(0.40)
    assert result["zero_ev_american_price_limit"] == pytest.approx(150.0)
    assert result["current_price_status"] == "BREAK_EVEN"


def test_vig_identity_handicap_minus_vig_equals_price_margin():
    result = price_discipline_context(_ctx())
    assert result["handicap_edge_probability"] - result["vig_drag_probability"] == pytest.approx(
        result["pricing_margin_probability"]
    )


def test_expected_value_and_price_margin_have_same_sign_positive():
    result = price_discipline_context(_ctx(model_probability=0.60, market_odds=-142))
    assert result["expected_value_per_unit"] > 0
    assert result["pricing_margin_probability"] > 0


def test_expected_value_and_price_margin_have_same_sign_negative():
    result = price_discipline_context(_ctx(model_probability=0.50, market_no_vig_probability=0.48, market_odds=-120))
    assert result["expected_value_per_unit"] < 0
    assert result["pricing_margin_probability"] < 0


def test_runline_fields_are_preserved():
    result = price_discipline_context(
        _ctx(
            market="Run Line",
            selected_side="away",
            market_line=1.5,
            model_probability=0.64,
            market_no_vig_probability=0.60,
            market_odds=-165,
        )
    )
    assert result["market"] == "Run Line"
    assert result["selected_side"] == "away"
    assert result["market_line"] == pytest.approx(1.5)


def test_total_fields_are_preserved():
    result = price_discipline_context(
        _ctx(
            market="Total",
            selected_side="over",
            market_line=8.5,
            model_probability=0.55,
            market_no_vig_probability=0.49,
            market_odds=-105,
        )
    )
    assert result["market"] == "Total"
    assert result["selected_side"] == "over"
    assert result["market_line"] == pytest.approx(8.5)


def test_wrong_data_type_fails_closed():
    ctx = _ctx()
    ctx["data_type"] = "wrong"
    with pytest.raises(MLBPriceDisciplineError):
        price_discipline_context(ctx)


def test_wrong_schema_fails_closed():
    ctx = _ctx()
    ctx["schema_version"] = 2
    with pytest.raises(MLBPriceDisciplineError):
        price_discipline_context(ctx)


def test_wrong_source_fails_closed():
    ctx = _ctx()
    ctx["source"] = "OtherBook"
    with pytest.raises(MLBPriceDisciplineError):
        price_discipline_context(ctx)


def test_fallback_context_fails_closed():
    ctx = _ctx()
    ctx["fallback_matching_used"] = True
    with pytest.raises(MLBPriceDisciplineError):
        price_discipline_context(ctx)


def test_comparison_only_invariant_required():
    ctx = _ctx()
    ctx["comparison_only"] = False
    with pytest.raises(MLBPriceDisciplineError):
        price_discipline_context(ctx)


def test_bad_official_game_id_fails_closed():
    ctx = _ctx()
    ctx["official_game_id"] = "not-an-id"
    with pytest.raises(MLBPriceDisciplineError):
        price_discipline_context(ctx)


@pytest.mark.parametrize("p", [None, True, False, 0, 1, -0.1, 1.1, float("nan")])
def test_bad_model_probability_fails_closed(p):
    ctx = _ctx()
    ctx["model_probability"] = p
    with pytest.raises(MLBPriceDisciplineError):
        price_discipline_context(ctx)


@pytest.mark.parametrize("p", [None, True, False, 0, 1, -0.1, 1.1, float("nan")])
def test_bad_no_vig_probability_fails_closed(p):
    ctx = _ctx()
    ctx["market_no_vig_probability"] = p
    with pytest.raises(MLBPriceDisciplineError):
        price_discipline_context(ctx)


def test_step54_ev_reconciliation_failure_fails_closed():
    ctx = _ctx()
    ctx["expected_value_per_unit"] += 0.01
    with pytest.raises(MLBPriceDisciplineError):
        price_discipline_context(ctx)


def test_step54_fair_odds_reconciliation_failure_fails_closed():
    ctx = _ctx()
    ctx["model_fair_american_odds"] -= 10
    with pytest.raises(MLBPriceDisciplineError):
        price_discipline_context(ctx)


def test_step54_edge_reconciliation_failure_fails_closed():
    ctx = _ctx()
    ctx["edge_probability"] += 0.01
    with pytest.raises(MLBPriceDisciplineError):
        price_discipline_context(ctx)


def test_input_context_is_not_mutated():
    ctx = _ctx()
    before = deepcopy(ctx)
    price_discipline_context(ctx)
    assert ctx == before
