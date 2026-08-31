from __future__ import annotations

from datetime import datetime, timedelta, timezone
import copy

import pytest

from sports_api.mlb_step6e_25pct_stability_monitor_v1 import (
    CYCLE_DATA_TYPE,
    DATA_TYPE,
    MAX_FEED_AGE_SECONDS,
    MAX_PRODUCTION_PERCENT,
    MIN_DISTINCT_SNAPSHOTS,
    MIN_STABILITY_CYCLES,
    SCHEMA_VERSION,
    TARGET_PRODUCTION_PERCENT,
    WARNING_FEED_AGE_SECONDS,
    MLBStep6EStabilityMonitorError,
    build_25pct_stability_cycle,
    evaluate_25pct_stability_window,
)

GAMES = [823663, 824314, 824911, 825001, 825002, 825003, 825004, 825005, 825006, 825007, 825008, 825009]
SELECTED = [824314, 824911, 823663]
BASE = datetime(2026, 8, 31, 17, 20, 0, tzinfo=timezone.utc)


def good_cycle(index: int = 0, *, collected_offset_seconds: int | None = None, **overrides):
    offset = index * 20 if collected_offset_seconds is None else collected_offset_seconds
    collected = BASE + timedelta(seconds=offset)
    observed = collected + timedelta(seconds=3)
    kwargs = dict(
        cycle_index=index,
        observed_at_utc=observed,
        collected_at_utc=collected,
        http_status=200,
        source="FanDuel",
        official_game_ids=GAMES,
        selected_game_ids=SELECTED,
        attached_count=12,
        derived_context_count=12,
        fallback_matching_used=False,
        total_checks=72,
        enrolled_checks=18,
        allow_count=7,
        block_count=11,
        nonenrolled_passthrough=54,
        rollback_passthrough=72,
        line_bearing_checks=48,
        rollout_enabled=True,
        rollout_percent=25.0,
        step6c_permission_valid=True,
        protected_impacts_clear=True,
    )
    kwargs.update(overrides)
    return build_25pct_stability_cycle(**kwargs)


def test_constants_are_bounded_and_longer_than_step6c_window():
    assert TARGET_PRODUCTION_PERCENT == 25.0
    assert MAX_PRODUCTION_PERCENT == 25.0
    assert MIN_STABILITY_CYCLES == 12
    assert MIN_DISTINCT_SNAPSHOTS == 8
    assert MAX_FEED_AGE_SECONDS == 60.0
    assert WARNING_FEED_AGE_SECONDS == 45.0


def test_good_cycle_contract_is_green():
    row = good_cycle()
    assert row["data_type"] == CYCLE_DATA_TYPE
    assert row["schema_version"] == SCHEMA_VERSION
    assert row["cycle_green"] is True
    assert row["selected_game_count"] == 3
    assert row["expected_selected_game_count"] == 3
    assert row["realized_percent"] == 25.0
    assert row["violations"] == []
    assert row["warnings"] == []


@pytest.mark.parametrize(
    "field,value,error_text",
    [
        ("official_game_ids", [True, 2], "boolean id"),
        ("official_game_ids", [0, 2], "non-positive id"),
        ("official_game_ids", ["x"], "invalid id"),
        ("selected_game_ids", [-1], "non-positive id"),
        ("cycle_index", True, "must be an integer"),
        ("cycle_index", -1, "must be non-negative"),
    ],
)
def test_invalid_inputs_raise(field, value, error_text):
    kwargs = dict(
        cycle_index=0,
        observed_at_utc=BASE + timedelta(seconds=3),
        collected_at_utc=BASE,
        http_status=200,
        source="FanDuel",
        official_game_ids=GAMES,
        selected_game_ids=SELECTED,
        attached_count=12,
        derived_context_count=12,
        fallback_matching_used=False,
        total_checks=72,
        enrolled_checks=18,
        allow_count=7,
        block_count=11,
        nonenrolled_passthrough=54,
        rollback_passthrough=72,
        line_bearing_checks=48,
        rollout_enabled=True,
        rollout_percent=25.0,
        step6c_permission_valid=True,
        protected_impacts_clear=True,
    )
    kwargs[field] = value
    with pytest.raises(MLBStep6EStabilityMonitorError, match=error_text):
        build_25pct_stability_cycle(**kwargs)


def test_selected_must_be_subset_of_official_slate():
    with pytest.raises(MLBStep6EStabilityMonitorError, match="subset"):
        good_cycle(selected_game_ids=[999999])


@pytest.mark.parametrize(
    "override,expected",
    [
        ({"http_status": 503}, "PRODUCTION_HTTP_NOT_200"),
        ({"source": "OtherBook"}, "PRODUCTION_SOURCE_NOT_FANDUEL"),
        ({"attached_count": 11}, "EXACT_ID_ATTACH_COUNT_MISMATCH"),
        ({"derived_context_count": 11}, "PROBABILITY_CONTEXT_COUNT_MISMATCH"),
        ({"fallback_matching_used": True}, "FALLBACK_MATCHING_USED"),
        ({"rollout_enabled": False}, "STEP6D_ROLLOUT_NOT_ENABLED"),
        ({"rollout_percent": 10.0}, "STEP6D_PERCENT_NOT_25"),
        ({"step6c_permission_valid": False}, "STEP6C_PERMISSION_NOT_VALID"),
        ({"selected_game_ids": SELECTED[:2]}, "EXPANDED_COHORT_SIZE_MISMATCH"),
        ({"total_checks": 71}, "LIVE_CHECK_COVERAGE_MISMATCH"),
        ({"enrolled_checks": 17}, "ENROLLED_CHECK_COVERAGE_MISMATCH"),
        ({"allow_count": 6}, "ENROLLED_GATE_PARTITION_MISMATCH"),
        ({"nonenrolled_passthrough": 53}, "PRODUCTION_PARTITION_MISMATCH"),
        ({"rollback_passthrough": 71}, "ROLLBACK_PASSTHROUGH_MISMATCH"),
        ({"line_bearing_checks": 47}, "LINE_BEARING_COVERAGE_MISMATCH"),
        ({"protected_impacts_clear": False}, "PROTECTED_IMPACT_DRIFT"),
    ],
)
def test_cycle_failures_are_explicit(override, expected):
    row = good_cycle(**override)
    assert expected in row["violations"]
    assert row["cycle_green"] is False


def test_feed_warning_is_not_green():
    row = good_cycle(
        observed_at_utc=BASE + timedelta(seconds=WARNING_FEED_AGE_SECONDS + 1),
        collected_at_utc=BASE,
    )
    assert row["violations"] == []
    assert row["warnings"] == ["FEED_AGE_APPROACHING_LIMIT"]
    assert row["cycle_green"] is False


def test_stale_feed_is_violation():
    row = good_cycle(
        observed_at_utc=BASE + timedelta(seconds=MAX_FEED_AGE_SECONDS + 1),
        collected_at_utc=BASE,
    )
    assert "FEED_STALE" in row["violations"]


def test_good_12_cycle_window_is_green_and_graduation_ready():
    rows = [good_cycle(i) for i in range(12)]
    report = evaluate_25pct_stability_window(rows)
    assert report["data_type"] == DATA_TYPE
    assert report["stability_result"] == "GREEN"
    assert report["graduation_evidence_ready"] is True
    assert report["cycle_count"] == 12
    assert report["distinct_snapshot_count"] == 12
    assert report["total_checks"] == 864
    assert report["total_enrolled_checks"] == 216
    assert report["total_allow_count"] == 84
    assert report["total_block_count"] == 132
    assert report["total_nonenrolled_passthrough"] == 648
    assert report["total_rollback_passthrough"] == 864
    assert report["total_line_bearing_checks"] == 576
    assert report["same_slate_cohort_deterministic"] is True
    assert report["requires_separate_graduation_step"] is True
    assert report["automatic_runtime_mutation"] is False


def test_window_fails_with_fewer_than_12_cycles():
    report = evaluate_25pct_stability_window([good_cycle(i) for i in range(11)])
    assert report["stability_result"] == "RED"
    assert "INSUFFICIENT_STABILITY_CYCLES" in report["violations"]


def test_window_fails_with_fewer_than_required_distinct_snapshots():
    rows = [good_cycle(i, collected_offset_seconds=(i % 7) * 20) for i in range(12)]
    report = evaluate_25pct_stability_window(rows)
    assert report["distinct_snapshot_count"] == 7
    assert "INSUFFICIENT_DISTINCT_SNAPSHOTS" in report["violations"]
    assert report["graduation_evidence_ready"] is False


def test_window_fails_on_same_slate_cohort_drift():
    rows = [good_cycle(i) for i in range(12)]
    drifted = copy.deepcopy(rows[5])
    drifted["selected_game_ids"] = [823663, 824314, 825001]
    rows[5] = drifted
    report = evaluate_25pct_stability_window(rows)
    assert report["stability_result"] == "RED"
    assert any("SAME_SLATE_COHORT_CHANGED" in item for item in report["violations"])
    assert report["same_slate_cohort_deterministic"] is False


def test_window_fails_closed_on_warning():
    rows = [good_cycle(i) for i in range(12)]
    rows[2]["warnings"] = ["FEED_AGE_APPROACHING_LIMIT"]
    rows[2]["cycle_green"] = False
    report = evaluate_25pct_stability_window(rows)
    assert report["stability_result"] == "RED"
    assert "STABILITY_WARNINGS_PRESENT" in report["violations"]


def test_window_fails_closed_on_cycle_violation():
    rows = [good_cycle(i) for i in range(12)]
    rows[4]["violations"] = ["ROLLBACK_PASSTHROUGH_MISMATCH"]
    report = evaluate_25pct_stability_window(rows)
    assert any("ROLLBACK_PASSTHROUGH_MISMATCH" in item for item in report["violations"])
    assert report["graduation_evidence_ready"] is False


def test_different_slates_may_have_different_deterministic_cohorts():
    rows = [good_cycle(i) for i in range(6)]
    games2 = [v + 100 for v in GAMES]
    selected2 = [games2[0], games2[1], games2[2]]
    for i in range(6, 12):
        rows.append(good_cycle(i, official_game_ids=games2, selected_game_ids=selected2))
    report = evaluate_25pct_stability_window(rows)
    assert report["stability_result"] == "GREEN"
    assert report["distinct_slate_count"] == 2
    assert report["same_slate_cohort_deterministic"] is True


@pytest.mark.parametrize("field", ["fallback_matching_used", "rollout_enabled", "step6c_permission_valid", "protected_impacts_clear"])
def test_boolean_fields_reject_non_boolean(field):
    with pytest.raises(MLBStep6EStabilityMonitorError, match="must be boolean"):
        good_cycle(**{field: "true"})


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1.0, True])
def test_rollout_percent_invalid_values_fail(value):
    if value is True:
        # bool converts numerically in Python; the contract still detects it as wrong percent.
        row = good_cycle(rollout_percent=value)
        assert "STEP6D_PERCENT_NOT_25" in row["violations"]
    else:
        with pytest.raises(MLBStep6EStabilityMonitorError, match="finite and non-negative"):
            good_cycle(rollout_percent=value)


def test_window_rejects_string_cycles():
    with pytest.raises(MLBStep6EStabilityMonitorError, match="sequence"):
        evaluate_25pct_stability_window("not-cycles")


@pytest.mark.parametrize("field,value", [("min_cycles", 0), ("min_distinct_snapshots", 0), ("min_cycles", -1), ("min_distinct_snapshots", -1)])
def test_window_minimums_must_be_positive(field, value):
    kwargs = {field: value}
    with pytest.raises(MLBStep6EStabilityMonitorError):
        evaluate_25pct_stability_window([good_cycle(i) for i in range(12)], **kwargs)


def test_protected_flags_are_false_on_cycle_and_window():
    cycle = good_cycle()
    report = evaluate_25pct_stability_window([good_cycle(i) for i in range(12)])
    for obj in (cycle, report):
        assert obj["model_math_impact"] is False
        assert obj["pick_strength_impact"] is False
        assert obj["ranking_math_impact"] is False
        assert obj["risk_logic_impact"] is False
        assert obj["wagering_impact"] is False
        assert obj["durable_persistence"] is False
        assert obj["player_props_price_gated"] is False
        assert obj["wnba_impact"] is False
