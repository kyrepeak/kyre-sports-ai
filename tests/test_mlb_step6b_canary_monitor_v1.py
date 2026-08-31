from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from sports_api.mlb_step6b_canary_monitor_v1 import (
    DATA_TYPE,
    MAX_CANARY_PERCENT,
    MAX_FEED_AGE_SECONDS,
    MIN_MONITOR_CYCLES,
    MLBStep6BCanaryMonitorError,
    SCHEMA_VERSION,
    TARGET_CANARY_PERCENT,
    build_canary_cycle_observation,
    evaluate_canary_monitor_window,
)


BASE_TIME = datetime(2026, 8, 31, 16, 40, tzinfo=timezone.utc)
GAME_IDS = tuple(range(824900, 824912))
SELECTED = (824903,)


def _cycle(index=0, **overrides):
    args = {
        "cycle_index": index,
        "observed_at_utc": BASE_TIME + timedelta(seconds=index * 20),
        "collected_at_utc": BASE_TIME + timedelta(seconds=index * 20 - 2),
        "http_status": 200,
        "source": "FanDuel",
        "official_game_ids": GAME_IDS,
        "selected_game_ids": SELECTED,
        "attached_count": 12,
        "derived_context_count": 12,
        "fallback_matching_used": False,
        "total_checks": 72,
        "enrolled_checks": 6,
        "allow_count": 2,
        "block_count": 4,
        "nonenrolled_passthrough": 66,
        "rollback_passthrough": 72,
        "line_bearing_checks": 48,
        "rollout_enabled": True,
        "rollout_percent": 10.0,
        "protected_impacts_clear": True,
    }
    args.update(overrides)
    return build_canary_cycle_observation(**args)


def _window(count=4):
    return [_cycle(i) for i in range(count)]


def test_constants_are_frozen_for_step6b():
    assert DATA_TYPE == "mlb_step6b_canary_monitor_window_v1"
    assert SCHEMA_VERSION == 1
    assert TARGET_CANARY_PERCENT == 10.0
    assert MAX_CANARY_PERCENT == 10.0
    assert MIN_MONITOR_CYCLES == 4
    assert MAX_FEED_AGE_SECONDS == 300.0


def test_good_cycle_is_green():
    out = _cycle()
    assert out["cycle_green"] is True
    assert out["violations"] == []
    assert out["game_count"] == 12
    assert out["selected_game_count"] == 1
    assert out["realized_percent"] == pytest.approx(100 / 12)


def test_good_window_is_green():
    out = evaluate_canary_monitor_window(_window())
    assert out["monitor_result"] == "GREEN"
    assert out["cycle_count"] == 4
    assert out["same_slate_cohort_deterministic"] is True


def test_same_slate_cohort_change_is_red():
    rows = _window()
    rows[-1] = _cycle(3, selected_game_ids=(824904,))
    out = evaluate_canary_monitor_window(rows)
    assert out["monitor_result"] == "RED"
    assert any("SAME_SLATE_COHORT_CHANGED" in v for v in out["violations"])


def test_different_slate_can_have_different_cohort_without_drift():
    rows = _window(3)
    new_games = tuple(range(824920, 824932))
    rows.append(_cycle(3, official_game_ids=new_games, selected_game_ids=(824921,)))
    out = evaluate_canary_monitor_window(rows)
    assert out["monitor_result"] == "GREEN"
    assert out["distinct_slate_count"] == 2


def test_no_snapshot_advance_is_warning_not_failure():
    collected = BASE_TIME
    rows = [_cycle(i, collected_at_utc=collected) for i in range(4)]
    out = evaluate_canary_monitor_window(rows)
    assert out["monitor_result"] == "GREEN"
    assert "NO_SNAPSHOT_ADVANCE_OBSERVED_IN_WINDOW" in out["warnings"]


def test_insufficient_cycles_is_red():
    out = evaluate_canary_monitor_window(_window(3))
    assert out["monitor_result"] == "RED"
    assert "INSUFFICIENT_MONITOR_CYCLES" in out["violations"]


def test_custom_min_cycles_is_supported():
    out = evaluate_canary_monitor_window(_window(2), min_cycles=2)
    assert out["monitor_result"] == "GREEN"


def test_zero_min_cycles_is_rejected():
    with pytest.raises(MLBStep6BCanaryMonitorError):
        evaluate_canary_monitor_window([], min_cycles=0)


def test_selected_ids_must_be_subset_of_slate():
    with pytest.raises(MLBStep6BCanaryMonitorError):
        _cycle(selected_game_ids=(999999,))


def test_boolean_game_id_is_rejected():
    with pytest.raises(MLBStep6BCanaryMonitorError):
        _cycle(official_game_ids=[True, 824900])


def test_nonpositive_game_id_is_rejected():
    with pytest.raises(MLBStep6BCanaryMonitorError):
        _cycle(official_game_ids=[0, 824900])


def test_invalid_game_id_is_rejected():
    with pytest.raises(MLBStep6BCanaryMonitorError):
        _cycle(official_game_ids=["nope"])


def test_duplicate_game_ids_are_normalized():
    out = _cycle(official_game_ids=list(GAME_IDS) + [GAME_IDS[0]])
    assert out["game_count"] == 12


def test_http_failure_is_violation():
    out = _cycle(http_status=503)
    assert "PRODUCTION_HTTP_NOT_200" in out["violations"]


def test_wrong_source_is_violation():
    out = _cycle(source="OtherBook")
    assert "PRODUCTION_SOURCE_NOT_FANDUEL" in out["violations"]


def test_empty_slate_is_violation():
    out = _cycle(
        official_game_ids=[], selected_game_ids=[], attached_count=0, derived_context_count=0,
        total_checks=0, enrolled_checks=0, allow_count=0, block_count=0,
        nonenrolled_passthrough=0, rollback_passthrough=0, line_bearing_checks=0,
    )
    assert "EMPTY_CURRENT_SLATE" in out["violations"]


def test_attach_count_mismatch_is_violation():
    out = _cycle(attached_count=11)
    assert "EXACT_ID_ATTACH_COUNT_MISMATCH" in out["violations"]


def test_context_count_mismatch_is_violation():
    out = _cycle(derived_context_count=11)
    assert "PROBABILITY_CONTEXT_COUNT_MISMATCH" in out["violations"]


def test_fallback_matching_is_violation():
    out = _cycle(fallback_matching_used=True)
    assert "FALLBACK_MATCHING_USED" in out["violations"]


def test_fallback_matching_must_be_boolean():
    with pytest.raises(MLBStep6BCanaryMonitorError):
        _cycle(fallback_matching_used=1)


def test_rollout_must_be_enabled():
    out = _cycle(rollout_enabled=False)
    assert "STEP6A_CANARY_NOT_ENABLED" in out["violations"]


def test_rollout_enabled_must_be_boolean():
    with pytest.raises(MLBStep6BCanaryMonitorError):
        _cycle(rollout_enabled="true")


def test_rollout_must_remain_10_percent():
    out = _cycle(rollout_percent=9.0)
    assert "STEP6A_PERCENT_NOT_10" in out["violations"]


def test_rollout_percent_must_be_numeric():
    with pytest.raises(MLBStep6BCanaryMonitorError):
        _cycle(rollout_percent="bad")


def test_negative_rollout_percent_is_rejected():
    with pytest.raises(MLBStep6BCanaryMonitorError):
        _cycle(rollout_percent=-1)


def test_cohort_size_mismatch_is_violation():
    out = _cycle(selected_game_ids=())
    assert "CANARY_COHORT_SIZE_MISMATCH" in out["violations"]


def test_realized_percent_never_exceeds_cap_on_valid_12_game_cohort():
    out = _cycle()
    assert out["realized_percent"] <= MAX_CANARY_PERCENT


def test_total_check_coverage_mismatch_is_violation():
    out = _cycle(total_checks=71)
    assert "LIVE_CHECK_COVERAGE_MISMATCH" in out["violations"]


def test_enrolled_check_coverage_mismatch_is_violation():
    out = _cycle(enrolled_checks=5)
    assert "ENROLLED_CHECK_COVERAGE_MISMATCH" in out["violations"]


def test_allow_block_partition_mismatch_is_violation():
    out = _cycle(allow_count=2, block_count=3)
    assert "ENROLLED_GATE_PARTITION_MISMATCH" in out["violations"]


def test_nonenrolled_partition_mismatch_is_violation():
    out = _cycle(nonenrolled_passthrough=65)
    assert "CANARY_PARTITION_MISMATCH" in out["violations"]


def test_rollback_mismatch_is_violation():
    out = _cycle(rollback_passthrough=71)
    assert "ROLLBACK_PASSTHROUGH_MISMATCH" in out["violations"]


def test_line_bearing_coverage_mismatch_is_violation():
    out = _cycle(line_bearing_checks=47)
    assert "LINE_BEARING_COVERAGE_MISMATCH" in out["violations"]


def test_feed_older_than_five_minutes_is_stale():
    out = _cycle(
        observed_at_utc=BASE_TIME,
        collected_at_utc=BASE_TIME - timedelta(seconds=MAX_FEED_AGE_SECONDS + 1),
    )
    assert "FEED_STALE" in out["violations"]


def test_feed_approaching_stale_limit_warns():
    out = _cycle(
        observed_at_utc=BASE_TIME,
        collected_at_utc=BASE_TIME - timedelta(seconds=MAX_FEED_AGE_SECONDS * 0.8),
    )
    assert "FEED_AGE_APPROACHING_LIMIT" in out["warnings"]
    assert "FEED_STALE" not in out["violations"]


def test_future_collected_time_is_clamped_to_zero_age():
    out = _cycle(observed_at_utc=BASE_TIME, collected_at_utc=BASE_TIME + timedelta(seconds=5))
    assert out["feed_age_seconds"] == 0.0


def test_naive_timestamps_are_interpreted_as_utc():
    out = _cycle(observed_at_utc="2026-08-31T16:40:00", collected_at_utc="2026-08-31T16:39:58")
    assert out["feed_age_seconds"] == 2.0


def test_zulu_timestamps_are_supported():
    out = _cycle(observed_at_utc="2026-08-31T16:40:00Z", collected_at_utc="2026-08-31T16:39:58Z")
    assert out["feed_age_seconds"] == 2.0


def test_invalid_timestamp_is_rejected():
    with pytest.raises(MLBStep6BCanaryMonitorError):
        _cycle(observed_at_utc="not-time")


def test_negative_count_is_rejected():
    with pytest.raises(MLBStep6BCanaryMonitorError):
        _cycle(allow_count=-1)


def test_boolean_count_is_rejected():
    with pytest.raises(MLBStep6BCanaryMonitorError):
        _cycle(allow_count=True)


def test_protected_impact_drift_is_violation():
    out = _cycle(protected_impacts_clear=False)
    assert "PROTECTED_IMPACT_DRIFT" in out["violations"]


def test_protected_impact_flag_must_be_boolean():
    with pytest.raises(MLBStep6BCanaryMonitorError):
        _cycle(protected_impacts_clear=1)


def test_cycle_exposes_all_no_impact_flags():
    out = _cycle()
    for key in (
        "model_math_impact", "pick_strength_impact", "ranking_math_impact",
        "risk_logic_impact", "wagering_impact", "durable_persistence", "wnba_impact",
    ):
        assert out[key] is False


def test_window_exposes_all_no_impact_flags():
    out = evaluate_canary_monitor_window(_window())
    for key in (
        "model_math_impact", "pick_strength_impact", "ranking_math_impact",
        "risk_logic_impact", "wagering_impact", "durable_persistence", "wnba_impact",
    ):
        assert out[key] is False


def test_window_aggregates_gate_counts():
    out = evaluate_canary_monitor_window(_window())
    assert out["total_enrolled_checks"] == 24
    assert out["total_allow_count"] == 8
    assert out["total_block_count"] == 16
    assert out["total_rollback_passthrough"] == 288


def test_window_tracks_max_feed_age():
    rows = _window()
    rows[-1] = _cycle(3, observed_at_utc=BASE_TIME, collected_at_utc=BASE_TIME - timedelta(seconds=120))
    out = evaluate_canary_monitor_window(rows)
    assert out["max_feed_age_seconds"] == 120.0


def test_cycle_index_must_be_nonnegative_integer():
    with pytest.raises(MLBStep6BCanaryMonitorError):
        _cycle(cycle_index=-1)


def test_cycle_snapshot_key_is_stable_for_same_snapshot_and_slate():
    one = _cycle(0)
    two = _cycle(1, collected_at_utc=one["collected_at_utc"])
    assert one["snapshot_key"] == two["snapshot_key"]


def test_cycle_snapshot_key_changes_when_collection_time_changes():
    one = _cycle(0)
    two = _cycle(1)
    assert one["snapshot_key"] != two["snapshot_key"]


def test_window_rejects_string_cycles_container():
    with pytest.raises(MLBStep6BCanaryMonitorError):
        evaluate_canary_monitor_window("not-cycles")
