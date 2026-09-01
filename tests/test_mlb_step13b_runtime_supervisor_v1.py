from __future__ import annotations

from copy import deepcopy

import pytest

from sports_api.mlb_step9_final_freeze_v1 import PROTECTED_INVARIANTS
from sports_api.mlb_step13a_bounded_scheduler_v1 import (
    FINAL_CERTIFICATION_MARKER as STEP13A_MARKER,
    RUNTIME_MODE as STEP13A_MODE,
    SCHEDULER_STATUS as STEP13A_STATUS,
    bounded_scheduler_manifest,
    build_bounded_scheduler_tick,
)
from sports_api.mlb_step13b_runtime_supervisor_v1 import (
    DATA_TYPE,
    DEFAULT_MAX_CYCLE_RUNTIME_SECONDS,
    FINAL_CERTIFICATION_MARKER,
    MAX_MAX_CYCLE_RUNTIME_SECONDS,
    MIN_MAX_CYCLE_RUNTIME_SECONDS,
    MLBStep13BRuntimeSupervisorError,
    RUNTIME_MODE,
    SCHEMA_VERSION,
    STEP13B_BASE_MAIN_SHA,
    SUPERVISION_STATES,
    SUPERVISOR_STATUS,
    TERMINAL_OUTCOMES,
    build_runtime_supervision,
    runtime_supervisor_manifest,
    validate_runtime_supervision,
)

BASE_SHA = "1587b4825ad5ce01c8dcd669417da6046ede6921"
ANCHOR = "2026-09-01T19:10:00Z"


def _permit_tick(*, evaluated_at_utc: str = ANCHOR, scheduler_enabled: bool = True):
    return build_bounded_scheduler_tick(
        evaluated_at_utc=evaluated_at_utc,
        scheduler_anchor_utc=ANCHOR,
        scheduler_state=None,
        step12_final_manifest=__import__(
            "sports_api.mlb_step12_final_runtime_freeze_v1",
            fromlist=["final_runtime_freeze_manifest"],
        ).final_runtime_freeze_manifest(),
        scheduler_enabled=scheduler_enabled,
    )


def _active_tick(*, evaluated_at_utc: str = "2026-09-01T19:10:30Z"):
    first = _permit_tick()
    state = {
        "last_granted_slot_utc": first["permit_slot_utc"],
        "active_cycle_id": first["permit_cycle_id"],
        "active_cycle_slot_utc": first["permit_slot_utc"],
    }
    return build_bounded_scheduler_tick(
        evaluated_at_utc=evaluated_at_utc,
        scheduler_anchor_utc=ANCHOR,
        scheduler_state=state,
        step12_final_manifest=__import__(
            "sports_api.mlb_step12_final_runtime_freeze_v1",
            fromlist=["final_runtime_freeze_manifest"],
        ).final_runtime_freeze_manifest(),
        scheduler_enabled=True,
    )


def _completed_slot_tick():
    first = _permit_tick()
    state = {
        "last_granted_slot_utc": first["permit_slot_utc"],
        "active_cycle_id": None,
        "active_cycle_slot_utc": None,
    }
    return build_bounded_scheduler_tick(
        evaluated_at_utc="2026-09-01T19:10:10Z",
        scheduler_anchor_utc=ANCHOR,
        scheduler_state=state,
        step12_final_manifest=__import__(
            "sports_api.mlb_step12_final_runtime_freeze_v1",
            fromlist=["final_runtime_freeze_manifest"],
        ).final_runtime_freeze_manifest(),
        scheduler_enabled=True,
    )


def _observation(
    tick,
    *,
    started_at_utc: str = ANCHOR,
    finished_at_utc=None,
    outcome=None,
    failure_code=None,
):
    state = tick["scheduler_state"]
    cycle_id = state["active_cycle_id"] or tick["permit_cycle_id"]
    slot = state["active_cycle_slot_utc"] or tick["permit_slot_utc"]
    return {
        "cycle_id": cycle_id,
        "cycle_slot_utc": slot,
        "started_at_utc": started_at_utc,
        "finished_at_utc": finished_at_utc,
        "outcome": outcome,
        "failure_code": failure_code,
    }


def _supervise(
    tick=None,
    *,
    observed_at_utc: str = "2026-09-01T19:11:00Z",
    cycle_observation=None,
    max_cycle_runtime_seconds: int = DEFAULT_MAX_CYCLE_RUNTIME_SECONDS,
):
    tick = _permit_tick() if tick is None else tick
    return build_runtime_supervision(
        tick,
        observed_at_utc=observed_at_utc,
        cycle_observation=cycle_observation,
        step13a_manifest=bounded_scheduler_manifest(),
        max_cycle_runtime_seconds=max_cycle_runtime_seconds,
    )


def test_constants_are_exact():
    assert DATA_TYPE == "mlb_step13b_runtime_supervisor_v1"
    assert SCHEMA_VERSION == 1
    assert STEP13B_BASE_MAIN_SHA == BASE_SHA
    assert SUPERVISOR_STATUS == "STEP13B_RUNTIME_SUPERVISOR_READY"
    assert RUNTIME_MODE == "SHADOW_ONLY"
    assert FINAL_CERTIFICATION_MARKER == "MLB_STEP13B_RUNTIME_SUPERVISOR_GREEN"
    assert DEFAULT_MAX_CYCLE_RUNTIME_SECONDS == 120
    assert MIN_MAX_CYCLE_RUNTIME_SECONDS == 15
    assert MAX_MAX_CYCLE_RUNTIME_SECONDS == 3600


def test_supervision_state_contract_is_exact():
    assert SUPERVISION_STATES == (
        "READY_TO_START",
        "RUNNING",
        "COMPLETED",
        "FAILED",
        "BLOCKED",
        "IDLE",
        "POTENTIALLY_STUCK",
    )
    assert TERMINAL_OUTCOMES == ("SUCCESS", "FAILURE")


def test_manifest_pins_step13a_exactly():
    manifest = runtime_supervisor_manifest()
    assert manifest["step13a_scheduler_status_required"] == STEP13A_STATUS
    assert manifest["step13a_runtime_mode_required"] == STEP13A_MODE
    assert manifest["step13a_final_certification_marker_required"] == STEP13A_MARKER


@pytest.mark.parametrize(
    "key",
    [
        "exact_step13a_tick_required",
        "exact_cycle_id_required",
        "exact_cycle_slot_required",
        "caller_supplied_cycle_observation_required_for_active_cycle",
        "running_cycle_age_monitored",
        "potentially_stuck_detection_enabled",
        "terminal_success_observed",
        "terminal_failure_observed",
        "scheduler_overlap_blocking_preserved",
        "failure_isolation_preserved",
        "supervisor_is_observational_only",
        "future_reliability_recovery_step_required",
        "future_scheduler_freeze_required",
    ],
)
def test_manifest_required_guards_are_true(key):
    assert runtime_supervisor_manifest()[key] is True


@pytest.mark.parametrize(
    "key",
    [
        "scheduler_state_mutation_added_by_step13b",
        "stuck_cycle_release_added_by_step13b",
        "retry_added_by_step13b",
        "restart_added_by_step13b",
        "cooldown_added_by_step13b",
        "runtime_cycle_execution_added_by_step13b",
        "scheduler_sleep_loop_added_by_step13b",
        "background_thread_added_by_step13b",
        "background_process_added_by_step13b",
        "network_io_added_by_step13b",
        "provider_network_calls_enabled_by_step13b",
        "production_api_wiring_added_by_step13b",
        "production_runtime_wiring_added_by_step13b",
        "production_scheduler_activation_enabled",
        "production_database_writes_enabled",
        "persistence_schema_changed_by_step13b",
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
    assert runtime_supervisor_manifest()[key] is False


def test_all_protected_invariants_remain_false():
    manifest = runtime_supervisor_manifest()
    assert PROTECTED_INVARIANTS
    for key, value in PROTECTED_INVARIANTS.items():
        assert value is False
        assert manifest[key] is False


@pytest.mark.parametrize("limit", [15, 120, 3600])
def test_runtime_limit_boundaries_are_allowed(limit):
    result = _supervise(max_cycle_runtime_seconds=limit)
    assert result["max_cycle_runtime_seconds"] == limit


@pytest.mark.parametrize("limit", [14, 3601, True, 120.0, "120", None])
def test_invalid_runtime_limits_fail_closed(limit):
    with pytest.raises(MLBStep13BRuntimeSupervisorError):
        _supervise(max_cycle_runtime_seconds=limit)


def test_non_mapping_step13a_manifest_fails_closed():
    with pytest.raises(MLBStep13BRuntimeSupervisorError):
        build_runtime_supervision(
            _permit_tick(),
            observed_at_utc="2026-09-01T19:11:00Z",
            cycle_observation=None,
            step13a_manifest=None,
        )


def test_tampered_step13a_manifest_fails_closed():
    manifest = bounded_scheduler_manifest()
    manifest["tampered"] = True
    with pytest.raises(MLBStep13BRuntimeSupervisorError):
        build_runtime_supervision(
            _permit_tick(),
            observed_at_utc="2026-09-01T19:11:00Z",
            cycle_observation=None,
            step13a_manifest=manifest,
        )


@pytest.mark.parametrize("value", [None, [], "tick", 1, True])
def test_scheduler_tick_must_be_mapping(value):
    with pytest.raises(MLBStep13BRuntimeSupervisorError):
        build_runtime_supervision(
            value,
            observed_at_utc="2026-09-01T19:11:00Z",
            cycle_observation=None,
            step13a_manifest=bounded_scheduler_manifest(),
        )


def test_tampered_scheduler_tick_fails_closed():
    tick = _permit_tick()
    tick["permit_cycle_id"] = "a" * 64
    with pytest.raises(MLBStep13BRuntimeSupervisorError):
        _supervise(tick)


@pytest.mark.parametrize(
    "value",
    [
        "2026-09-01 19:11:00Z",
        "2026-09-01T19:11:00",
        "2026-09-01T19:11:00+00:00",
        "bad",
        123,
    ],
)
def test_invalid_observed_timestamp_fails_closed(value):
    with pytest.raises(MLBStep13BRuntimeSupervisorError):
        _supervise(observed_at_utc=value)


def test_observed_time_cannot_precede_scheduler_tick():
    tick = _permit_tick(evaluated_at_utc="2026-09-01T19:10:30Z")
    with pytest.raises(MLBStep13BRuntimeSupervisorError):
        _supervise(tick, observed_at_utc="2026-09-01T19:10:29Z")


def test_new_permit_without_observation_is_ready_to_start():
    result = _supervise(observed_at_utc="2026-09-01T19:10:01Z")
    assert result["supervision_state"] == "READY_TO_START"
    assert result["cycle_identity_source"] == "PERMITTED"
    assert result["terminal"] is False
    assert result["cycle_age_seconds"] is None


def test_disabled_scheduler_is_blocked():
    tick = _permit_tick(scheduler_enabled=False)
    result = _supervise(tick, observed_at_utc="2026-09-01T19:10:01Z")
    assert result["supervision_state"] == "BLOCKED"
    assert result["cycle_identity_source"] == "NONE"
    assert result["cycle_id"] is None


def test_already_completed_slot_without_active_cycle_is_idle():
    result = _supervise(
        _completed_slot_tick(),
        observed_at_utc="2026-09-01T19:10:11Z",
    )
    assert result["supervision_state"] == "IDLE"
    assert result["cycle_identity_source"] == "NONE"


def test_active_cycle_requires_observation():
    with pytest.raises(MLBStep13BRuntimeSupervisorError):
        _supervise(_active_tick(), observed_at_utc="2026-09-01T19:10:31Z")


def test_active_cycle_running_classification():
    tick = _active_tick()
    observation = _observation(tick)
    result = _supervise(
        tick,
        observed_at_utc="2026-09-01T19:11:00Z",
        cycle_observation=observation,
    )
    assert result["supervision_state"] == "RUNNING"
    assert result["cycle_identity_source"] == "ACTIVE"
    assert result["cycle_age_seconds"] == 60.0
    assert result["potentially_stuck"] is False
    assert result["scheduler_overlap_blocked"] is True


def test_exact_runtime_limit_is_still_running():
    tick = _active_tick()
    result = _supervise(
        tick,
        observed_at_utc="2026-09-01T19:12:00Z",
        cycle_observation=_observation(tick),
        max_cycle_runtime_seconds=120,
    )
    assert result["cycle_age_seconds"] == 120.0
    assert result["supervision_state"] == "RUNNING"
    assert result["runtime_over_limit"] is False


def test_over_runtime_limit_is_potentially_stuck_only():
    tick = _active_tick()
    result = _supervise(
        tick,
        observed_at_utc="2026-09-01T19:12:01Z",
        cycle_observation=_observation(tick),
        max_cycle_runtime_seconds=120,
    )
    assert result["cycle_age_seconds"] == 121.0
    assert result["supervision_state"] == "POTENTIALLY_STUCK"
    assert result["runtime_over_limit"] is True
    assert result["potentially_stuck"] is True
    assert result["stuck_cycle_released"] is False
    assert result["retry_authorized"] is False
    assert result["restart_authorized"] is False


def test_successful_terminal_cycle_is_completed():
    tick = _active_tick()
    observation = _observation(
        tick,
        finished_at_utc="2026-09-01T19:10:45Z",
        outcome="success",
    )
    result = _supervise(
        tick,
        observed_at_utc="2026-09-01T19:11:00Z",
        cycle_observation=observation,
    )
    assert result["supervision_state"] == "COMPLETED"
    assert result["terminal"] is True
    assert result["success_observed"] is True
    assert result["failure_observed"] is False
    assert result["cycle_age_seconds"] == 45.0
    assert result["scheduler_state_release_candidate"] is True
    assert result["scheduler_state_mutated"] is False


def test_failed_terminal_cycle_is_failed_and_isolated():
    tick = _active_tick()
    observation = _observation(
        tick,
        finished_at_utc="2026-09-01T19:10:40Z",
        outcome="failure",
        failure_code="provider.timeout",
    )
    result = _supervise(
        tick,
        observed_at_utc="2026-09-01T19:11:00Z",
        cycle_observation=observation,
    )
    assert result["supervision_state"] == "FAILED"
    assert result["terminal"] is True
    assert result["success_observed"] is False
    assert result["failure_observed"] is True
    assert result["failure_code"] == "PROVIDER.TIMEOUT"
    assert result["retry_authorized"] is False
    assert result["restart_authorized"] is False
    assert result["scheduler_state_mutated"] is False


def test_terminal_permitted_cycle_is_not_scheduler_release_candidate():
    tick = _permit_tick()
    observation = _observation(
        tick,
        finished_at_utc="2026-09-01T19:10:10Z",
        outcome="SUCCESS",
    )
    result = _supervise(
        tick,
        observed_at_utc="2026-09-01T19:10:11Z",
        cycle_observation=observation,
    )
    assert result["supervision_state"] == "COMPLETED"
    assert result["cycle_identity_source"] == "PERMITTED"
    assert result["scheduler_state_release_candidate"] is False


@pytest.mark.parametrize("value", [[], "observation", 1, True])
def test_observation_must_be_mapping_or_none(value):
    with pytest.raises(MLBStep13BRuntimeSupervisorError):
        _supervise(cycle_observation=value)


def test_observation_unknown_keys_fail_closed():
    tick = _permit_tick()
    observation = _observation(tick)
    observation["unknown"] = True
    with pytest.raises(MLBStep13BRuntimeSupervisorError):
        _supervise(tick, cycle_observation=observation)


def test_observation_for_tick_without_cycle_identity_fails_closed():
    tick = _completed_slot_tick()
    fake = {
        "cycle_id": "a" * 64,
        "cycle_slot_utc": ANCHOR,
        "started_at_utc": ANCHOR,
        "finished_at_utc": None,
        "outcome": None,
        "failure_code": None,
    }
    with pytest.raises(MLBStep13BRuntimeSupervisorError):
        _supervise(tick, cycle_observation=fake)


@pytest.mark.parametrize("bad_id", ["a" * 63, "A" * 64, "g" * 64, 123])
def test_observation_cycle_id_format_is_strict(bad_id):
    tick = _permit_tick()
    observation = _observation(tick)
    observation["cycle_id"] = bad_id
    with pytest.raises(MLBStep13BRuntimeSupervisorError):
        _supervise(tick, cycle_observation=observation)


def test_observation_cycle_id_must_match_scheduler():
    tick = _permit_tick()
    observation = _observation(tick)
    observation["cycle_id"] = "a" * 64
    with pytest.raises(MLBStep13BRuntimeSupervisorError):
        _supervise(tick, cycle_observation=observation)


def test_observation_slot_must_match_scheduler():
    tick = _permit_tick()
    observation = _observation(tick)
    observation["cycle_slot_utc"] = "2026-09-01T19:10:30Z"
    with pytest.raises(MLBStep13BRuntimeSupervisorError):
        _supervise(tick, cycle_observation=observation)


def test_observation_started_time_cannot_be_future():
    tick = _permit_tick()
    observation = _observation(tick, started_at_utc="2026-09-01T19:11:01Z")
    with pytest.raises(MLBStep13BRuntimeSupervisorError):
        _supervise(
            tick,
            observed_at_utc="2026-09-01T19:11:00Z",
            cycle_observation=observation,
        )


def test_finished_time_cannot_precede_started_time():
    tick = _permit_tick()
    observation = _observation(
        tick,
        started_at_utc="2026-09-01T19:10:20Z",
        finished_at_utc="2026-09-01T19:10:19Z",
        outcome="SUCCESS",
    )
    with pytest.raises(MLBStep13BRuntimeSupervisorError):
        _supervise(tick, cycle_observation=observation)


def test_finished_time_cannot_be_after_observed_time():
    tick = _permit_tick()
    observation = _observation(
        tick,
        finished_at_utc="2026-09-01T19:11:01Z",
        outcome="SUCCESS",
    )
    with pytest.raises(MLBStep13BRuntimeSupervisorError):
        _supervise(
            tick,
            observed_at_utc="2026-09-01T19:11:00Z",
            cycle_observation=observation,
        )


@pytest.mark.parametrize("bad_outcome", ["CANCELLED", "OK", 1, True, []])
def test_invalid_outcome_fails_closed(bad_outcome):
    tick = _permit_tick()
    observation = _observation(
        tick,
        finished_at_utc="2026-09-01T19:10:10Z",
        outcome=bad_outcome,
    )
    with pytest.raises(MLBStep13BRuntimeSupervisorError):
        _supervise(tick, cycle_observation=observation)


def test_outcome_requires_finished_time():
    tick = _permit_tick()
    observation = _observation(tick, outcome="SUCCESS")
    with pytest.raises(MLBStep13BRuntimeSupervisorError):
        _supervise(tick, cycle_observation=observation)


def test_finished_time_requires_outcome():
    tick = _permit_tick()
    observation = _observation(
        tick,
        finished_at_utc="2026-09-01T19:10:10Z",
    )
    with pytest.raises(MLBStep13BRuntimeSupervisorError):
        _supervise(tick, cycle_observation=observation)


def test_failure_requires_failure_code():
    tick = _permit_tick()
    observation = _observation(
        tick,
        finished_at_utc="2026-09-01T19:10:10Z",
        outcome="FAILURE",
    )
    with pytest.raises(MLBStep13BRuntimeSupervisorError):
        _supervise(tick, cycle_observation=observation)


@pytest.mark.parametrize("bad_code", ["", "bad code", "!BAD", "x" * 129, 123])
def test_failure_code_format_is_strict(bad_code):
    tick = _permit_tick()
    observation = _observation(
        tick,
        finished_at_utc="2026-09-01T19:10:10Z",
        outcome="FAILURE",
        failure_code=bad_code,
    )
    with pytest.raises(MLBStep13BRuntimeSupervisorError):
        _supervise(tick, cycle_observation=observation)


def test_success_forbids_failure_code():
    tick = _permit_tick()
    observation = _observation(
        tick,
        finished_at_utc="2026-09-01T19:10:10Z",
        outcome="SUCCESS",
        failure_code="ERROR",
    )
    with pytest.raises(MLBStep13BRuntimeSupervisorError):
        _supervise(tick, cycle_observation=observation)


def test_running_forbids_failure_code():
    tick = _permit_tick()
    observation = _observation(tick, failure_code="ERROR")
    with pytest.raises(MLBStep13BRuntimeSupervisorError):
        _supervise(tick, cycle_observation=observation)


def test_inputs_are_not_mutated():
    tick = _permit_tick()
    observation = _observation(tick)
    tick_before = deepcopy(tick)
    observation_before = deepcopy(observation)
    _supervise(tick, cycle_observation=observation)
    assert tick == tick_before
    assert observation == observation_before


def test_same_inputs_are_bit_deterministic():
    tick = _permit_tick()
    observation = _observation(tick)
    a = _supervise(tick, cycle_observation=observation)
    b = _supervise(tick, cycle_observation=observation)
    assert a == b


def test_valid_supervision_rebuilds_exactly():
    tick = _active_tick()
    record = _supervise(tick, cycle_observation=_observation(tick))
    validation = validate_runtime_supervision(record)
    assert validation["supervision_valid"] is True
    assert validation["failures"] == []


@pytest.mark.parametrize("value", [None, [], "record", 1, True])
def test_non_mapping_supervision_validation_fails_closed(value):
    result = validate_runtime_supervision(value)
    assert result["supervision_valid"] is False
    assert result["failures"] == ["STEP13B_SUPERVISION_NOT_MAPPING"]


@pytest.mark.parametrize(
    "field",
    [
        "supervisor_status",
        "runtime_mode",
        "supervision_state",
        "cycle_id",
        "cycle_slot_utc",
        "runtime_over_limit",
        "potentially_stuck",
        "terminal",
        "network_io_performed",
        "supervision_sha256",
    ],
)
def test_tampered_supervision_fails_exact_validation(field):
    record = _supervise()
    if isinstance(record[field], bool):
        record[field] = not record[field]
    elif isinstance(record[field], int):
        record[field] += 1
    elif record[field] is None:
        record[field] = "tampered"
    else:
        record[field] = f"{record[field]}-tampered"
    validation = validate_runtime_supervision(record)
    assert validation["supervision_valid"] is False
    assert validation["failures"]


@pytest.mark.parametrize(
    "field",
    [
        "scheduler_state_mutated",
        "stuck_cycle_released",
        "retry_authorized",
        "restart_authorized",
        "cooldown_applied",
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
def test_supervision_never_enables_forbidden_behavior(field):
    assert _supervise()[field] is False


def test_supervision_reports_zero_provider_calls_and_database_writes():
    result = _supervise()
    assert result["provider_network_calls"] == 0
    assert result["production_database_writes"] == 0


def test_runtime_age_uses_finish_time_for_terminal_cycle():
    tick = _active_tick()
    observation = _observation(
        tick,
        started_at_utc="2026-09-01T19:10:05Z",
        finished_at_utc="2026-09-01T19:10:35Z",
        outcome="SUCCESS",
    )
    result = _supervise(
        tick,
        observed_at_utc="2026-09-01T19:20:00Z",
        cycle_observation=observation,
        max_cycle_runtime_seconds=15,
    )
    assert result["cycle_age_seconds"] == 30.0
    assert result["runtime_over_limit"] is False
    assert result["potentially_stuck"] is False
    assert result["supervision_state"] == "COMPLETED"


def test_subsecond_runtime_age_is_preserved_deterministically():
    tick = _permit_tick()
    observation = _observation(
        tick,
        started_at_utc="2026-09-01T19:10:00.250000Z",
    )
    result = _supervise(
        tick,
        observed_at_utc="2026-09-01T19:10:01.750000Z",
        cycle_observation=observation,
    )
    assert result["cycle_age_seconds"] == 1.5
    assert result["supervision_state"] == "RUNNING"


def test_exact_step13a_values_are_carried_in_every_record():
    result = _supervise()
    assert result["step13a_scheduler_status"] == STEP13A_STATUS
    assert result["step13a_runtime_mode"] == STEP13A_MODE == "SHADOW_ONLY"
    assert result["step13a_final_certification_marker"] == STEP13A_MARKER
