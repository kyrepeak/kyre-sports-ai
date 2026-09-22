from __future__ import annotations

import copy

import pytest

from sports_api.mlb_step6d_production_expansion_v1 import (
    CERTIFIED_STEP6C_PERMISSION,
    CURRENT_CERTIFIED_BASELINE_PERCENT,
    DATA_TYPE,
    DEFAULT_ENABLED,
    DEFAULT_PERCENT,
    ENABLED_ENV_KEY,
    KILL_SWITCH_ENV_KEY,
    MAX_PRODUCTION_CANARY_PERCENT,
    PERCENT_ENV_KEY,
    ROLLBACK_QUERY_KEY,
    SCHEMA_VERSION,
    STEP6C_CERTIFICATION_MARKER,
    STEP6C_CERTIFICATION_RUN_ID,
    STEP6C_CERTIFIED_MAIN_SHA,
    resolve_step6d_production_expansion,
    validate_step6c_permission,
)


def _good_permission():
    return copy.deepcopy(CERTIFIED_STEP6C_PERMISSION)


def test_step6d_constants_are_frozen():
    assert DATA_TYPE == "mlb_step6d_production_expansion_v1"
    assert SCHEMA_VERSION == 1
    assert CURRENT_CERTIFIED_BASELINE_PERCENT == 10.0
    assert DEFAULT_ENABLED is True
    assert DEFAULT_PERCENT == 25.0
    assert MAX_PRODUCTION_CANARY_PERCENT == 25.0
    assert ROLLBACK_QUERY_KEY == "mlb_step6d_rollback"


def test_step6c_release_attestation_is_pinned():
    assert STEP6C_CERTIFIED_MAIN_SHA == "b75fe13a25c15808c613d7ab2679d7bb0a829255"
    assert STEP6C_CERTIFICATION_RUN_ID == 33416917835
    assert STEP6C_CERTIFICATION_MARKER == "MLB_STEP6C_EVIDENCE_GATED_EXPANSION_GREEN"


def test_certified_permission_validates():
    valid, failures = validate_step6c_permission(_good_permission())
    assert valid is True
    assert failures == []


def test_repository_default_activates_25_percent():
    out = resolve_step6d_production_expansion({})
    assert out["enabled"] is True
    assert out["effective_percent"] == 25.0
    assert out["control_source"] == "REPOSITORY_PRODUCTION_DEFAULT"
    assert out["step6c_permission_valid"] is True


def test_default_permission_source_is_certified_release_attestation():
    out = resolve_step6d_production_expansion({})
    assert out["step6c_permission_source"] == "CERTIFIED_RELEASE_ATTESTATION"


def test_explicit_permission_source_is_runtime_permission():
    out = resolve_step6d_production_expansion({}, permission=_good_permission())
    assert out["step6c_permission_source"] == "EXTERNAL_RUNTIME_PERMISSION"


def test_global_kill_switch_has_highest_precedence():
    out = resolve_step6d_production_expansion({KILL_SWITCH_ENV_KEY: "1", PERCENT_ENV_KEY: "25"}, rollback_requested=True)
    assert out["enabled"] is False
    assert out["effective_percent"] == 0.0
    assert out["control_source"] == "GLOBAL_KILL_SWITCH"
    assert out["exact_rollback"] is True


def test_session_rollback_returns_exact_zero_percent():
    out = resolve_step6d_production_expansion({}, rollback_requested=True)
    assert out["enabled"] is False
    assert out["effective_percent"] == 0.0
    assert out["control_source"] == "STREAMLIT_SESSION_ROLLBACK"


def test_invalid_permission_holds_at_certified_10_percent():
    bad = _good_permission()
    bad["decision"] = "HOLD_AT_10_PERCENT"
    out = resolve_step6d_production_expansion({}, permission=bad)
    assert out["enabled"] is True
    assert out["effective_percent"] == 10.0
    assert out["control_source"] == "STEP6C_PERMISSION_HOLD"
    assert out["config_valid"] is False


def test_host_can_explicitly_disable():
    out = resolve_step6d_production_expansion({ENABLED_ENV_KEY: "0"})
    assert out["enabled"] is False
    assert out["effective_percent"] == 0.0
    assert out["control_source"] == "HOST_ENV"


def test_host_can_hold_at_10_percent():
    out = resolve_step6d_production_expansion({PERCENT_ENV_KEY: "10"})
    assert out["enabled"] is True
    assert out["effective_percent"] == 10.0


def test_host_can_request_25_percent():
    out = resolve_step6d_production_expansion({PERCENT_ENV_KEY: "25"})
    assert out["enabled"] is True
    assert out["effective_percent"] == 25.0


def test_host_request_above_25_is_bounded():
    out = resolve_step6d_production_expansion({PERCENT_ENV_KEY: "99"})
    assert out["effective_percent"] == 25.0
    assert out["percent_bounded"] is True


def test_negative_host_percent_fails_closed_to_off():
    out = resolve_step6d_production_expansion({PERCENT_ENV_KEY: "-1"})
    assert out["enabled"] is False
    assert out["effective_percent"] == 0.0
    assert out["config_valid"] is False


def test_non_numeric_host_percent_fails_closed_to_off():
    out = resolve_step6d_production_expansion({PERCENT_ENV_KEY: "nope"})
    assert out["enabled"] is False
    assert out["effective_percent"] == 0.0
    assert out["config_valid"] is False


def test_boolean_like_string_values_supported_for_enable():
    for value in ("1", "true", "yes", "on", "enabled"):
        out = resolve_step6d_production_expansion({ENABLED_ENV_KEY: value})
        assert out["enabled"] is True
    for value in ("0", "false", "no", "off", "disabled"):
        out = resolve_step6d_production_expansion({ENABLED_ENV_KEY: value})
        assert out["enabled"] is False


def test_invalid_enabled_value_fails_closed():
    out = resolve_step6d_production_expansion({ENABLED_ENV_KEY: "maybe"})
    assert out["enabled"] is False
    assert out["config_valid"] is False


def test_zero_percent_disables_even_if_enabled_true():
    out = resolve_step6d_production_expansion({ENABLED_ENV_KEY: "1", PERCENT_ENV_KEY: "0"})
    assert out["enabled"] is False
    assert out["effective_percent"] == 0.0


def test_host_control_presence_is_reported():
    assert resolve_step6d_production_expansion({})["host_control_present"] is False
    assert resolve_step6d_production_expansion({PERCENT_ENV_KEY: "25"})["host_control_present"] is True


def test_permission_wrong_data_type_is_rejected():
    bad = _good_permission(); bad["data_type"] = "wrong"
    valid, failures = validate_step6c_permission(bad)
    assert valid is False
    assert "STEP6C_DATA_TYPE_MISMATCH" in failures


def test_permission_wrong_schema_is_rejected():
    bad = _good_permission(); bad["schema_version"] = 2
    valid, failures = validate_step6c_permission(bad)
    assert valid is False
    assert "STEP6C_SCHEMA_VERSION_MISMATCH" in failures


def test_permission_non_green_is_rejected():
    bad = _good_permission(); bad["evidence_green"] = False
    valid, failures = validate_step6c_permission(bad)
    assert valid is False
    assert "STEP6C_EVIDENCE_NOT_GREEN" in failures


def test_permission_not_eligible_is_rejected():
    bad = _good_permission(); bad["expansion_eligible"] = False
    valid, failures = validate_step6c_permission(bad)
    assert valid is False
    assert "STEP6C_EXPANSION_NOT_ELIGIBLE" in failures


def test_permission_below_25_is_rejected():
    bad = _good_permission(); bad["permitted_percent"] = 20
    valid, failures = validate_step6c_permission(bad)
    assert valid is False
    assert "STEP6C_PERMISSION_BELOW_25" in failures


def test_permission_failures_are_rejected():
    bad = _good_permission(); bad["failures"] = ["X"]
    valid, failures = validate_step6c_permission(bad)
    assert valid is False
    assert "STEP6C_FAILURES_PRESENT" in failures


def test_permission_warnings_are_rejected():
    bad = _good_permission(); bad["warnings"] = ["X"]
    valid, failures = validate_step6c_permission(bad)
    assert valid is False
    assert "STEP6C_WARNINGS_PRESENT" in failures


def test_permission_must_require_separate_activation():
    bad = _good_permission(); bad["requires_separate_activation_step"] = False
    valid, failures = validate_step6c_permission(bad)
    assert valid is False
    assert "STEP6C_SEPARATE_ACTIVATION_CONTRACT_DRIFT" in failures


def test_permission_must_not_have_automatic_runtime_mutation():
    bad = _good_permission(); bad["automatic_runtime_mutation"] = True
    valid, failures = validate_step6c_permission(bad)
    assert valid is False
    assert "STEP6C_RUNTIME_MUTATION_CONTRACT_DRIFT" in failures


@pytest.mark.parametrize("field", [
    "model_math_impact",
    "pick_strength_impact",
    "ranking_math_impact",
    "risk_logic_impact",
    "wagering_impact",
    "durable_persistence",
    "player_props_price_gated",
    "wnba_impact",
])
def test_permission_protected_flags_must_remain_false(field):
    bad = _good_permission(); bad[field] = True
    valid, failures = validate_step6c_permission(bad)
    assert valid is False
    assert f"STEP6C_PROTECTED_FLAG_DRIFT:{field}" in failures


def test_missing_permission_mapping_holds_at_10_when_explicitly_supplied():
    out = resolve_step6d_production_expansion({}, permission={})
    assert out["effective_percent"] == 10.0
    assert out["control_source"] == "STEP6C_PERMISSION_HOLD"


def test_kill_switch_still_wins_with_invalid_permission():
    out = resolve_step6d_production_expansion({KILL_SWITCH_ENV_KEY: "true"}, permission={})
    assert out["effective_percent"] == 0.0
    assert out["control_source"] == "GLOBAL_KILL_SWITCH"


def test_rollback_still_wins_with_invalid_permission():
    out = resolve_step6d_production_expansion({}, rollback_requested=True, permission={})
    assert out["effective_percent"] == 0.0
    assert out["control_source"] == "STREAMLIT_SESSION_ROLLBACK"


def test_all_activation_outputs_expose_no_impact_flags():
    scenarios = [
        resolve_step6d_production_expansion({}),
        resolve_step6d_production_expansion({KILL_SWITCH_ENV_KEY: "1"}),
        resolve_step6d_production_expansion({}, rollback_requested=True),
        resolve_step6d_production_expansion({}, permission={}),
    ]
    for out in scenarios:
        for key in (
            "model_math_impact", "pick_strength_impact", "ranking_math_impact",
            "risk_logic_impact", "wagering_impact", "durable_persistence",
            "player_props_price_gated", "wnba_impact",
        ):
            assert out[key] is False


def test_default_output_pins_step6c_certification_metadata():
    out = resolve_step6d_production_expansion({})
    assert out["step6c_certified_main_sha"] == STEP6C_CERTIFIED_MAIN_SHA
    assert out["step6c_certification_run_id"] == STEP6C_CERTIFICATION_RUN_ID
    assert out["step6c_certification_marker"] == STEP6C_CERTIFICATION_MARKER


def test_25_is_absolute_runtime_ceiling_across_many_host_requests():
    for requested in (25, 25.1, 30, 50, 100, 1000):
        out = resolve_step6d_production_expansion({PERCENT_ENV_KEY: str(requested)})
        assert out["effective_percent"] <= 25.0


def test_permission_failure_list_is_deduplicated():
    bad = _good_permission()
    bad["model_math_impact"] = True
    valid, failures = validate_step6c_permission(bad)
    assert valid is False
    assert len(failures) == len(set(failures))
