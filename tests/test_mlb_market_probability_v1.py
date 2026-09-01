from __future__ import annotations

from copy import deepcopy
import math

import pytest

from sports_api.mlb_market_probability_v1 import (
    DATA_TYPE,
    METHOD,
    MLBMarketProbabilityError,
    SCHEMA_VERSION,
    american_odds_to_implied_probability,
    derive_market_probability_contexts,
    market_probability_context,
    two_way_no_vig,
)


def _context(game_id: int = 824911) -> dict:
    return {
        "official_game_id": game_id,
        "sportsbook": "FanDuel",
        "match_method": "official_mlb_game_id_exact",
        "fallback_matching_used": False,
        "scheduled_start_utc": "2026-08-31T19:05:00+00:00",
        "source_event_id": "event-1",
        "moneyline": {"away_odds": 120, "home_odds": -142},
        "run_line": {
            "away_line": 1.5,
            "away_odds": -165,
            "home_line": -1.5,
            "home_odds": 140,
        },
        "total": {"line": 8.5, "over_odds": -105, "under_odds": -115},
    }


def test_positive_even_money_implied_probability():
    assert american_odds_to_implied_probability(100) == pytest.approx(0.5)


def test_negative_even_money_implied_probability():
    assert american_odds_to_implied_probability(-100) == pytest.approx(0.5)


def test_positive_150_implied_probability():
    assert american_odds_to_implied_probability(150) == pytest.approx(0.4)


def test_negative_200_implied_probability():
    assert american_odds_to_implied_probability(-200) == pytest.approx(2.0 / 3.0)


def test_negative_110_implied_probability():
    assert american_odds_to_implied_probability(-110) == pytest.approx(110.0 / 210.0)


@pytest.mark.parametrize(
    "value",
    [None, True, False, "-110", 0, 99, -99, float("nan"), float("inf"), -float("inf")],
)
def test_invalid_american_odds_fail_closed(value):
    with pytest.raises(MLBMarketProbabilityError):
        american_odds_to_implied_probability(value)


def test_symmetric_two_way_market_normalizes_to_fifty_fifty():
    result = two_way_no_vig(-110, -110)
    assert result["left_no_vig_probability"] == pytest.approx(0.5)
    assert result["right_no_vig_probability"] == pytest.approx(0.5)
    assert result["hold_probability"] == pytest.approx((220.0 / 210.0) - 1.0)


def test_asymmetric_two_way_market_uses_proportional_normalization():
    result = two_way_no_vig(120, -142)
    left = 100.0 / 220.0
    right = 142.0 / 242.0
    total = left + right
    assert result["left_implied_probability"] == pytest.approx(left)
    assert result["right_implied_probability"] == pytest.approx(right)
    assert result["left_no_vig_probability"] == pytest.approx(left / total)
    assert result["right_no_vig_probability"] == pytest.approx(right / total)
    assert result["hold_probability"] == pytest.approx(total - 1.0)


def test_each_no_vig_pair_sums_to_one():
    for left, right in [(120, -142), (-165, 140), (-105, -115), (100, 100)]:
        result = two_way_no_vig(left, right)
        assert result["left_no_vig_probability"] + result["right_no_vig_probability"] == pytest.approx(1.0)


def test_market_probability_context_contract_and_values():
    result = market_probability_context(_context())
    assert result["data_type"] == DATA_TYPE
    assert result["schema_version"] == SCHEMA_VERSION
    assert result["source"] == "FanDuel"
    assert result["official_game_id"] == 824911
    assert result["match_method"] == "official_mlb_game_id_exact"
    assert result["fallback_matching_used"] is False
    assert result["probability_method"] == METHOD
    assert set(result) >= {"moneyline", "run_line", "total"}


def test_market_probability_context_preserves_raw_lines_and_odds():
    raw = _context()
    result = market_probability_context(raw)
    assert result["moneyline"]["away"]["odds"] == raw["moneyline"]["away_odds"]
    assert result["moneyline"]["home"]["odds"] == raw["moneyline"]["home_odds"]
    assert result["run_line"]["away"]["line"] == raw["run_line"]["away_line"]
    assert result["run_line"]["away"]["odds"] == raw["run_line"]["away_odds"]
    assert result["run_line"]["home"]["line"] == raw["run_line"]["home_line"]
    assert result["run_line"]["home"]["odds"] == raw["run_line"]["home_odds"]
    assert result["total"]["line"] == raw["total"]["line"]
    assert result["total"]["over"]["odds"] == raw["total"]["over_odds"]
    assert result["total"]["under"]["odds"] == raw["total"]["under_odds"]


def test_market_probability_context_does_not_mutate_input():
    raw = _context()
    before = deepcopy(raw)
    market_probability_context(raw)
    assert raw == before


def test_market_probability_context_all_market_pairs_sum_to_one():
    result = market_probability_context(_context())
    pairs = [
        (result["moneyline"]["away"], result["moneyline"]["home"]),
        (result["run_line"]["away"], result["run_line"]["home"]),
        (result["total"]["over"], result["total"]["under"]),
    ]
    for left, right in pairs:
        assert left["no_vig_probability"] + right["no_vig_probability"] == pytest.approx(1.0)


def test_market_probability_context_hold_matches_raw_overround():
    result = market_probability_context(_context())
    pairs = [
        (result["moneyline"], "away", "home"),
        (result["run_line"], "away", "home"),
        (result["total"], "over", "under"),
    ]
    for market, left_name, right_name in pairs:
        expected = (
            market[left_name]["implied_probability"]
            + market[right_name]["implied_probability"]
            - 1.0
        )
        assert market["hold_probability"] == pytest.approx(expected)


def test_market_probability_context_rejects_wrong_sportsbook():
    raw = _context()
    raw["sportsbook"] = "OtherBook"
    with pytest.raises(MLBMarketProbabilityError):
        market_probability_context(raw)


def test_market_probability_context_rejects_fallback_identity():
    raw = _context()
    raw["fallback_matching_used"] = True
    with pytest.raises(MLBMarketProbabilityError):
        market_probability_context(raw)


def test_market_probability_context_requires_complete_market_set():
    raw = _context()
    raw.pop("total")
    with pytest.raises(MLBMarketProbabilityError):
        market_probability_context(raw)


def test_derive_multiple_contexts_preserves_exact_game_ids():
    state = {
        "match_method": "official_mlb_game_id_exact",
        "fallback_matching_used": False,
        "contexts_by_game_id": {
            824911: _context(824911),
            824912: _context(824912),
        },
    }
    result = derive_market_probability_contexts(state)
    assert result["data_type"] == DATA_TYPE
    assert result["schema_version"] == SCHEMA_VERSION
    assert result["probability_method"] == METHOD
    assert result["fallback_matching_used"] is False
    assert result["input_context_count"] == 2
    assert result["derived_context_count"] == 2
    assert sorted(result["contexts_by_game_id"]) == [824911, 824912]
    assert result["unusable_game_ids"] == []


def test_derive_fails_closed_for_one_unusable_context_without_losing_good_game():
    bad = _context(824912)
    bad["moneyline"]["away_odds"] = 0
    state = {
        "match_method": "official_mlb_game_id_exact",
        "fallback_matching_used": False,
        "contexts_by_game_id": {
            824911: _context(824911),
            824912: bad,
        },
    }
    result = derive_market_probability_contexts(state)
    assert result["derived_context_count"] == 1
    assert sorted(result["contexts_by_game_id"]) == [824911]
    assert result["unusable_game_ids"] == [824912]


def test_derive_rejects_missing_context_mapping():
    with pytest.raises(MLBMarketProbabilityError):
        derive_market_probability_contexts({"contexts_by_game_id": None})


def test_all_derived_probabilities_are_finite_and_bounded():
    result = market_probability_context(_context())
    for market_name, left_name, right_name in [
        ("moneyline", "away", "home"),
        ("run_line", "away", "home"),
        ("total", "over", "under"),
    ]:
        market = result[market_name]
        for side_name in (left_name, right_name):
            side = market[side_name]
            for field in ("implied_probability", "no_vig_probability"):
                value = side[field]
                assert math.isfinite(value)
                assert 0.0 <= value <= 1.0
