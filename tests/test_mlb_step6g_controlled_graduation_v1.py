from __future__ import annotations

import copy
import math

import pytest

from sports_api.mlb_step6g_controlled_graduation_v1 import (
    CERTIFIED_STEP6F_DECISION,
    DATA_TYPE,
    GRADUATED_PRODUCTION_PERCENT,
    MAX_GRADUATED_PRODUCTION_PERCENT,
    MLBStep6GControlledGraduationError,
    SCHEMA_VERSION,
    STEP6F_CERTIFICATION_MARKER,
    resolve_step6g_controlled_graduation,
    validate_step6f_permission,
)


def step6d_config(**overrides):
    base = {
        "data_type": "mlb_step6d_production_expansion_v1",
        "schema_version": 1,
        "enabled": True,
        "effective_percent": 25.0,
        "requested_percent": 25.0,
        "control_source": "REPOSITORY_PRODUCTION_DEFAULT",
        "config_valid": True,
        "exact_rollback": True,
    }
    base.update(overrides)
    return base


def test_certified_permission_is_green():
    valid, failures = validate_step6f_permission(CERTIFIED_STEP6F_DECISION)
    assert valid is True
    assert failures == []


def test_default_25_percent_rollout_graduates_without_exposure_change():
    result = resolve_step6g_controlled_graduation(step6d_config())
    assert result["data_type"] == DATA_TYPE
    assert result["schema_version"] == SCHEMA_VERSION
    assert result["graduation_status"] == "GRADUATED_PRODUCTION_ACTIVE"
    assert result["graduated_production_active"] is True
    assert result["canary_status_retired"] is True
    assert result["step6d_effective_percent"] == 25.0
    assert result["graduated_production_percent"] == GRADUATED_PRODUCTION_PERCENT == 25.0
    assert result["max_graduated_production_percent"] == MAX_GRADUATED_PRODUCTION_PERCENT == 25.0
    assert result["production_exposure_changed"] is False
    assert result["exposure_change_percent"] == 0.0
    assert result["exposure_increase_authorized"] is False
    assert result["step6d_rollout_reused"] is True
    assert result["exact_rollback_preserved"] is True
    assert result["failures"] == []
    assert result["step6f_certification_marker"] == STEP6F_CERTIFICATION_MARKER


def test_inputs_are_not_mutated():
    rollout = step6d_config()
    permission = copy.deepcopy(CERTIFIED_STEP6F_DECISION)
    before_rollout = copy.deepcopy(rollout)
    before_permission = copy.deepcopy(permission)
    resolve_step6g_controlled_graduation(rollout, permission=permission)
    assert rollout == before_rollout
    assert permission == before_permission


@pytest.mark.parametrize("bad", [None, 1, 1.2, "x", [], (), object()])
def test_bad_step6d_config_rejected(bad):
    with pytest.raises(MLBStep6GControlledGraduationError):
        resolve_step6g_controlled_graduation(bad)


@pytest.mark.parametrize("bad", [1, 1.2, "x", [], (), object()])
def test_bad_permission_rejected(bad):
    with pytest.raises(MLBStep6GControlledGraduationError):
        validate_step6f_permission(bad)


def test_missing_permission_holds_canary_status_at_25():
    result = resolve_step6g_controlled_graduation(step6d_config(), permission={})
    assert result["graduation_status"] == "CANARY_HOLD_AT_25_PERCENT"
    assert result["graduated_production_active"] is False
    assert result["canary_status_retired"] is False
    assert result["step6d_effective_percent"] == 25.0
    assert result["production_exposure_changed"] is False
    assert result["failures"]


@pytest.mark.parametrize(
    "field,value,expected",
    [
        ("data_type", "wrong", "STEP6F_DATA_TYPE_MISMATCH"),
        ("schema_version", 2, "STEP6F_SCHEMA_VERSION_MISMATCH"),
        ("decision", "HOLD_AT_25_PERCENT", "STEP6F_DECISION_NOT_ALLOWED"),
        ("graduation_eligible", False, "STEP6F_GRADUATION_NOT_ELIGIBLE"),
        ("current_production_percent", 24.0, "STEP6F_CURRENT_PRODUCTION_PERCENT_NOT_25"),
        ("permitted_graduated_percent", 26.0, "STEP6F_PERMITTED_GRADUATED_PERCENT_NOT_25"),
        ("exposure_increase_authorized", True, "STEP6F_EXPOSURE_INCREASE_CONTRACT_DRIFT"),
        ("automatic_runtime_mutation", True, "STEP6F_RUNTIME_MUTATION_CONTRACT_DRIFT"),
        ("requires_separate_activation_step", False, "STEP6F_SEPARATE_ACTIVATION_CONTRACT_DRIFT"),
    ],
)
def test_permission_drift_holds_graduation(field, value, expected):
    permission = copy.deepcopy(CERTIFIED_STEP6F_DECISION)
    permission[field] = value
    valid, failures = validate_step6f_permission(permission)
    assert valid is False
    assert expected in failures
    result = resolve_step6g_controlled_graduation(step6d_config(), permission=permission)
    assert result["graduated_production_active"] is False
    assert result["canary_status_retired"] is False
    assert result["step6d_effective_percent"] == 25.0


def test_step6f_failures_hold_graduation():
    permission = copy.deepcopy(CERTIFIED_STEP6F_DECISION)
    permission["failures"] = ["FORCED"]
    result = resolve_step6g_controlled_graduation(step6d_config(), permission=permission)
    assert result["graduated_production_active"] is False
    assert "STEP6F_FAILURES_PRESENT" in result["failures"]


@pytest.mark.parametrize("field", ["current_production_percent", "permitted_graduated_percent"])
@pytest.mark.parametrize("value", ["x", None, math.nan, math.inf, -math.inf, True])
def test_invalid_permission_percent_fails_closed(field, value):
    permission = copy.deepcopy(CERTIFIED_STEP6F_DECISION)
    permission[field] = value
    valid, failures = validate_step6f_permission(permission)
    assert valid is False
    assert failures


@pytest.mark.parametrize(
    "field,value,expected",
    [
        ("data_type", "wrong", "STEP6D_DATA_TYPE_MISMATCH"),
        ("schema_version", 2, "STEP6D_SCHEMA_VERSION_MISMATCH"),
        ("exact_rollback", False, "STEP6D_EXACT_ROLLBACK_CONTRACT_DRIFT"),
        ("config_valid", False, "STEP6D_CONFIG_NOT_VALID"),
    ],
)
def test_step6d_contract_drift_prevents_graduation(field, value, expected):
    result = resolve_step6g_controlled_graduation(step6d_config(**{field: value}))
    assert result["graduated_production_active"] is False
    assert expected in result["failures"]


def test_step6d_above_25_is_never_graduated():
    result = resolve_step6g_controlled_graduation(step6d_config(effective_percent=25.01))
    assert result["graduated_production_active"] is False
    assert "STEP6D_EFFECTIVE_PERCENT_EXCEEDS_25" in result["failures"]
    assert result["exposure_increase_authorized"] is False


@pytest.mark.parametrize("value", ["x", math.nan, math.inf, -math.inf, True])
def test_invalid_step6d_percent_fails_closed(value):
    result = resolve_step6g_controlled_graduation(step6d_config(effective_percent=value))
    assert result["graduated_production_active"] is False
    assert "STEP6D_EFFECTIVE_PERCENT_INVALID" in result["failures"]


def test_10_percent_is_not_labeled_graduated():
    result = resolve_step6g_controlled_graduation(step6d_config(effective_percent=10.0))
    assert result["graduation_status"] == "CANARY_HOLD_AT_25_PERCENT"
    assert result["graduated_production_active"] is False
    assert "STEP6D_NOT_AT_GRADUATED_25_PERCENT" not in result["failures"]


def test_global_kill_switch_status_preserves_zero_percent_rollback():
    result = resolve_step6g_controlled_graduation(
        step6d_config(
            enabled=False,
            effective_percent=0.0,
            requested_percent=0.0,
            control_source="GLOBAL_KILL_SWITCH",
        )
    )
    assert result["graduation_status"] == "GRADUATED_PRODUCTION_ROLLBACK"
    assert result["graduated_production_active"] is False
    assert result["step6d_effective_percent"] == 0.0
    assert result["exact_rollback_preserved"] is True


def test_streamlit_session_rollback_status_preserves_zero_percent():
    result = resolve_step6g_controlled_graduation(
        step6d_config(
            enabled=False,
            effective_percent=0.0,
            requested_percent=0.0,
            control_source="STREAMLIT_SESSION_ROLLBACK",
        )
    )
    assert result["graduation_status"] == "GRADUATED_PRODUCTION_ROLLBACK"
    assert result["graduated_production_active"] is False
    assert result["canary_status_retired"] is False
    assert result["step6d_effective_percent"] == 0.0


def test_disabled_nonrollback_config_is_not_graduated():
    result = resolve_step6g_controlled_graduation(
        step6d_config(enabled=False, effective_percent=0.0, control_source="HOST_ENV")
    )
    assert result["graduated_production_active"] is False
    assert result["graduation_status"] == "GRADUATED_PRODUCTION_ROLLBACK"


def test_graduation_never_changes_exposure():
    for effective in (0.0, 10.0, 25.0):
        result = resolve_step6g_controlled_graduation(
            step6d_config(enabled=effective > 0.0, effective_percent=effective)
        )
        assert result["production_exposure_changed"] is False
        assert result["exposure_change_percent"] == 0.0
        assert result["exposure_increase_authorized"] is False
        assert result["max_graduated_production_percent"] <= 25.0
