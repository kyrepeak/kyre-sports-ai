from __future__ import annotations

import copy

import pytest

from sports_api.mlb_price_gate_canary_v1 import MAX_CANARY_PERCENT, select_canary_game_ids
from sports_api.mlb_streamlit_canary_control_v1 import (
    DATA_TYPE,
    MLBStreamlitCanaryControlError,
    QUERY_ENABLED_KEY,
    QUERY_PERCENT_KEY,
    SCHEMA_VERSION,
    resolve_streamlit_canary_config,
)


def _base(enabled=False, percent=0.0, valid=True):
    return {
        "enabled": enabled,
        "requested_percent": percent,
        "config_valid": valid,
        "enabled_env_key": "MLB_STEP5_10_CANARY_ENABLED",
        "percent_env_key": "MLB_STEP5_10_CANARY_PERCENT",
        "production_default_enabled": False,
        "production_default_percent": 0.0,
    }


def _resolve(*, base=None, host=False, enabled=None, percent=None):
    return resolve_streamlit_canary_config(
        _base() if base is None else base,
        host_env_present=host,
        query_enabled_value=enabled,
        query_percent_value=percent,
    )


def test_default_off_when_no_host_or_query_control():
    out = _resolve()
    assert out["enabled"] is False
    assert out["requested_percent"] == 0.0
    assert out["control_source"] == "DEFAULT_OFF"
    assert out["streamlit_session_control"] is False
    assert out["query_param_activation_requested"] is False


def test_query_can_arm_25_percent_session_canary():
    out = _resolve(enabled="1", percent="25")
    assert out["enabled"] is True
    assert out["requested_percent"] == 25.0
    assert out["config_valid"] is True
    assert out["control_source"] == "STREAMLIT_QUERY_SESSION"
    assert out["streamlit_session_control"] is True
    assert out["query_param_activation_requested"] is True


@pytest.mark.parametrize("truthy", ["1", "true", "TRUE", "yes", "YES", "on", "enabled"])
def test_supported_truthy_query_values_arm_canary(truthy):
    out = _resolve(enabled=truthy, percent="10")
    assert out["enabled"] is True
    assert out["query_param_activation_requested"] is True


@pytest.mark.parametrize("falsey", ["0", "false", "no", "off", "disabled", "", None])
def test_falsey_or_missing_enable_never_arms_canary(falsey):
    out = _resolve(enabled=falsey, percent="25")
    assert out["enabled"] is False
    assert out["query_param_activation_requested"] is False


def test_missing_percent_resolves_to_zero_even_when_enable_is_true():
    out = _resolve(enabled="1", percent=None)
    assert out["enabled"] is True
    assert out["requested_percent"] == 0.0
    cohort = select_canary_game_ids(range(824900, 824912), enabled=out["enabled"], requested_percent=out["requested_percent"])
    assert cohort["selected_game_ids"] == []


def test_invalid_percent_fails_closed():
    out = _resolve(enabled="1", percent="not-a-number")
    assert out["enabled"] is False
    assert out["requested_percent"] == 0.0
    assert out["config_valid"] is False
    assert out["query_param_activation_requested"] is False


def test_query_above_25_is_still_capped_by_frozen_step510_core():
    out = _resolve(enabled="1", percent="100")
    assert out["requested_percent"] == 100.0
    cohort = select_canary_game_ids(range(824900, 824912), enabled=out["enabled"], requested_percent=out["requested_percent"])
    assert cohort["effective_percent"] == MAX_CANARY_PERCENT
    assert cohort["selected_game_count"] == 3


def test_negative_query_percent_rolls_to_zero_through_frozen_step510_core():
    out = _resolve(enabled="1", percent="-5")
    cohort = select_canary_game_ids(range(824900, 824912), enabled=out["enabled"], requested_percent=out["requested_percent"])
    assert cohort["effective_percent"] == 0.0
    assert cohort["selected_game_ids"] == []


def test_explicit_host_environment_always_has_precedence_over_query():
    base = _base(enabled=False, percent=0.0)
    out = _resolve(base=base, host=True, enabled="1", percent="25")
    assert out["enabled"] is False
    assert out["requested_percent"] == 0.0
    assert out["control_source"] == "HOST_ENV"
    assert out["streamlit_session_control"] is False
    assert out["query_param_activation_requested"] is False


def test_explicit_host_enabled_configuration_is_preserved_exactly():
    base = _base(enabled=True, percent=17.5)
    out = _resolve(base=base, host=True, enabled="0", percent="0")
    assert out["enabled"] is True
    assert out["requested_percent"] == 17.5
    assert out["control_source"] == "HOST_ENV"


def test_query_control_does_not_mutate_input_config():
    base = _base()
    before = copy.deepcopy(base)
    _resolve(base=base, enabled="1", percent="25")
    assert base == before


def test_exact_query_rollback_flag_is_always_explicit():
    for out in (
        _resolve(),
        _resolve(enabled="1", percent="25"),
        _resolve(host=True, enabled="1", percent="25"),
    ):
        assert out["exact_query_rollback"] is True


def test_query_key_names_are_stable_and_nonsecret():
    out = _resolve(enabled="1", percent="25")
    assert out["query_enabled_key"] == QUERY_ENABLED_KEY == "mlb_step5_10b_canary"
    assert out["query_percent_key"] == QUERY_PERCENT_KEY == "mlb_step5_10b_percent"


def test_removing_query_returns_exact_underlying_default_config_values():
    base = _base(enabled=False, percent=0.0, valid=True)
    armed = _resolve(base=base, enabled="1", percent="25")
    rolled_back = _resolve(base=base)
    assert armed["enabled"] is True
    assert rolled_back["enabled"] == base["enabled"]
    assert rolled_back["requested_percent"] == base["requested_percent"]
    assert rolled_back["config_valid"] == base["config_valid"]
    assert rolled_back["control_source"] == "DEFAULT_OFF"


def test_query_disabled_with_percent_is_valid_but_not_armed():
    out = _resolve(enabled="0", percent="25")
    assert out["config_valid"] is True
    assert out["enabled"] is False
    assert out["requested_percent"] == 25.0
    assert out["query_param_activation_requested"] is False


def test_decimal_percent_is_preserved_for_step510_bounding():
    out = _resolve(enabled="true", percent="12.5")
    assert out["requested_percent"] == 12.5
    cohort = select_canary_game_ids(range(824900, 824940), enabled=True, requested_percent=out["requested_percent"])
    assert cohort["effective_percent"] == 12.5
    assert cohort["realized_percent"] <= 12.5


def test_core_contract_metadata_is_explicit():
    out = _resolve(enabled="1", percent="25")
    assert out["step5_10b_data_type"] == DATA_TYPE
    assert out["step5_10b_schema_version"] == SCHEMA_VERSION
    assert out["session_only"] is True
    assert out["host_env_precedence"] is True
    assert out["step5_10_core_impact"] is False


def test_all_protected_impact_flags_remain_false():
    out = _resolve(enabled="1", percent="25")
    for key in (
        "model_math_impact",
        "pick_strength_impact",
        "ranking_math_impact",
        "risk_logic_impact",
        "wagering_impact",
        "durable_persistence",
        "wnba_impact",
    ):
        assert out[key] is False


def test_non_mapping_base_config_fails_closed():
    with pytest.raises(MLBStreamlitCanaryControlError):
        resolve_streamlit_canary_config([], host_env_present=False)


@pytest.mark.parametrize("bad", [0, 1, None, "false", "true"])
def test_host_env_presence_must_be_boolean(bad):
    with pytest.raises(MLBStreamlitCanaryControlError):
        resolve_streamlit_canary_config(_base(), host_env_present=bad)
