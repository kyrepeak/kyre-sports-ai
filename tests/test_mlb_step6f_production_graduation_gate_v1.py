from __future__ import annotations

import copy
import math

import pytest

from sports_api.mlb_step6f_production_graduation_gate_v1 import (
    CURRENT_PRODUCTION_PERCENT,
    DATA_TYPE,
    MAX_GRADUATED_PERCENT,
    MLBStep6FGraduationGateError,
    SCHEMA_VERSION,
    STEP6E_CERTIFICATION_MARKER,
    evaluate_production_graduation,
)


def green_report() -> dict:
    return {
        "data_type": "mlb_step6e_25pct_stability_window_v1",
        "schema_version": 1,
        "stability_result": "GREEN",
        "graduation_evidence_ready": True,
        "cycle_count": 12,
        "minimum_cycle_count": 12,
        "distinct_snapshot_count": 12,
        "minimum_distinct_snapshot_count": 8,
        "distinct_slate_count": 1,
        "max_feed_age_seconds": 4.01,
        "stale_cycle_count": 0,
        "total_checks": 864,
        "total_enrolled_checks": 216,
        "total_allow_count": 84,
        "total_block_count": 132,
        "total_nonenrolled_passthrough": 648,
        "total_rollback_passthrough": 864,
        "total_line_bearing_checks": 576,
        "same_slate_cohort_deterministic": True,
        "target_production_percent": 25.0,
        "max_production_percent": 25.0,
        "violations": [],
        "warnings": [],
        "read_only_monitor": True,
        "automatic_runtime_mutation": False,
        "requires_separate_graduation_step": True,
        "scheduled_monitor_safe": True,
        "model_math_impact": False,
        "pick_strength_impact": False,
        "ranking_math_impact": False,
        "risk_logic_impact": False,
        "wagering_impact": False,
        "durable_persistence": False,
        "player_props_price_gated": False,
        "wnba_impact": False,
    }


def test_green_evidence_allows_graduation_without_exposure_increase():
    result = evaluate_production_graduation(green_report())
    assert result["data_type"] == DATA_TYPE
    assert result["schema_version"] == SCHEMA_VERSION
    assert result["decision"] == "GRADUATION_ALLOWED"
    assert result["graduation_eligible"] is True
    assert result["current_production_percent"] == CURRENT_PRODUCTION_PERCENT == 25.0
    assert result["permitted_graduated_percent"] == MAX_GRADUATED_PERCENT == 25.0
    assert result["exposure_increase_authorized"] is False
    assert result["automatic_runtime_mutation"] is False
    assert result["requires_separate_activation_step"] is True
    assert result["failures"] == []
    assert result["step6e_certification_marker"] == STEP6E_CERTIFICATION_MARKER


def test_input_is_not_mutated():
    report = green_report()
    before = copy.deepcopy(report)
    evaluate_production_graduation(report)
    assert report == before


def test_none_fails_closed():
    result = evaluate_production_graduation(None)
    assert result["decision"] == "HOLD_AT_25_PERCENT"
    assert result["graduation_eligible"] is False
    assert result["exposure_increase_authorized"] is False
    assert result["failures"]


@pytest.mark.parametrize("bad", [1, 1.2, "x", [], (), object()])
def test_non_mapping_report_rejected(bad):
    with pytest.raises(MLBStep6FGraduationGateError):
        evaluate_production_graduation(bad)


@pytest.mark.parametrize(
    "field,value,expected",
    [
        ("data_type", "wrong", "STEP6E_DATA_TYPE_MISMATCH"),
        ("schema_version", 2, "STEP6E_SCHEMA_VERSION_MISMATCH"),
        ("stability_result", "RED", "STEP6E_STABILITY_NOT_GREEN"),
        ("graduation_evidence_ready", False, "STEP6E_GRADUATION_EVIDENCE_NOT_READY"),
        ("cycle_count", 11, "STEP6E_INSUFFICIENT_CYCLES"),
        ("distinct_snapshot_count", 7, "STEP6E_INSUFFICIENT_DISTINCT_SNAPSHOTS"),
        ("max_feed_age_seconds", 60.01, "STEP6E_FEED_TOO_OLD"),
        ("stale_cycle_count", 1, "STEP6E_STALE_CYCLES_PRESENT"),
        ("same_slate_cohort_deterministic", False, "STEP6E_COHORT_NOT_DETERMINISTIC"),
        ("target_production_percent", 24.9, "STEP6E_TARGET_PERCENT_NOT_25"),
        ("max_production_percent", 26.0, "STEP6E_MAX_PERCENT_NOT_25"),
        ("read_only_monitor", False, "STEP6E_MONITOR_NOT_READ_ONLY"),
        ("automatic_runtime_mutation", True, "STEP6E_RUNTIME_MUTATION_CONTRACT_DRIFT"),
        ("requires_separate_graduation_step", False, "STEP6E_SEPARATE_GRADUATION_CONTRACT_DRIFT"),
        ("scheduled_monitor_safe", False, "STEP6E_SCHEDULED_MONITOR_NOT_SAFE"),
    ],
)
def test_bad_evidence_holds_at_25(field, value, expected):
    report = green_report()
    report[field] = value
    result = evaluate_production_graduation(report)
    assert result["decision"] == "HOLD_AT_25_PERCENT"
    assert result["graduation_eligible"] is False
    assert expected in result["failures"]
    assert result["current_production_percent"] == 25.0
    assert result["exposure_increase_authorized"] is False


def test_violations_fail_graduation():
    report = green_report()
    report["violations"] = ["X"]
    result = evaluate_production_graduation(report)
    assert "STEP6E_VIOLATIONS_PRESENT" in result["failures"]


def test_warnings_fail_graduation():
    report = green_report()
    report["warnings"] = ["X"]
    result = evaluate_production_graduation(report)
    assert "STEP6E_WARNINGS_PRESENT" in result["failures"]


@pytest.mark.parametrize(
    "field",
    [
        "model_math_impact",
        "pick_strength_impact",
        "ranking_math_impact",
        "risk_logic_impact",
        "wagering_impact",
        "durable_persistence",
        "player_props_price_gated",
        "wnba_impact",
    ],
)
def test_protected_flag_drift_fails(field):
    report = green_report()
    report[field] = True
    result = evaluate_production_graduation(report)
    assert f"STEP6E_PROTECTED_FLAG_DRIFT:{field}" in result["failures"]


@pytest.mark.parametrize(
    "field,value,expected",
    [
        ("total_checks", 0, "STEP6E_NO_LIVE_CHECKS"),
        ("total_enrolled_checks", 0, "STEP6E_NO_ENROLLED_CHECKS"),
        ("total_allow_count", 85, "STEP6E_GATE_PARTITION_MISMATCH"),
        ("total_block_count", 133, "STEP6E_GATE_PARTITION_MISMATCH"),
        ("total_nonenrolled_passthrough", 647, "STEP6E_PRODUCTION_PARTITION_MISMATCH"),
        ("total_rollback_passthrough", 863, "STEP6E_ROLLBACK_NOT_EXACT"),
        ("total_line_bearing_checks", 0, "STEP6E_NO_LINE_BEARING_CHECKS"),
    ],
)
def test_count_partition_failures(field, value, expected):
    report = green_report()
    report[field] = value
    result = evaluate_production_graduation(report)
    assert expected in result["failures"]


@pytest.mark.parametrize(
    "field,value,expected_prefix",
    [
        ("cycle_count", "x", "STEP6E_CYCLE_COUNT_INVALID"),
        ("distinct_snapshot_count", "x", "STEP6E_DISTINCT_SNAPSHOT_COUNT_INVALID"),
        ("max_feed_age_seconds", "x", "STEP6E_FEED_AGE_INVALID"),
        ("stale_cycle_count", "x", "STEP6E_STALE_CYCLE_COUNT_INVALID"),
        ("target_production_percent", "x", "STEP6E_TARGET_PERCENT_INVALID"),
        ("max_production_percent", "x", "STEP6E_MAX_PERCENT_INVALID"),
        ("total_checks", "x", "STEP6E_TOTAL_CHECKS_INVALID"),
    ],
)
def test_invalid_numeric_fields_fail_closed(field, value, expected_prefix):
    report = green_report()
    report[field] = value
    result = evaluate_production_graduation(report)
    assert expected_prefix in result["failures"]
    assert result["graduation_eligible"] is False


def test_exact_limits_are_allowed():
    report = green_report()
    report["cycle_count"] = 12
    report["distinct_snapshot_count"] = 8
    report["max_feed_age_seconds"] = 60.0
    result = evaluate_production_graduation(report)
    assert result["decision"] == "GRADUATION_ALLOWED"


def test_nan_feed_age_fails_closed():
    report = green_report()
    report["max_feed_age_seconds"] = math.nan
    result = evaluate_production_graduation(report)
    assert "STEP6E_FEED_AGE_INVALID" in result["failures"]


def test_graduation_gate_never_authorizes_more_than_25():
    result = evaluate_production_graduation(green_report())
    assert result["permitted_graduated_percent"] <= 25.0
    assert result["exposure_increase_authorized"] is False


def test_protected_output_flags_are_false():
    result = evaluate_production_graduation(green_report())
    for field in (
        "model_math_impact",
        "pick_strength_impact",
        "ranking_math_impact",
        "risk_logic_impact",
        "wagering_impact",
        "durable_persistence",
        "player_props_price_gated",
        "wnba_impact",
    ):
        assert result[field] is False
