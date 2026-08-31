from __future__ import annotations

import math

import pytest

from sports_api.mlb_price_gate_canary_v1 import (
    COHORT_SALT,
    DATA_TYPE,
    MAX_CANARY_PERCENT,
    MLBPriceGateCanaryError,
    SCHEMA_VERSION,
    bounded_canary_percent,
    game_is_in_canary,
    select_canary_game_ids,
)


def _ids(n=12, start=824900):
    return list(range(start, start + n))


def test_contract_and_production_defaults():
    out = select_canary_game_ids(_ids(), enabled=False, requested_percent=0)
    assert out["data_type"] == DATA_TYPE
    assert out["schema_version"] == SCHEMA_VERSION
    assert out["cohort_salt"] == COHORT_SALT
    assert out["production_default_enabled"] is False
    assert out["production_default_percent"] == 0.0
    assert out["selected_game_ids"] == []


def test_disabled_is_exact_zero_even_with_requested_percent():
    out = select_canary_game_ids(_ids(), enabled=False, requested_percent=25)
    assert out["selected_game_count"] == 0
    assert out["realized_percent"] == 0.0


def test_zero_percent_is_exact_zero_even_when_enabled():
    out = select_canary_game_ids(_ids(), enabled=True, requested_percent=0)
    assert out["selected_game_ids"] == []


def test_twenty_five_percent_of_twelve_is_exactly_three_games():
    out = select_canary_game_ids(_ids(), enabled=True, requested_percent=25)
    assert out["target_game_count"] == 3
    assert out["selected_game_count"] == 3
    assert out["realized_percent"] == pytest.approx(25.0)


def test_ten_percent_of_twelve_uses_floor_and_never_exceeds_request():
    out = select_canary_game_ids(_ids(), enabled=True, requested_percent=10)
    assert out["selected_game_count"] == 1
    assert out["realized_percent"] < 10.0


def test_small_slate_does_not_break_hard_cap():
    out = select_canary_game_ids(_ids(3), enabled=True, requested_percent=25)
    assert out["selected_game_count"] == 0
    assert out["realized_percent"] == 0.0


def test_four_game_slate_can_enroll_one_at_cap():
    out = select_canary_game_ids(_ids(4), enabled=True, requested_percent=25)
    assert out["selected_game_count"] == 1
    assert out["realized_percent"] == pytest.approx(25.0)


def test_requested_above_cap_is_bounded_to_25_percent():
    out = select_canary_game_ids(_ids(), enabled=True, requested_percent=100)
    assert out["effective_percent"] == MAX_CANARY_PERCENT
    assert out["percent_bounded"] is True
    assert out["selected_game_count"] == 3


def test_negative_percent_is_bounded_to_zero():
    out = select_canary_game_ids(_ids(), enabled=True, requested_percent=-5)
    assert out["effective_percent"] == 0.0
    assert out["percent_bounded"] is True
    assert out["selected_game_count"] == 0


def test_exact_cap_is_not_marked_bounded():
    out = select_canary_game_ids(_ids(), enabled=True, requested_percent=25)
    assert out["percent_bounded"] is False


def test_order_does_not_change_assignment():
    ids = _ids()
    a = select_canary_game_ids(ids, enabled=True, requested_percent=25)
    b = select_canary_game_ids(list(reversed(ids)), enabled=True, requested_percent=25)
    assert a["selected_game_ids"] == b["selected_game_ids"]


def test_duplicates_do_not_change_assignment_or_denominator():
    ids = _ids()
    a = select_canary_game_ids(ids, enabled=True, requested_percent=25)
    b = select_canary_game_ids(ids + ids[:5], enabled=True, requested_percent=25)
    assert a["official_game_count"] == b["official_game_count"] == 12
    assert a["selected_game_ids"] == b["selected_game_ids"]


def test_assignment_is_deterministic_across_repeated_calls():
    first = select_canary_game_ids(_ids(100), enabled=True, requested_percent=17)
    for _ in range(5):
        assert select_canary_game_ids(_ids(100), enabled=True, requested_percent=17) == first


def test_realized_percent_never_exceeds_effective_percent_across_slate_sizes():
    for size in range(1, 101):
        for pct in (1, 5, 10, 17.5, 25, 50, 100):
            out = select_canary_game_ids(_ids(size), enabled=True, requested_percent=pct)
            assert out["realized_percent"] <= out["effective_percent"] + 1e-12
            assert out["effective_percent"] <= MAX_CANARY_PERCENT


def test_selected_ids_are_subset_of_official_ids():
    ids = _ids(40)
    out = select_canary_game_ids(ids, enabled=True, requested_percent=25)
    assert set(out["selected_game_ids"]).issubset(set(ids))


def test_game_level_atomicity_and_determinism_flags_are_explicit():
    out = select_canary_game_ids(_ids(), enabled=True, requested_percent=25)
    assert out["game_level_atomicity"] is True
    assert out["deterministic_assignment"] is True
    assert out["rollback_to_zero_is_exact"] is True


def test_protected_impact_flags_are_false():
    out = select_canary_game_ids(_ids(), enabled=True, requested_percent=25)
    assert out["model_math_impact"] is False
    assert out["pick_strength_impact"] is False
    assert out["ranking_math_impact"] is False
    assert out["risk_logic_impact"] is False
    assert out["wagering_impact"] is False
    assert out["durable_persistence"] is False


def test_game_is_in_canary_matches_selected_list():
    out = select_canary_game_ids(_ids(), enabled=True, requested_percent=25)
    for game_id in _ids():
        assert game_is_in_canary(game_id, out) == (game_id in out["selected_game_ids"])


def test_canonical_digit_string_game_ids_are_supported():
    out = select_canary_game_ids(["824900", "824901", "824902", "824903"], enabled=True, requested_percent=25)
    assert out["official_game_count"] == 4
    assert out["selected_game_count"] == 1


@pytest.mark.parametrize("bad", [True, False, None, 0, -1, 1.5, "1.5", "", "abc"])
def test_invalid_game_ids_fail_closed(bad):
    with pytest.raises(MLBPriceGateCanaryError):
        select_canary_game_ids([bad], enabled=True, requested_percent=25)


@pytest.mark.parametrize("bad", [None, "abc", float("nan"), float("inf"), -float("inf"), True, False])
def test_invalid_percent_fails_closed(bad):
    with pytest.raises(MLBPriceGateCanaryError):
        bounded_canary_percent(bad)


def test_enabled_must_be_boolean():
    with pytest.raises(MLBPriceGateCanaryError):
        select_canary_game_ids(_ids(), enabled=1, requested_percent=25)


def test_game_ids_must_be_iterable():
    with pytest.raises(MLBPriceGateCanaryError):
        select_canary_game_ids(None, enabled=True, requested_percent=25)


def test_game_is_in_canary_requires_certified_context():
    with pytest.raises(MLBPriceGateCanaryError):
        game_is_in_canary(824900, {})


def test_game_is_in_canary_requires_selected_list():
    out = select_canary_game_ids(_ids(), enabled=True, requested_percent=25)
    out["selected_game_ids"] = "824900"
    with pytest.raises(MLBPriceGateCanaryError):
        game_is_in_canary(824900, out)


def test_nonfinite_never_enters_output():
    out = select_canary_game_ids(_ids(), enabled=True, requested_percent=12.5)
    for key in ("requested_percent", "effective_percent", "max_canary_percent", "realized_percent"):
        assert math.isfinite(float(out[key]))
