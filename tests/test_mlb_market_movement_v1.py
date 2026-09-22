from __future__ import annotations

from copy import deepcopy

import pytest

from sports_api.mlb_market_movement_v1 import (
    DATA_TYPE,
    MLBMarketMovementError,
    OBSERVATION_DATA_TYPE,
    SCHEMA_VERSION,
    build_market_observation,
    canonical_utc_timestamp,
    compare_market_observations,
    observation_identity,
    observation_identity_key,
    parse_utc_timestamp,
)
from sports_api.mlb_price_discipline_v1 import american_odds_implied_probability


def _fair_odds(p: float) -> float:
    return -(100.0 * p / (1.0 - p)) if p >= 0.5 else 100.0 * (1.0 - p) / p


def _profit(odds: float) -> float:
    return odds / 100.0 if odds > 0 else 100.0 / (-odds)


def _step55(
    *,
    game_id=824911,
    market="Moneyline",
    side="home",
    line=None,
    odds=-142,
    no_vig=0.56,
    model_p=0.60,
):
    raw = american_odds_implied_probability(odds)
    ev = model_p * _profit(float(odds)) - (1.0 - model_p)
    return {
        "data_type": "mlb_price_discipline_context_v1",
        "schema_version": 1,
        "source": "FanDuel",
        "official_game_id": game_id,
        "match_method": "official_mlb_game_id_exact",
        "fallback_matching_used": False,
        "market": market,
        "selected_side": side,
        "market_line": line,
        "model_probability": model_p,
        "market_no_vig_probability": no_vig,
        "market_raw_break_even_probability": raw,
        "handicap_edge_probability": model_p - no_vig,
        "vig_drag_probability": raw - no_vig,
        "pricing_margin_probability": model_p - raw,
        "market_odds": odds,
        "zero_ev_american_price_limit": _fair_odds(model_p),
        "expected_value_per_unit": ev,
        "expected_value_percent": ev * 100.0,
        "current_price_status": "POSITIVE_VALUE" if ev > 1e-12 else "NEGATIVE_VALUE" if ev < -1e-12 else "BREAK_EVEN",
        "positive_expected_value": ev > 1e-12,
        "current_price_meets_model_fair_limit": ev >= -1e-12,
        "comparison_only": True,
        "selection_impact": False,
        "ranking_impact": False,
        "wagering_impact": False,
    }


def _obs(ts="2026-08-31T07:00:00Z", **kwargs):
    return build_market_observation(_step55(**kwargs), collected_at_utc=ts)


def test_parse_z_timestamp():
    dt = parse_utc_timestamp("2026-08-31T07:00:00Z")
    assert dt.isoformat() == "2026-08-31T07:00:00+00:00"


def test_parse_offset_normalizes_to_utc():
    assert canonical_utc_timestamp("2026-08-31T02:00:00-05:00") == "2026-08-31T07:00:00+00:00"


@pytest.mark.parametrize("value", [None, "", "not-a-time", "2026-08-31T07:00:00"])
def test_bad_or_naive_timestamp_fails_closed(value):
    with pytest.raises(MLBMarketMovementError):
        parse_utc_timestamp(value)


def test_build_observation_contract():
    observation = _obs()
    assert observation["data_type"] == OBSERVATION_DATA_TYPE
    assert observation["schema_version"] == SCHEMA_VERSION
    assert observation["source"] == "FanDuel"
    assert observation["official_game_id"] == 824911
    assert observation["market"] == "Moneyline"
    assert observation["selected_side"] == "home"
    assert observation["collected_at_utc"] == "2026-08-31T07:00:00+00:00"
    assert observation["comparison_only"] is True
    assert observation["durable_persistence"] is False


def test_build_observation_does_not_mutate_step55_input():
    ctx = _step55()
    before = deepcopy(ctx)
    build_market_observation(ctx, collected_at_utc="2026-08-31T07:00:00Z")
    assert ctx == before


def test_observation_identity_and_key_are_exact():
    observation = _obs()
    assert observation_identity(observation) == (824911, "Moneyline", "home")
    assert observation_identity_key(observation) == "824911|Moneyline|home"


def test_baseline_has_no_fabricated_movement():
    current = _obs()
    result = compare_market_observations(current, as_of_utc="2026-08-31T07:00:30Z")
    assert result["data_type"] == DATA_TYPE
    assert result["movement_status"] == "NO_PRIOR_OBSERVATION"
    assert result["movement_available"] is False
    assert result["price_comparison_comparable"] is False
    assert result["snapshot_age_seconds"] == pytest.approx(30.0)
    assert result["ephemeral_session_history"] is True
    assert result["durable_persistence"] is False
    assert result["selection_impact"] is False
    assert result["ranking_impact"] is False
    assert result["wagering_impact"] is False


def test_same_timestamp_identical_snapshot_is_no_new_observation():
    current = _obs()
    previous = deepcopy(current)
    result = compare_market_observations(current, previous)
    assert result["movement_status"] == "NO_NEW_OBSERVATION"
    assert result["movement_available"] is False
    assert result["seconds_since_previous_observation"] == pytest.approx(0.0)


def test_same_timestamp_conflicting_price_fails_closed():
    current = _obs(odds=-142)
    previous = _obs(odds=-140)
    with pytest.raises(MLBMarketMovementError):
        compare_market_observations(current, previous)


def test_previous_newer_than_current_fails_closed():
    current = _obs(ts="2026-08-31T07:00:00Z")
    previous = _obs(ts="2026-08-31T07:01:00Z")
    with pytest.raises(MLBMarketMovementError):
        compare_market_observations(current, previous)


def test_identity_mismatch_game_id_fails_closed():
    current = _obs(game_id=824911, ts="2026-08-31T07:01:00Z")
    previous = _obs(game_id=824912, ts="2026-08-31T07:00:00Z")
    with pytest.raises(MLBMarketMovementError):
        compare_market_observations(current, previous)


def test_identity_mismatch_market_fails_closed():
    current = _obs(market="Moneyline", side="home", ts="2026-08-31T07:01:00Z")
    previous = _obs(market="Total", side="over", line=8.5, ts="2026-08-31T07:00:00Z")
    with pytest.raises(MLBMarketMovementError):
        compare_market_observations(current, previous)


def test_identity_mismatch_side_fails_closed():
    current = _obs(side="home", ts="2026-08-31T07:01:00Z")
    previous = _obs(side="away", ts="2026-08-31T07:00:00Z")
    with pytest.raises(MLBMarketMovementError):
        compare_market_observations(current, previous)


def test_better_positive_price_is_detected():
    previous = _obs(odds=120, model_p=0.60, no_vig=0.44, ts="2026-08-31T07:00:00Z", side="away")
    current = _obs(odds=130, model_p=0.60, no_vig=0.43, ts="2026-08-31T07:01:00Z", side="away")
    result = compare_market_observations(current, previous)
    assert result["movement_status"] == "BETTER_PRICE"
    assert result["price_direction"] == "BETTER_PRICE"
    assert result["price_comparison_comparable"] is True
    assert result["raw_break_even_probability_delta"] < 0
    assert result["american_odds_delta"] == pytest.approx(10.0)
    assert result["price_only_ev_delta"] > 0
    assert result["seconds_since_previous_observation"] == pytest.approx(60.0)


def test_more_expensive_positive_price_is_detected():
    previous = _obs(odds=130, model_p=0.60, no_vig=0.43, ts="2026-08-31T07:00:00Z", side="away")
    current = _obs(odds=120, model_p=0.60, no_vig=0.44, ts="2026-08-31T07:01:00Z", side="away")
    result = compare_market_observations(current, previous)
    assert result["movement_status"] == "MORE_EXPENSIVE"
    assert result["raw_break_even_probability_delta"] > 0
    assert result["price_only_ev_delta"] < 0


def test_better_negative_price_is_detected():
    previous = _obs(odds=-130, model_p=0.60, no_vig=0.56, ts="2026-08-31T07:00:00Z")
    current = _obs(odds=-120, model_p=0.60, no_vig=0.55, ts="2026-08-31T07:01:00Z")
    result = compare_market_observations(current, previous)
    assert result["movement_status"] == "BETTER_PRICE"
    assert result["raw_break_even_probability_delta"] < 0
    assert result["price_only_ev_delta"] > 0


def test_more_expensive_negative_price_is_detected():
    previous = _obs(odds=-120, model_p=0.60, no_vig=0.55, ts="2026-08-31T07:00:00Z")
    current = _obs(odds=-130, model_p=0.60, no_vig=0.56, ts="2026-08-31T07:01:00Z")
    result = compare_market_observations(current, previous)
    assert result["movement_status"] == "MORE_EXPENSIVE"
    assert result["raw_break_even_probability_delta"] > 0
    assert result["price_only_ev_delta"] < 0


def test_unchanged_price_newer_snapshot_is_real_but_zero_price_move():
    previous = _obs(odds=-120, model_p=0.60, no_vig=0.55, ts="2026-08-31T07:00:00Z")
    current = _obs(odds=-120, model_p=0.60, no_vig=0.55, ts="2026-08-31T07:01:00Z")
    result = compare_market_observations(current, previous)
    assert result["movement_available"] is True
    assert result["movement_status"] == "UNCHANGED"
    assert result["raw_break_even_probability_delta"] == pytest.approx(0.0)
    assert result["price_only_ev_delta"] == pytest.approx(0.0)


def test_no_vig_bullish_direction_is_separate_from_price_direction():
    previous = _obs(odds=-120, model_p=0.60, no_vig=0.53, ts="2026-08-31T07:00:00Z")
    current = _obs(odds=-120, model_p=0.60, no_vig=0.55, ts="2026-08-31T07:01:00Z")
    result = compare_market_observations(current, previous)
    assert result["price_direction"] == "UNCHANGED"
    assert result["no_vig_direction"] == "MARKET_MORE_BULLISH_ON_SIDE"
    assert result["no_vig_probability_delta"] == pytest.approx(0.02)


def test_no_vig_less_bullish_direction_is_separate_from_price_direction():
    previous = _obs(odds=-120, model_p=0.60, no_vig=0.55, ts="2026-08-31T07:00:00Z")
    current = _obs(odds=-120, model_p=0.60, no_vig=0.53, ts="2026-08-31T07:01:00Z")
    result = compare_market_observations(current, previous)
    assert result["no_vig_direction"] == "MARKET_LESS_BULLISH_ON_SIDE"


def test_runline_line_change_suppresses_direct_price_comparison():
    previous = _obs(market="Run Line", side="away", line=1.5, odds=-165, no_vig=0.60, model_p=0.64, ts="2026-08-31T07:00:00Z")
    current = _obs(market="Run Line", side="away", line=2.5, odds=-210, no_vig=0.68, model_p=0.64, ts="2026-08-31T07:01:00Z")
    result = compare_market_observations(current, previous)
    assert result["movement_status"] == "LINE_CHANGED"
    assert result["line_changed"] is True
    assert result["line_delta"] == pytest.approx(1.0)
    assert result["price_comparison_comparable"] is False
    assert result["raw_break_even_probability_delta"] is None
    assert result["no_vig_probability_delta"] is None
    assert result["american_odds_delta"] is None
    assert result["price_only_ev_delta"] is None
    assert result["price_direction"] == "NOT_COMPARABLE_DIFFERENT_LINE"


def test_total_line_change_suppresses_direct_price_comparison():
    previous = _obs(market="Total", side="over", line=8.5, odds=-105, no_vig=0.49, model_p=0.55, ts="2026-08-31T07:00:00Z")
    current = _obs(market="Total", side="over", line=9.0, odds=-110, no_vig=0.50, model_p=0.55, ts="2026-08-31T07:01:00Z")
    result = compare_market_observations(current, previous)
    assert result["movement_status"] == "LINE_CHANGED"
    assert result["line_delta"] == pytest.approx(0.5)
    assert result["price_comparison_comparable"] is False


def test_same_runline_line_remains_price_comparable():
    previous = _obs(market="Run Line", side="away", line=1.5, odds=-165, no_vig=0.60, model_p=0.64, ts="2026-08-31T07:00:00Z")
    current = _obs(market="Run Line", side="away", line=1.5, odds=-155, no_vig=0.59, model_p=0.64, ts="2026-08-31T07:01:00Z")
    result = compare_market_observations(current, previous)
    assert result["line_changed"] is False
    assert result["price_comparison_comparable"] is True
    assert result["line_delta"] == pytest.approx(0.0)


def test_price_only_ev_holds_current_model_probability_constant():
    previous = _obs(odds=-120, model_p=0.52, no_vig=0.53, ts="2026-08-31T07:00:00Z")
    current = _obs(odds=-110, model_p=0.60, no_vig=0.54, ts="2026-08-31T07:01:00Z")
    result = compare_market_observations(current, previous)
    expected_previous_using_current_model = 0.60 * (100.0 / 120.0) - 0.40
    assert result["ev_comparison_model_probability"] == pytest.approx(0.60)
    assert result["ev_comparison_holds_current_model_probability_constant"] is True
    assert result["price_only_previous_ev_using_current_model"] == pytest.approx(expected_previous_using_current_model)
    assert result["price_only_previous_ev_using_current_model"] != pytest.approx(previous["expected_value_per_unit"])


def test_snapshot_age_allows_small_clock_skew_and_clamps_zero():
    current = _obs(ts="2026-08-31T07:00:03Z")
    result = compare_market_observations(current, as_of_utc="2026-08-31T07:00:00Z")
    assert result["snapshot_age_seconds"] == pytest.approx(0.0)


def test_snapshot_age_rejects_large_future_timestamp():
    current = _obs(ts="2026-08-31T07:00:06Z")
    with pytest.raises(MLBMarketMovementError):
        compare_market_observations(current, as_of_utc="2026-08-31T07:00:00Z")


def test_snapshot_age_can_be_omitted_without_guessing():
    result = compare_market_observations(_obs())
    assert result["snapshot_age_seconds"] is None


@pytest.mark.parametrize("field,value", [
    ("data_type", "wrong"),
    ("schema_version", 2),
    ("source", "OtherBook"),
    ("fallback_matching_used", True),
    ("comparison_only", False),
    ("durable_persistence", True),
])
def test_invalid_observation_contract_fails_closed(field, value):
    observation = _obs()
    observation[field] = value
    with pytest.raises(MLBMarketMovementError):
        compare_market_observations(observation)


@pytest.mark.parametrize("field", ["selection_impact", "ranking_impact", "wagering_impact"])
def test_build_requires_step55_no_impact_invariants(field):
    ctx = _step55()
    ctx[field] = True
    with pytest.raises(MLBMarketMovementError):
        build_market_observation(ctx, collected_at_utc="2026-08-31T07:00:00Z")


def test_build_wrong_step55_data_type_fails_closed():
    ctx = _step55()
    ctx["data_type"] = "wrong"
    with pytest.raises(MLBMarketMovementError):
        build_market_observation(ctx, collected_at_utc="2026-08-31T07:00:00Z")


def test_build_wrong_step55_source_fails_closed():
    ctx = _step55()
    ctx["source"] = "OtherBook"
    with pytest.raises(MLBMarketMovementError):
        build_market_observation(ctx, collected_at_utc="2026-08-31T07:00:00Z")


def test_build_bad_step55_timestamp_fails_closed():
    with pytest.raises(MLBMarketMovementError):
        build_market_observation(_step55(), collected_at_utc="not-a-time")


def test_observation_bad_ev_reconciliation_fails_closed():
    observation = _obs()
    observation["expected_value_per_unit"] += 0.01
    with pytest.raises(MLBMarketMovementError):
        compare_market_observations(observation)


def test_observation_invalid_market_side_fails_closed():
    observation = _obs()
    observation["selected_side"] = "over"
    with pytest.raises(MLBMarketMovementError):
        compare_market_observations(observation)


def test_observation_bad_american_odds_fails_closed():
    observation = _obs()
    observation["market_odds"] = 50
    with pytest.raises(MLBMarketMovementError):
        compare_market_observations(observation)


def test_compare_does_not_mutate_inputs():
    current = _obs(odds=-120, ts="2026-08-31T07:01:00Z")
    previous = _obs(odds=-130, ts="2026-08-31T07:00:00Z")
    current_before = deepcopy(current)
    previous_before = deepcopy(previous)
    compare_market_observations(current, previous, as_of_utc="2026-08-31T07:01:10Z")
    assert current == current_before
    assert previous == previous_before
