from __future__ import annotations

from copy import deepcopy

import pytest

from sports_api.mlb_step9_final_freeze_v1 import PROTECTED_INVARIANTS
from sports_api.mlb_step12_final_runtime_freeze_v1 import (
    FINAL_CERTIFICATION_MARKER as STEP12_MARKER,
    FINAL_FREEZE_STATUS as STEP12_STATUS,
    RUNTIME_MODE as STEP12_MODE,
    final_runtime_freeze_manifest,
)
from sports_api.mlb_step13a_bounded_scheduler_v1 import (
    DATA_TYPE,
    DEFAULT_INTERVAL_SECONDS,
    FINAL_CERTIFICATION_MARKER,
    MAX_INTERVAL_SECONDS,
    MAX_PERMITS_PER_TICK,
    MIN_INTERVAL_SECONDS,
    MLBStep13ABoundedSchedulerError,
    RUNTIME_MODE,
    SCHEMA_VERSION,
    SCHEDULER_STATUS,
    STEP13A_BASE_MAIN_SHA,
    bounded_scheduler_manifest,
    build_bounded_scheduler_tick,
    validate_bounded_scheduler_tick,
)

BASE_SHA = "6f67626c064facf3402c8fdcb66b00832bdb47d1"
ANCHOR = "2026-09-01T19:00:00Z"


def _build(
    *,
    evaluated_at_utc: str = ANCHOR,
    scheduler_anchor_utc: str = ANCHOR,
    scheduler_state=None,
    scheduler_enabled: bool = True,
    interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
):
    return build_bounded_scheduler_tick(
        evaluated_at_utc=evaluated_at_utc,
        scheduler_anchor_utc=scheduler_anchor_utc,
        scheduler_state=scheduler_state,
        step12_final_manifest=final_runtime_freeze_manifest(),
        scheduler_enabled=scheduler_enabled,
        interval_seconds=interval_seconds,
    )


def _completed_state(tick):
    return {
        "last_granted_slot_utc": tick["permit_slot_utc"],
        "active_cycle_id": None,
        "active_cycle_slot_utc": None,
    }


def _active_state(tick):
    return {
        "last_granted_slot_utc": tick["permit_slot_utc"],
        "active_cycle_id": tick["permit_cycle_id"],
        "active_cycle_slot_utc": tick["permit_slot_utc"],
    }


def test_constants_are_exact():
    assert DATA_TYPE == "mlb_step13a_bounded_scheduler_v1"
    assert SCHEMA_VERSION == 1
    assert STEP13A_BASE_MAIN_SHA == BASE_SHA
    assert SCHEDULER_STATUS == "STEP13A_BOUNDED_SCHEDULER_READY"
    assert RUNTIME_MODE == "SHADOW_ONLY"
    assert FINAL_CERTIFICATION_MARKER == "MLB_STEP13A_BOUNDED_SCHEDULER_GREEN"
    assert DEFAULT_INTERVAL_SECONDS == 30
    assert MIN_INTERVAL_SECONDS == 15
    assert MAX_INTERVAL_SECONDS == 300
    assert MAX_PERMITS_PER_TICK == 1


def test_manifest_pins_step12_final_freeze_exactly():
    manifest = bounded_scheduler_manifest()
    assert manifest["step12_final_freeze_status_required"] == STEP12_STATUS
    assert manifest["step12_final_runtime_mode_required"] == STEP12_MODE
    assert manifest["step12_final_certification_marker_required"] == STEP12_MARKER
    assert manifest["bounded_scheduler_requirement_present"] is True


@pytest.mark.parametrize(
    "key",
    [
        "fixed_cadence_required",
        "utc_anchor_required",
        "caller_owned_scheduler_state_required",
        "at_most_one_permit_per_tick",
        "duplicate_slot_permits_forbidden",
        "overlapping_cycles_forbidden",
        "active_cycle_blocks_new_permit",
        "catch_up_bursts_forbidden",
        "missed_slots_are_not_replayed",
        "future_runtime_supervisor_required",
        "future_reliability_recovery_step_required",
        "future_scheduler_freeze_required",
    ],
)
def test_manifest_required_guards_are_true(key):
    assert bounded_scheduler_manifest()[key] is True


@pytest.mark.parametrize(
    "key",
    [
        "stale_active_cycle_recovery_added_by_step13a",
        "scheduler_sleep_loop_added_by_step13a",
        "background_thread_added_by_step13a",
        "background_process_added_by_step13a",
        "network_io_added_by_step13a",
        "provider_network_calls_enabled_by_step13a",
        "production_api_wiring_added_by_step13a",
        "production_runtime_wiring_added_by_step13a",
        "production_scheduler_activation_enabled",
        "production_database_writes_enabled",
        "persistence_schema_changed_by_step13a",
        "actionable_output_enabled",
        "production_provider_consensus_enabled",
        "production_provider_failover_enabled",
        "best_price_selection_enabled",
        "provider_weighting_enabled",
        "price_fabrication_allowed",
        "fallback_price_fabrication_allowed",
        "team_name_join_allowed",
        "player_name_join_allowed",
        "fuzzy_matching_allowed",
        "synthetic_game_id_allowed",
        "shadow_output_as_model_input_allowed",
        "shadow_output_as_sportsbook_input_allowed",
        "live_board_as_model_input_allowed",
        "live_board_as_sportsbook_input_allowed",
        "persisted_snapshot_as_model_input_allowed",
        "persisted_snapshot_as_sportsbook_input_allowed",
    ],
)
def test_manifest_forbidden_behaviors_are_false(key):
    assert bounded_scheduler_manifest()[key] is False


def test_all_protected_invariants_remain_false():
    manifest = bounded_scheduler_manifest()
    assert PROTECTED_INVARIANTS
    for key, value in PROTECTED_INVARIANTS.items():
        assert value is False
        assert manifest[key] is False


@pytest.mark.parametrize("interval", [15, 30, 300])
def test_interval_boundaries_and_default_are_allowed(interval):
    tick = _build(interval_seconds=interval)
    assert tick["interval_seconds"] == interval
    assert tick["permit_granted"] is True


@pytest.mark.parametrize("interval", [14, 301, True, 30.0, "30", None])
def test_invalid_intervals_fail_closed(interval):
    with pytest.raises(MLBStep13ABoundedSchedulerError):
        _build(interval_seconds=interval)


def test_non_mapping_step12_manifest_fails_closed():
    with pytest.raises(MLBStep13ABoundedSchedulerError):
        build_bounded_scheduler_tick(
            evaluated_at_utc=ANCHOR,
            scheduler_anchor_utc=ANCHOR,
            scheduler_state=None,
            step12_final_manifest=None,
            scheduler_enabled=True,
        )


def test_tampered_step12_manifest_fails_closed():
    manifest = final_runtime_freeze_manifest()
    manifest["tampered"] = True
    with pytest.raises(MLBStep13ABoundedSchedulerError):
        build_bounded_scheduler_tick(
            evaluated_at_utc=ANCHOR,
            scheduler_anchor_utc=ANCHOR,
            scheduler_state=None,
            step12_final_manifest=manifest,
            scheduler_enabled=True,
        )


@pytest.mark.parametrize("value", [1, 0, "true", [], {"enabled": True}])
def test_scheduler_enabled_requires_exact_boolean(value):
    with pytest.raises(MLBStep13ABoundedSchedulerError):
        _build(scheduler_enabled=value)


@pytest.mark.parametrize(
    "value",
    [
        "2026-09-01 19:00:00Z",
        "2026-09-01T19:00:00",
        "2026-09-01T19:00:00+00:00",
        "not-a-time",
        123,
    ],
)
def test_invalid_evaluated_timestamp_fails_closed(value):
    with pytest.raises(MLBStep13ABoundedSchedulerError):
        _build(evaluated_at_utc=value)


@pytest.mark.parametrize(
    "value",
    [
        "2026-09-01 19:00:00Z",
        "2026-09-01T19:00:00",
        "2026-09-01T19:00:00+00:00",
        "not-a-time",
        123,
    ],
)
def test_invalid_anchor_timestamp_fails_closed(value):
    with pytest.raises(MLBStep13ABoundedSchedulerError):
        _build(scheduler_anchor_utc=value)


def test_anchor_requires_whole_second_precision():
    with pytest.raises(MLBStep13ABoundedSchedulerError):
        _build(scheduler_anchor_utc="2026-09-01T19:00:00.100000Z")


def test_anchor_cannot_be_in_future():
    with pytest.raises(MLBStep13ABoundedSchedulerError):
        _build(
            evaluated_at_utc="2026-09-01T19:00:00Z",
            scheduler_anchor_utc="2026-09-01T19:00:01Z",
        )


def test_default_scheduler_is_disabled_and_grants_nothing():
    tick = build_bounded_scheduler_tick(
        evaluated_at_utc=ANCHOR,
        scheduler_anchor_utc=ANCHOR,
        scheduler_state=None,
        step12_final_manifest=final_runtime_freeze_manifest(),
    )
    assert tick["scheduler_enabled"] is False
    assert tick["decision_reason"] == "SCHEDULER_DISABLED"
    assert tick["permit_granted"] is False
    assert tick["permits_granted"] == 0
    assert tick["permit_cycle_id"] is None
    assert tick["permit_slot_utc"] is None


def test_first_enabled_tick_grants_exactly_one_current_slot_permit():
    tick = _build()
    assert tick["current_slot_index"] == 0
    assert tick["current_slot_utc"] == ANCHOR
    assert tick["next_slot_utc"] == "2026-09-01T19:00:30Z"
    assert tick["decision_reason"] == "FIRST_CURRENT_SLOT_ELIGIBLE"
    assert tick["permit_granted"] is True
    assert tick["permits_granted"] == 1
    assert tick["permit_slot_utc"] == ANCHOR
    assert isinstance(tick["permit_cycle_id"], str)
    assert len(tick["permit_cycle_id"]) == 64


def test_same_inputs_are_bit_deterministic():
    assert _build() == _build()


def test_subsecond_evaluation_is_allowed_and_stays_in_current_slot():
    tick = _build(evaluated_at_utc="2026-09-01T19:00:29.999999Z")
    assert tick["current_slot_index"] == 0
    assert tick["current_slot_utc"] == ANCHOR
    assert tick["permit_slot_utc"] == ANCHOR


def test_boundary_evaluation_advances_to_next_slot():
    tick = _build(evaluated_at_utc="2026-09-01T19:00:30Z")
    assert tick["current_slot_index"] == 1
    assert tick["current_slot_utc"] == "2026-09-01T19:00:30Z"
    assert tick["next_slot_utc"] == "2026-09-01T19:01:00Z"


def test_cycle_id_is_stable_within_same_slot():
    a = _build(evaluated_at_utc="2026-09-01T19:00:01Z")
    b = _build(evaluated_at_utc="2026-09-01T19:00:29Z")
    assert a["current_slot_utc"] == b["current_slot_utc"]
    assert a["permit_cycle_id"] == b["permit_cycle_id"]


def test_cycle_id_changes_between_slots():
    a = _build(evaluated_at_utc="2026-09-01T19:00:01Z")
    b = _build(evaluated_at_utc="2026-09-01T19:00:30Z")
    assert a["permit_cycle_id"] != b["permit_cycle_id"]


def test_recorded_current_slot_cannot_be_granted_twice():
    first = _build()
    second = _build(
        evaluated_at_utc="2026-09-01T19:00:29Z",
        scheduler_state=_completed_state(first),
    )
    assert second["decision_reason"] == "CURRENT_SLOT_ALREADY_GRANTED"
    assert second["permit_granted"] is False
    assert second["permits_granted"] == 0


def test_next_slot_is_eligible_after_prior_slot_was_recorded():
    first = _build()
    second = _build(
        evaluated_at_utc="2026-09-01T19:00:30Z",
        scheduler_state=_completed_state(first),
    )
    assert second["decision_reason"] == "CURRENT_SLOT_ELIGIBLE"
    assert second["permit_granted"] is True
    assert second["permit_slot_utc"] == "2026-09-01T19:00:30Z"


def test_missed_slots_are_counted_but_never_replayed():
    first = _build()
    late = _build(
        evaluated_at_utc="2026-09-01T19:05:00Z",
        scheduler_state=_completed_state(first),
    )
    assert late["current_slot_index"] == 10
    assert late["missed_slot_count"] == 9
    assert late["missed_slots_replayed"] == 0
    assert late["catch_up_cycles_granted"] == 0
    assert late["permits_granted"] == 1
    assert late["permit_slot_utc"] == "2026-09-01T19:05:00Z"


def test_active_cycle_blocks_overlap_in_same_slot():
    first = _build()
    blocked = _build(
        evaluated_at_utc="2026-09-01T19:00:10Z",
        scheduler_state=_active_state(first),
    )
    assert blocked["decision_reason"] == "ACTIVE_CYCLE_OVERLAP_BLOCKED"
    assert blocked["overlap_blocked"] is True
    assert blocked["active_cycle_age_slots"] == 0
    assert blocked["permit_granted"] is False


def test_active_cycle_blocks_overlap_even_after_multiple_slots():
    first = _build()
    blocked = _build(
        evaluated_at_utc="2026-09-01T19:03:00Z",
        scheduler_state=_active_state(first),
    )
    assert blocked["decision_reason"] == "ACTIVE_CYCLE_OVERLAP_BLOCKED"
    assert blocked["active_cycle_age_slots"] == 6
    assert blocked["missed_slot_count"] == 5
    assert blocked["permit_granted"] is False
    assert blocked["permits_granted"] == 0


@pytest.mark.parametrize("value", [[], "state", 1, True])
def test_scheduler_state_must_be_mapping_or_none(value):
    with pytest.raises(MLBStep13ABoundedSchedulerError):
        _build(scheduler_state=value)


def test_scheduler_state_unknown_keys_fail_closed():
    with pytest.raises(MLBStep13ABoundedSchedulerError):
        _build(scheduler_state={"unknown": "value"})


def test_active_slot_without_id_fails_closed():
    with pytest.raises(MLBStep13ABoundedSchedulerError):
        _build(
            scheduler_state={
                "last_granted_slot_utc": ANCHOR,
                "active_cycle_slot_utc": ANCHOR,
            }
        )


def test_active_id_without_slot_fails_closed():
    with pytest.raises(MLBStep13ABoundedSchedulerError):
        _build(
            scheduler_state={
                "last_granted_slot_utc": ANCHOR,
                "active_cycle_id": "a" * 64,
            }
        )


@pytest.mark.parametrize("bad_id", ["a" * 63, "A" * 64, "g" * 64, 123])
def test_active_id_format_is_strict(bad_id):
    with pytest.raises(MLBStep13ABoundedSchedulerError):
        _build(
            scheduler_state={
                "last_granted_slot_utc": ANCHOR,
                "active_cycle_id": bad_id,
                "active_cycle_slot_utc": ANCHOR,
            }
        )


def test_active_id_must_match_deterministic_slot_id():
    with pytest.raises(MLBStep13ABoundedSchedulerError):
        _build(
            scheduler_state={
                "last_granted_slot_utc": ANCHOR,
                "active_cycle_id": "a" * 64,
                "active_cycle_slot_utc": ANCHOR,
            }
        )


def test_active_cycle_requires_last_granted_slot():
    first = _build()
    with pytest.raises(MLBStep13ABoundedSchedulerError):
        _build(
            scheduler_state={
                "active_cycle_id": first["permit_cycle_id"],
                "active_cycle_slot_utc": first["permit_slot_utc"],
            }
        )


def test_active_slot_must_equal_last_granted_slot():
    first = _build()
    second = _build(evaluated_at_utc="2026-09-01T19:00:30Z")
    with pytest.raises(MLBStep13ABoundedSchedulerError):
        _build(
            evaluated_at_utc="2026-09-01T19:00:30Z",
            scheduler_state={
                "last_granted_slot_utc": second["permit_slot_utc"],
                "active_cycle_id": first["permit_cycle_id"],
                "active_cycle_slot_utc": first["permit_slot_utc"],
            },
        )


def test_misaligned_last_granted_slot_fails_closed():
    with pytest.raises(MLBStep13ABoundedSchedulerError):
        _build(
            evaluated_at_utc="2026-09-01T19:01:00Z",
            scheduler_state={"last_granted_slot_utc": "2026-09-01T19:00:01Z"},
        )


def test_fractional_state_slot_fails_closed():
    with pytest.raises(MLBStep13ABoundedSchedulerError):
        _build(
            scheduler_state={
                "last_granted_slot_utc": "2026-09-01T19:00:00.100000Z"
            }
        )


def test_state_before_anchor_fails_closed():
    with pytest.raises(MLBStep13ABoundedSchedulerError):
        _build(
            scheduler_state={"last_granted_slot_utc": "2026-09-01T18:59:30Z"}
        )


def test_state_ahead_of_current_slot_fails_closed():
    with pytest.raises(MLBStep13ABoundedSchedulerError):
        _build(
            scheduler_state={"last_granted_slot_utc": "2026-09-01T19:00:30Z"}
        )


def test_input_state_is_not_mutated():
    state = {
        "last_granted_slot_utc": ANCHOR,
        "active_cycle_id": None,
        "active_cycle_slot_utc": None,
    }
    before = deepcopy(state)
    _build(evaluated_at_utc="2026-09-01T19:00:30Z", scheduler_state=state)
    assert state == before


def test_normalized_state_contains_all_contract_keys():
    tick = _build(scheduler_state={})
    assert tick["scheduler_state"] == {
        "last_granted_slot_utc": None,
        "active_cycle_id": None,
        "active_cycle_slot_utc": None,
    }


def test_valid_tick_rebuilds_exactly():
    tick = _build(evaluated_at_utc="2026-09-01T19:00:29.123456Z")
    validation = validate_bounded_scheduler_tick(tick)
    assert validation["tick_valid"] is True
    assert validation["failures"] == []


@pytest.mark.parametrize("value", [None, [], "tick", 1, True])
def test_non_mapping_tick_validation_fails_closed(value):
    result = validate_bounded_scheduler_tick(value)
    assert result["tick_valid"] is False
    assert result["failures"] == ["STEP13A_TICK_NOT_MAPPING"]


@pytest.mark.parametrize(
    "field",
    [
        "scheduler_status",
        "runtime_mode",
        "decision_reason",
        "permit_granted",
        "permits_granted",
        "permit_cycle_id",
        "current_slot_index",
        "current_slot_utc",
        "missed_slot_count",
        "network_io_performed",
        "decision_sha256",
    ],
)
def test_tampered_tick_fails_exact_validation(field):
    tick = _build()
    if isinstance(tick[field], bool):
        tick[field] = not tick[field]
    elif isinstance(tick[field], int):
        tick[field] += 1
    elif tick[field] is None:
        tick[field] = "tampered"
    else:
        tick[field] = f"{tick[field]}-tampered"
    result = validate_bounded_scheduler_tick(tick)
    assert result["tick_valid"] is False
    assert result["failures"]


@pytest.mark.parametrize(
    "field",
    [
        "runtime_cycle_executed",
        "network_io_performed",
        "production_api_wiring",
        "production_runtime_wiring",
        "production_scheduler_activation",
        "actionable_output_enabled",
        "production_provider_consensus_used",
        "production_provider_failover_used",
        "best_price_selection_used",
        "provider_weighting_used",
        "price_fabrication_used",
        "fallback_price_fabrication_used",
        "team_name_join_used",
        "player_name_join_used",
        "fuzzy_matching_used",
        "synthetic_game_id_used",
        "shadow_output_as_model_input",
        "shadow_output_as_sportsbook_input",
        "live_board_as_model_input",
        "live_board_as_sportsbook_input",
        "persisted_snapshot_as_model_input",
        "persisted_snapshot_as_sportsbook_input",
    ],
)
def test_tick_never_enables_forbidden_behavior(field):
    assert _build()[field] is False


def test_tick_reports_zero_provider_calls_and_database_writes():
    tick = _build()
    assert tick["provider_network_calls"] == 0
    assert tick["production_database_writes"] == 0


def test_disabled_scheduler_still_never_replays_missed_slots():
    first = _build()
    tick = _build(
        evaluated_at_utc="2026-09-01T19:05:00Z",
        scheduler_state=_completed_state(first),
        scheduler_enabled=False,
    )
    assert tick["missed_slot_count"] == 9
    assert tick["missed_slots_replayed"] == 0
    assert tick["catch_up_cycles_granted"] == 0
    assert tick["permits_granted"] == 0


def test_interval_changes_also_change_cycle_identity():
    a = _build(interval_seconds=30)
    b = _build(interval_seconds=60)
    assert a["permit_cycle_id"] != b["permit_cycle_id"]


def test_anchor_changes_also_change_cycle_identity():
    a = _build(
        evaluated_at_utc="2026-09-01T19:00:30Z",
        scheduler_anchor_utc="2026-09-01T19:00:00Z",
    )
    b = _build(
        evaluated_at_utc="2026-09-01T19:00:30Z",
        scheduler_anchor_utc="2026-09-01T18:59:45Z",
    )
    assert a["permit_cycle_id"] != b["permit_cycle_id"]


def test_exact_step12_freeze_values_are_carried_in_every_tick():
    tick = _build()
    assert tick["step12_final_freeze_status"] == STEP12_STATUS
    assert tick["step12_final_runtime_mode"] == STEP12_MODE == "SHADOW_ONLY"
    assert tick["step12_final_certification_marker"] == STEP12_MARKER
