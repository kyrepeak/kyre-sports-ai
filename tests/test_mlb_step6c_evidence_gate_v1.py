from __future__ import annotations

import math

import pytest

from sports_api.mlb_step6c_evidence_gate_v1 import (
    CURRENT_CERTIFIED_PERCENT,
    DATA_TYPE,
    MAX_EXPANSION_FEED_AGE_SECONDS,
    MAX_EXPANSION_PERCENT,
    MIN_DISTINCT_SNAPSHOTS,
    MIN_REQUIRED_CYCLES,
    MLBStep6CEvidenceGateError,
    REQUIRED_MONITOR_DATA_TYPE,
    REQUIRED_MONITOR_SCHEMA_VERSION,
    SCHEMA_VERSION,
    evaluate_expansion_evidence,
)


def _green_report(**overrides):
    report = {
        "data_type": REQUIRED_MONITOR_DATA_TYPE,
        "schema_version": REQUIRED_MONITOR_SCHEMA_VERSION,
        "monitor_result": "GREEN",
        "cycle_count": 4,
        "distinct_snapshot_count": 4,
        "distinct_slate_count": 1,
        "max_feed_age_seconds": 3.63,
        "stale_cycle_count": 0,
        "total_enrolled_checks": 24,
        "total_allow_count": 8,
        "total_block_count": 16,
        "total_rollback_passthrough": 288,
        "same_slate_cohort_deterministic": True,
        "violations": [],
        "warnings": [],
        "read_only_monitor": True,
        "scheduled_monitor_safe": True,
        "model_math_impact": False,
        "pick_strength_impact": False,
        "ranking_math_impact": False,
        "risk_logic_impact": False,
        "wagering_impact": False,
        "durable_persistence": False,
        "wnba_impact": False,
    }
    report.update(overrides)
    return report


def test_constants_are_frozen():
    assert DATA_TYPE == "mlb_step6c_evidence_gate_v1"
    assert SCHEMA_VERSION == 1
    assert CURRENT_CERTIFIED_PERCENT == 10.0
    assert MAX_EXPANSION_PERCENT == 25.0
    assert MIN_REQUIRED_CYCLES == 4
    assert MIN_DISTINCT_SNAPSHOTS == 4
    assert MAX_EXPANSION_FEED_AGE_SECONDS == 60.0


def test_green_evidence_allows_25_percent():
    out = evaluate_expansion_evidence(_green_report(), requested_percent=25)
    assert out["decision"] == "EXPANSION_ALLOWED"
    assert out["evidence_green"] is True
    assert out["expansion_eligible"] is True
    assert out["permitted_percent"] == 25.0
    assert out["failures"] == []


def test_green_evidence_allows_intermediate_percent():
    out = evaluate_expansion_evidence(_green_report(), requested_percent=17.5)
    assert out["decision"] == "EXPANSION_ALLOWED"
    assert out["permitted_percent"] == 17.5


def test_request_above_25_is_bounded():
    out = evaluate_expansion_evidence(_green_report(), requested_percent=99)
    assert out["bounded_requested_percent"] == 25.0
    assert out["permitted_percent"] == 25.0
    assert out["percent_bounded"] is True


def test_request_at_10_does_not_require_expansion():
    out = evaluate_expansion_evidence({}, requested_percent=10)
    assert out["decision"] == "WITHIN_CURRENT_CERTIFIED_EXPOSURE"
    assert out["permitted_percent"] == 10.0
    assert out["expansion_eligible"] is False


def test_request_below_10_is_respected():
    out = evaluate_expansion_evidence({}, requested_percent=5)
    assert out["decision"] == "WITHIN_CURRENT_CERTIFIED_EXPOSURE"
    assert out["permitted_percent"] == 5.0


def test_missing_evidence_holds_at_10_for_expansion_request():
    out = evaluate_expansion_evidence(None, requested_percent=25)
    assert out["decision"] == "HOLD_AT_10_PERCENT"
    assert out["permitted_percent"] == 10.0
    assert out["evidence_green"] is False


@pytest.mark.parametrize(
    "key,value,expected",
    [
        ("data_type", "wrong", "MONITOR_DATA_TYPE_MISMATCH"),
        ("schema_version", 2, "MONITOR_SCHEMA_VERSION_MISMATCH"),
        ("monitor_result", "RED", "MONITOR_NOT_GREEN"),
        ("cycle_count", 3, "INSUFFICIENT_MONITOR_CYCLES"),
        ("distinct_snapshot_count", 3, "INSUFFICIENT_DISTINCT_SNAPSHOTS"),
        ("max_feed_age_seconds", 61, "FEED_TOO_OLD_FOR_EXPANSION"),
        ("stale_cycle_count", 1, "STALE_CYCLE_PRESENT"),
        ("same_slate_cohort_deterministic", False, "COHORT_NOT_DETERMINISTIC"),
        ("read_only_monitor", False, "MONITOR_NOT_READ_ONLY"),
        ("scheduled_monitor_safe", False, "SCHEDULED_MONITOR_NOT_SAFE"),
        ("total_enrolled_checks", 0, "NO_ENROLLED_LIVE_CHECKS"),
        ("total_rollback_passthrough", 0, "NO_ROLLBACK_EVIDENCE"),
    ],
)
def test_each_core_failure_holds_at_10(key, value, expected):
    report = _green_report(**{key: value})
    out = evaluate_expansion_evidence(report, requested_percent=25)
    assert expected in out["failures"]
    assert out["decision"] == "HOLD_AT_10_PERCENT"
    assert out["permitted_percent"] == 10.0


def test_monitor_violation_list_blocks_expansion():
    out = evaluate_expansion_evidence(_green_report(violations=["X"]), requested_percent=25)
    assert "MONITOR_VIOLATIONS_PRESENT" in out["failures"]


def test_monitor_warning_list_blocks_expansion():
    out = evaluate_expansion_evidence(_green_report(warnings=["AGE"]), requested_percent=25)
    assert "MONITOR_WARNINGS_PRESENT" in out["failures"]
    assert out["warnings"] == ["AGE"]


@pytest.mark.parametrize(
    "field",
    [
        "model_math_impact",
        "pick_strength_impact",
        "ranking_math_impact",
        "risk_logic_impact",
        "wagering_impact",
        "durable_persistence",
        "wnba_impact",
    ],
)
def test_each_protected_flag_must_remain_false(field):
    out = evaluate_expansion_evidence(_green_report(**{field: True}), requested_percent=25)
    assert f"PROTECTED_FLAG_DRIFT:{field}" in out["failures"]
    assert out["permitted_percent"] == 10.0


def test_enrolled_partition_must_balance():
    out = evaluate_expansion_evidence(
        _green_report(total_enrolled_checks=24, total_allow_count=7, total_block_count=16),
        requested_percent=25,
    )
    assert "ENROLLED_GATE_PARTITION_MISMATCH" in out["failures"]


def test_negative_gate_counts_fail_closed():
    out = evaluate_expansion_evidence(_green_report(total_allow_count=-1), requested_percent=25)
    assert "ENROLLED_GATE_PARTITION_MISMATCH" in out["failures"]


def test_bad_count_types_fail_closed():
    out = evaluate_expansion_evidence(_green_report(total_enrolled_checks="bad"), requested_percent=25)
    assert "NO_ENROLLED_LIVE_CHECKS" in out["failures"]


def test_nonfinite_feed_age_fails_closed():
    out = evaluate_expansion_evidence(_green_report(max_feed_age_seconds=math.inf), requested_percent=25)
    assert "INVALID_FEED_AGE" in out["failures"]


def test_negative_feed_age_fails_closed():
    out = evaluate_expansion_evidence(_green_report(max_feed_age_seconds=-1), requested_percent=25)
    assert "INVALID_FEED_AGE" in out["failures"]


def test_exact_feed_age_limit_is_allowed():
    out = evaluate_expansion_evidence(
        _green_report(max_feed_age_seconds=MAX_EXPANSION_FEED_AGE_SECONDS), requested_percent=25
    )
    assert out["decision"] == "EXPANSION_ALLOWED"


def test_default_request_is_25_percent():
    out = evaluate_expansion_evidence(_green_report())
    assert out["requested_percent"] == 25.0
    assert out["permitted_percent"] == 25.0


@pytest.mark.parametrize("value", [True, -1, float("nan"), float("inf"), "bad"])
def test_invalid_requested_percent_raises(value):
    with pytest.raises(MLBStep6CEvidenceGateError):
        evaluate_expansion_evidence(_green_report(), requested_percent=value)


def test_zero_percent_is_allowed_without_expansion():
    out = evaluate_expansion_evidence(_green_report(), requested_percent=0)
    assert out["permitted_percent"] == 0.0
    assert out["expansion_requested"] is False


def test_output_is_policy_only_and_requires_separate_activation():
    out = evaluate_expansion_evidence(_green_report(), requested_percent=25)
    assert out["automatic_runtime_mutation"] is False
    assert out["requires_separate_activation_step"] is True


def test_output_preserves_all_no_impact_guards():
    out = evaluate_expansion_evidence(_green_report(), requested_percent=25)
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
        assert out[field] is False


def test_multiple_failures_are_reported_not_hidden():
    report = _green_report(
        monitor_result="RED",
        cycle_count=1,
        distinct_snapshot_count=1,
        max_feed_age_seconds=100,
        stale_cycle_count=1,
        warnings=["X"],
    )
    out = evaluate_expansion_evidence(report, requested_percent=25)
    assert len(out["failures"]) >= 6
    assert out["permitted_percent"] == 10.0


def test_failure_list_is_deduplicated():
    report = _green_report(warnings=["X", "X"])
    out = evaluate_expansion_evidence(report, requested_percent=25)
    assert out["failures"].count("MONITOR_WARNINGS_PRESENT") == 1


def test_string_numeric_request_is_supported():
    out = evaluate_expansion_evidence(_green_report(), requested_percent="20")
    assert out["permitted_percent"] == 20.0


def test_string_numeric_monitor_counts_are_supported():
    report = _green_report(
        cycle_count="4",
        distinct_snapshot_count="4",
        stale_cycle_count="0",
        total_enrolled_checks="24",
        total_allow_count="8",
        total_block_count="16",
        total_rollback_passthrough="288",
    )
    out = evaluate_expansion_evidence(report, requested_percent=25)
    assert out["decision"] == "EXPANSION_ALLOWED"


def test_expansion_request_flag_is_true_only_above_10():
    assert evaluate_expansion_evidence(_green_report(), requested_percent=10)["expansion_requested"] is False
    assert evaluate_expansion_evidence(_green_report(), requested_percent=10.01)["expansion_requested"] is True
