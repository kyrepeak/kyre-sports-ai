from __future__ import annotations

import copy

import pytest

from sports_api.mlb_price_gate_canary_v1 import select_canary_game_ids
from sports_api.mlb_step6a_production_canary_v1 import (
    DEFAULT_ENABLED,
    DEFAULT_PERCENT,
    ENABLED_ENV_KEY,
    KILL_SWITCH_ENV_KEY,
    MAX_PRODUCTION_CANARY_PERCENT,
    PERCENT_ENV_KEY,
    ROLLBACK_QUERY_KEY,
    resolve_step6a_production_canary,
)


def _resolve(env=None, rollback=False):
    return resolve_step6a_production_canary(env or {}, rollback_requested=rollback)


def test_repository_default_intentionally_activates_ten_percent():
    out = _resolve()
    assert out["enabled"] is True
    assert out["requested_percent"] == 10.0
    assert out["effective_percent"] == 10.0
    assert out["control_source"] == "REPOSITORY_PRODUCTION_DEFAULT"


def test_default_constants_are_explicit_initial_rollout_values():
    assert DEFAULT_ENABLED is True
    assert DEFAULT_PERCENT == 10.0
    assert MAX_PRODUCTION_CANARY_PERCENT == 10.0


def test_default_twelve_game_slate_enrolls_exactly_one_game():
    out = _resolve()
    cohort = select_canary_game_ids(range(824900, 824912), enabled=out["enabled"], requested_percent=out["requested_percent"])
    assert cohort["selected_game_count"] == 1
    assert cohort["realized_percent"] <= 10.0


def test_default_twenty_game_slate_enrolls_exactly_two_games():
    out = _resolve()
    cohort = select_canary_game_ids(range(824900, 824920), enabled=out["enabled"], requested_percent=out["requested_percent"])
    assert cohort["selected_game_count"] == 2
    assert cohort["realized_percent"] == 10.0


def test_small_slate_never_exceeds_ten_percent_just_to_force_one_game():
    out = _resolve()
    cohort = select_canary_game_ids(range(824900, 824909), enabled=out["enabled"], requested_percent=out["requested_percent"])
    assert cohort["selected_game_count"] == 0
    assert cohort["realized_percent"] == 0.0


def test_explicit_host_disable_is_exact_off_zero():
    out = _resolve({ENABLED_ENV_KEY: "0"})
    assert out["enabled"] is False
    assert out["requested_percent"] == 0.0
    assert out["control_source"] == "HOST_ENV"


def test_explicit_host_enable_without_percent_uses_ten_percent_default():
    out = _resolve({ENABLED_ENV_KEY: "1"})
    assert out["enabled"] is True
    assert out["requested_percent"] == 10.0
    assert out["control_source"] == "HOST_ENV"


def test_explicit_host_percent_without_enable_uses_enabled_default():
    out = _resolve({PERCENT_ENV_KEY: "5"})
    assert out["enabled"] is True
    assert out["requested_percent"] == 5.0


def test_explicit_host_five_percent_is_preserved():
    out = _resolve({ENABLED_ENV_KEY: "true", PERCENT_ENV_KEY: "5"})
    assert out["enabled"] is True
    assert out["requested_percent"] == 5.0
    assert out["percent_bounded"] is False


def test_host_percent_above_phase_cap_is_bounded_to_ten():
    out = _resolve({ENABLED_ENV_KEY: "1", PERCENT_ENV_KEY: "25"})
    assert out["enabled"] is True
    assert out["requested_percent"] == 10.0
    assert out["percent_bounded"] is True


def test_host_percent_one_hundred_is_bounded_to_ten():
    out = _resolve({ENABLED_ENV_KEY: "1", PERCENT_ENV_KEY: "100"})
    assert out["requested_percent"] == 10.0
    assert out["effective_percent"] == 10.0


def test_host_zero_percent_disables_even_when_enabled_true():
    out = _resolve({ENABLED_ENV_KEY: "1", PERCENT_ENV_KEY: "0"})
    assert out["enabled"] is False
    assert out["requested_percent"] == 0.0


def test_negative_percent_fails_closed():
    out = _resolve({ENABLED_ENV_KEY: "1", PERCENT_ENV_KEY: "-1"})
    assert out["enabled"] is False
    assert out["requested_percent"] == 0.0
    assert out["config_valid"] is False


def test_invalid_percent_fails_closed():
    out = _resolve({ENABLED_ENV_KEY: "1", PERCENT_ENV_KEY: "banana"})
    assert out["enabled"] is False
    assert out["requested_percent"] == 0.0
    assert out["config_valid"] is False


def test_invalid_enabled_value_fails_closed():
    out = _resolve({ENABLED_ENV_KEY: "maybe"})
    assert out["enabled"] is False
    assert out["requested_percent"] == 0.0
    assert out["config_valid"] is False


@pytest.mark.parametrize("truthy", ["1", "true", "TRUE", "yes", "YES", "on", "enabled"])
def test_kill_switch_truthy_values_force_global_rollback(truthy):
    out = _resolve({KILL_SWITCH_ENV_KEY: truthy, ENABLED_ENV_KEY: "1", PERCENT_ENV_KEY: "10"})
    assert out["enabled"] is False
    assert out["requested_percent"] == 0.0
    assert out["control_source"] == "GLOBAL_KILL_SWITCH"


@pytest.mark.parametrize("falsey", ["0", "false", "FALSE", "no", "off", "disabled"])
def test_kill_switch_false_values_do_not_disable_default(falsey):
    out = _resolve({KILL_SWITCH_ENV_KEY: falsey})
    assert out["enabled"] is True
    assert out["requested_percent"] == 10.0
    assert out["control_source"] == "HOST_ENV"


def test_invalid_kill_switch_fails_closed_because_host_config_is_invalid():
    out = _resolve({KILL_SWITCH_ENV_KEY: "maybe"})
    assert out["enabled"] is False
    assert out["requested_percent"] == 0.0
    assert out["config_valid"] is False


def test_session_rollback_disables_repository_default():
    out = _resolve({}, rollback=True)
    assert out["enabled"] is False
    assert out["requested_percent"] == 0.0
    assert out["control_source"] == "STREAMLIT_SESSION_ROLLBACK"


def test_session_rollback_beats_explicit_host_enable_for_browser_safety():
    out = _resolve({ENABLED_ENV_KEY: "1", PERCENT_ENV_KEY: "10"}, rollback=True)
    assert out["enabled"] is False
    assert out["control_source"] == "STREAMLIT_SESSION_ROLLBACK"


def test_global_kill_switch_beats_session_rollback():
    out = _resolve({KILL_SWITCH_ENV_KEY: "1"}, rollback=True)
    assert out["enabled"] is False
    assert out["control_source"] == "GLOBAL_KILL_SWITCH"


def test_session_rollback_produces_empty_step510_cohort():
    out = _resolve({}, rollback=True)
    cohort = select_canary_game_ids(range(824900, 824912), enabled=out["enabled"], requested_percent=out["requested_percent"])
    assert cohort["selected_game_ids"] == []


def test_host_disable_produces_empty_step510_cohort():
    out = _resolve({ENABLED_ENV_KEY: "off", PERCENT_ENV_KEY: "10"})
    cohort = select_canary_game_ids(range(824900, 824912), enabled=out["enabled"], requested_percent=out["requested_percent"])
    assert cohort["selected_game_ids"] == []


def test_above_cap_host_request_cannot_enroll_more_than_ten_percent():
    out = _resolve({ENABLED_ENV_KEY: "1", PERCENT_ENV_KEY: "100"})
    cohort = select_canary_game_ids(range(824900, 824940), enabled=out["enabled"], requested_percent=out["requested_percent"])
    assert cohort["selected_game_count"] == 4
    assert cohort["realized_percent"] == 10.0


def test_resolver_does_not_mutate_environment_mapping():
    env = {ENABLED_ENV_KEY: "1", PERCENT_ENV_KEY: "7.5"}
    before = copy.deepcopy(env)
    _resolve(env)
    assert env == before


def test_decimal_host_percent_is_preserved_below_cap():
    out = _resolve({PERCENT_ENV_KEY: "7.5"})
    assert out["requested_percent"] == 7.5
    assert out["percent_bounded"] is False


def test_metadata_always_exposes_exact_rollback():
    for out in (
        _resolve(),
        _resolve({ENABLED_ENV_KEY: "0"}),
        _resolve({}, rollback=True),
        _resolve({KILL_SWITCH_ENV_KEY: "1"}),
    ):
        assert out["exact_rollback"] is True


def test_repository_default_metadata_is_not_mislabeled_as_host_control():
    out = _resolve()
    assert out["host_control_present"] is False
    assert out["control_source"] == "REPOSITORY_PRODUCTION_DEFAULT"


def test_host_configuration_metadata_is_explicit():
    out = _resolve({PERCENT_ENV_KEY: "5"})
    assert out["host_control_present"] is True
    assert out["control_source"] == "HOST_ENV"


def test_stable_control_names_are_nonsecret():
    assert ENABLED_ENV_KEY == "MLB_STEP6A_PRODUCTION_CANARY_ENABLED"
    assert PERCENT_ENV_KEY == "MLB_STEP6A_PRODUCTION_CANARY_PERCENT"
    assert KILL_SWITCH_ENV_KEY == "MLB_STEP6A_PRODUCTION_CANARY_KILL_SWITCH"
    assert ROLLBACK_QUERY_KEY == "mlb_step6a_rollback"


def test_phase_cap_metadata_is_always_ten_percent():
    assert _resolve()["max_production_canary_percent"] == 10.0
    assert _resolve({PERCENT_ENV_KEY: "100"})["max_production_canary_percent"] == 10.0


def test_default_config_is_valid():
    assert _resolve()["config_valid"] is True


def test_explicit_valid_host_config_is_valid():
    assert _resolve({ENABLED_ENV_KEY: "yes", PERCENT_ENV_KEY: "8"})["config_valid"] is True
