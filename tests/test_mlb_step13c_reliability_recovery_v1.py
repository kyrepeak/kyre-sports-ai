from __future__ import annotations

from copy import deepcopy

import pytest

from sports_api.mlb_step12_final_runtime_freeze_v1 import final_runtime_freeze_manifest
from sports_api.mlb_step13a_bounded_scheduler_v1 import (
    bounded_scheduler_manifest,
    build_bounded_scheduler_tick,
)
from sports_api.mlb_step13b_runtime_supervisor_v1 import (
    build_runtime_supervision,
)
from sports_api.mlb_step13c_reliability_recovery_v1 import (
    DATA_TYPE,
    FINAL_CERTIFICATION_MARKER,
    RECOVERY_ACTIONS,
    RELIABILITY_STATUS,
    RUNTIME_MODE,
    STEP13C_BASE_MAIN_SHA,
    MLBStep13CDuplicateRecoveryError,
    MLBStep13CReliabilityRecoveryError,
    acquire_process_local_recovery_token,
    build_recovery_decision,
    build_recovery_state,
    reliability_recovery_manifest,
    release_process_local_recovery_token,
    validate_recovery_decision,
)

ANCHOR = "2026-09-01T19:10:00Z"
STEP12 = final_runtime_freeze_manifest()
STEP13A = bounded_scheduler_manifest()


def _permit():
    return build_bounded_scheduler_tick(
        evaluated_at_utc=ANCHOR,
        scheduler_anchor_utc=ANCHOR,
        scheduler_state=None,
        step12_final_manifest=STEP12,
        scheduler_enabled=True,
    )


def _active_tick():
    permit = _permit()
    active_state = {
        "last_granted_slot_utc": permit["permit_slot_utc"],
        "active_cycle_id": permit["permit_cycle_id"],
        "active_cycle_slot_utc": permit["permit_slot_utc"],
    }
    tick = build_bounded_scheduler_tick(
        evaluated_at_utc="2026-09-01T19:10:30Z",
        scheduler_anchor_utc=ANCHOR,
        scheduler_state=active_state,
        step12_final_manifest=STEP12,
        scheduler_enabled=True,
    )
    return permit, tick


def _base_observation():
    permit, _ = _active_tick()
    return {
        "cycle_id": permit["permit_cycle_id"],
        "cycle_slot_utc": permit["permit_slot_utc"],
        "started_at_utc": ANCHOR,
        "finished_at_utc": None,
        "outcome": None,
        "failure_code": None,
    }


def _running():
    _, tick = _active_tick()
    return build_runtime_supervision(
        tick,
        observed_at_utc="2026-09-01T19:11:00Z",
        cycle_observation=_base_observation(),
        step13a_manifest=STEP13A,
    )


def _stuck(observed="2026-09-01T19:12:31Z"):
    _, tick = _active_tick()
    return build_runtime_supervision(
        tick,
        observed_at_utc=observed,
        cycle_observation=_base_observation(),
        step13a_manifest=STEP13A,
    )


def _failed(code="PROVIDER.TIMEOUT"):
    _, tick = _active_tick()
    obs = _base_observation()
    obs.update(
        {
            "finished_at_utc": "2026-09-01T19:10:40Z",
            "outcome": "FAILURE",
            "failure_code": code,
        }
    )
    return build_runtime_supervision(
        tick,
        observed_at_utc="2026-09-01T19:11:00Z",
        cycle_observation=obs,
        step13a_manifest=STEP13A,
    )


def _completed():
    _, tick = _active_tick()
    obs = _base_observation()
    obs.update(
        {
            "finished_at_utc": "2026-09-01T19:10:40Z",
            "outcome": "SUCCESS",
        }
    )
    return build_runtime_supervision(
        tick,
        observed_at_utc="2026-09-01T19:11:00Z",
        cycle_observation=obs,
        step13a_manifest=STEP13A,
    )


def _ready():
    permit = _permit()
    return build_runtime_supervision(
        permit,
        observed_at_utc="2026-09-01T19:10:01Z",
        cycle_observation=None,
        step13a_manifest=STEP13A,
    )


def _blocked():
    tick = build_bounded_scheduler_tick(
        evaluated_at_utc=ANCHOR,
        scheduler_anchor_utc=ANCHOR,
        scheduler_state=None,
        step12_final_manifest=STEP12,
        scheduler_enabled=False,
    )
    return build_runtime_supervision(
        tick,
        observed_at_utc="2026-09-01T19:10:01Z",
        cycle_observation=None,
        step13a_manifest=STEP13A,
    )


def _decision(parent, **kwargs):
    evaluated = kwargs.pop("evaluated_at_utc", "2026-09-01T19:13:00Z")
    return build_recovery_decision(
        parent,
        evaluated_at_utc=evaluated,
        **kwargs,
    )


def test_manifest_core_identity():
    manifest = reliability_recovery_manifest()
    assert manifest["data_type"] == DATA_TYPE
    assert manifest["schema_version"] == 1
    assert manifest["step13c_base_main_sha"] == STEP13C_BASE_MAIN_SHA
    assert STEP13C_BASE_MAIN_SHA == "7895eb6699630025fd49698e4b7fc2d3ff013fb6"
    assert manifest["reliability_status"] == RELIABILITY_STATUS
    assert manifest["runtime_mode"] == RUNTIME_MODE == "SHADOW_ONLY"
    assert manifest["final_certification_marker"] == FINAL_CERTIFICATION_MARKER


@pytest.mark.parametrize(
    "key",
    [
        "bounded_retry_authorization_enabled",
        "exponential_cooldown_policy_enabled",
        "cooldown_capped",
        "terminal_scheduler_state_release_authorization_enabled",
        "stuck_cycle_grace_enabled",
        "stuck_cycle_restart_authorization_enabled",
        "retry_reuses_exact_cycle_identity",
        "recovery_token_hash_binding_enabled",
        "caller_owned_recovery_state_enabled",
        "process_local_duplicate_recovery_guard_available",
    ],
)
def test_manifest_enabled_reliability_contracts(key):
    assert reliability_recovery_manifest()[key] is True


@pytest.mark.parametrize(
    "key",
    [
        "cross_process_duplicate_recovery_guard_available",
        "scheduler_state_mutation_performed_by_step13c",
        "stuck_cycle_release_performed_by_step13c",
        "retry_execution_performed_by_step13c",
        "restart_execution_performed_by_step13c",
        "runtime_cycle_execution_added_by_step13c",
        "scheduler_sleep_loop_added_by_step13c",
        "background_thread_added_by_step13c",
        "background_process_added_by_step13c",
        "network_io_added_by_step13c",
        "provider_network_calls_enabled_by_step13c",
        "production_api_wiring_added_by_step13c",
        "production_runtime_wiring_added_by_step13c",
        "production_scheduler_activation_enabled",
        "production_database_writes_enabled",
        "persistence_schema_changed_by_step13c",
        "actionable_output_enabled",
        "production_provider_consensus_enabled",
        "production_provider_failover_enabled",
        "best_price_selection_enabled",
        "provider_weighting_enabled",
        "price_fabrication_allowed",
        "fallback_price_fabrication_allowed",
    ],
)
def test_manifest_forbidden_side_effects_remain_false(key):
    assert reliability_recovery_manifest()[key] is False


def test_recovery_state_round_trip():
    cycle_id = _failed()["cycle_id"]
    state = build_recovery_state(
        cycle_id=cycle_id,
        attempts_used=2,
        last_action="RETRY_SAME_CYCLE_AFTER_COOLDOWN",
        last_failure_code="PROVIDER.TIMEOUT",
        last_transition_at_utc="2026-09-01T19:13:00Z",
        last_recovery_token_sha256="a" * 64,
    )
    assert state["attempts_used"] == 2
    assert state["cycle_id"] == cycle_id
    assert len(state["recovery_state_sha256"]) == 64


@pytest.mark.parametrize("attempts", range(0, 6))
def test_recovery_state_accepts_bounded_attempt_count(attempts):
    cycle_id = _failed()["cycle_id"]
    state = build_recovery_state(cycle_id=cycle_id, attempts_used=attempts)
    assert state["attempts_used"] == attempts


@pytest.mark.parametrize("attempts", [-1, 6, 99])
def test_recovery_state_rejects_out_of_range_attempt_count(attempts):
    with pytest.raises(MLBStep13CReliabilityRecoveryError):
        build_recovery_state(cycle_id=_failed()["cycle_id"], attempts_used=attempts)


@pytest.mark.parametrize("bad", [True, False, 1.2, "1", None])
def test_recovery_state_rejects_non_integer_attempt_count(bad):
    with pytest.raises(MLBStep13CReliabilityRecoveryError):
        build_recovery_state(cycle_id=_failed()["cycle_id"], attempts_used=bad)


@pytest.mark.parametrize("bad", ["", "x", "g" * 64, "A" * 64, "0" * 63])
def test_recovery_state_rejects_bad_cycle_id(bad):
    with pytest.raises(MLBStep13CReliabilityRecoveryError):
        build_recovery_state(cycle_id=bad, attempts_used=0)


@pytest.mark.parametrize("action", RECOVERY_ACTIONS)
def test_recovery_state_accepts_all_certified_actions(action):
    state = build_recovery_state(
        cycle_id=_failed()["cycle_id"],
        attempts_used=0,
        last_action=action,
    )
    assert state["last_action"] == action


def test_completed_active_cycle_authorizes_terminal_release_only():
    decision = _decision(_completed())
    assert decision["recovery_action"] == "TERMINAL_SUCCESS_RELEASE"
    assert decision["scheduler_state_release_authorized"] is True
    assert decision["retry_authorized"] is False
    assert decision["restart_authorized"] is False
    assert decision["stuck_cycle_release_authorized"] is False
    assert decision["attempts_used_after"] == 0


@pytest.mark.parametrize(
    "code",
    [
        "PROVIDER.TIMEOUT",
        "PROVIDER.CONNECTION_ERROR",
        "PROVIDER.CONNECTIONRESET",
        "PROVIDER.CONNECTION_RESET",
        "NETWORK.TIMEOUT",
        "NETWORK.CONNECTION_ERROR",
        "NETWORK.CONNECTIONRESET",
        "NETWORK.CONNECTION_RESET",
        "TRANSPORT.TIMEOUT",
        "TRANSPORT.CONNECTION_ERROR",
        "TRANSPORT.CONNECTIONRESET",
        "TRANSPORT.CONNECTION_RESET",
    ],
)
def test_recoverable_failure_codes_authorize_bounded_retry(code):
    decision = _decision(_failed(code))
    assert decision["recoverable_failure"] is True
    assert decision["retry_authorized"] is True
    assert decision["restart_authorized"] is True
    assert decision["retry_reuses_exact_cycle_identity"] is True
    assert decision["recovery_attempt_number"] == 1
    assert decision["attempts_used_after"] == 1
    assert decision["cooldown_seconds"] == 15
    assert decision["recovery_action"] == "RETRY_SAME_CYCLE_AFTER_COOLDOWN"


@pytest.mark.parametrize(
    "code",
    [
        "MODEL.INTEGRITY",
        "SCHEDULER.INPUT",
        "PROVIDER.AUTH",
        "NETWORK.BAD_PAYLOAD",
        "TRANSPORT.HTTP_401",
        "DATABASE.ERROR",
        "RUNTIME.UNKNOWN",
        "PROVIDER.RATE_LIMIT",
    ],
)
def test_nonrecoverable_failure_codes_fail_closed(code):
    decision = _decision(_failed(code))
    assert decision["recoverable_failure"] is False
    assert decision["retry_authorized"] is False
    assert decision["restart_authorized"] is False
    assert decision["scheduler_state_release_authorized"] is True
    assert decision["recovery_action"] == "TERMINAL_FAILURE_RELEASE"
    assert decision["recovery_reason"] == "NONRECOVERABLE_FAILURE_FAIL_CLOSED"


@pytest.mark.parametrize(
    "attempts_used,expected_delay,expected_attempt,remaining",
    [
        (0, 15, 1, 2),
        (1, 30, 2, 1),
        (2, 60, 3, 0),
    ],
)
def test_exponential_cooldown_progression(attempts_used, expected_delay, expected_attempt, remaining):
    parent = _failed("PROVIDER.TIMEOUT")
    state = build_recovery_state(
        cycle_id=parent["cycle_id"],
        attempts_used=attempts_used,
    )
    decision = _decision(parent, recovery_state=state)
    assert decision["cooldown_seconds"] == expected_delay
    assert decision["recovery_attempt_number"] == expected_attempt
    assert decision["attempts_remaining_after"] == remaining


def test_cooldown_cap_is_respected():
    parent = _failed("NETWORK.TIMEOUT")
    state = build_recovery_state(cycle_id=parent["cycle_id"], attempts_used=2)
    decision = _decision(
        parent,
        recovery_state=state,
        base_cooldown_seconds=100,
        max_cooldown_seconds=120,
    )
    assert decision["cooldown_seconds"] == 120


def test_zero_cooldown_authorizes_immediate_retry():
    decision = _decision(
        _failed("TRANSPORT.TIMEOUT"),
        base_cooldown_seconds=0,
        max_cooldown_seconds=0,
    )
    assert decision["recovery_action"] == "RETRY_SAME_CYCLE_NOW"
    assert decision["cooldown_required"] is False
    assert decision["cooldown_until_utc"] is None


def test_retry_budget_exhaustion_fails_closed_and_releases_terminal_active_state():
    parent = _failed("PROVIDER.TIMEOUT")
    state = build_recovery_state(cycle_id=parent["cycle_id"], attempts_used=3)
    decision = _decision(parent, recovery_state=state)
    assert decision["retry_authorized"] is False
    assert decision["restart_authorized"] is False
    assert decision["recovery_action"] == "RECOVERY_EXHAUSTED_RELEASE"
    assert decision["scheduler_state_release_authorized"] is True
    assert decision["attempts_used_after"] == 3


def test_stuck_cycle_inside_grace_waits_without_release_or_retry():
    parent = _stuck("2026-09-01T19:12:01Z")
    decision = _decision(
        parent,
        evaluated_at_utc="2026-09-01T19:12:01Z",
        stuck_grace_seconds=30,
    )
    assert parent["cycle_age_seconds"] == 121.0
    assert decision["recovery_action"] == "WAIT_STUCK_GRACE"
    assert decision["retry_authorized"] is False
    assert decision["restart_authorized"] is False
    assert decision["stuck_cycle_release_authorized"] is False


def test_stuck_cycle_after_grace_authorizes_bounded_restart():
    parent = _stuck("2026-09-01T19:12:31Z")
    decision = _decision(parent)
    assert parent["cycle_age_seconds"] == 151.0
    assert decision["recovery_action"] == "STUCK_RESTART_AFTER_COOLDOWN"
    assert decision["retry_authorized"] is True
    assert decision["restart_authorized"] is True
    assert decision["stuck_cycle_release_authorized"] is True
    assert decision["scheduler_state_release_authorized"] is False
    assert decision["cooldown_seconds"] == 15


def test_stuck_cycle_zero_cooldown_authorizes_immediate_restart():
    decision = _decision(
        _stuck(),
        base_cooldown_seconds=0,
        max_cooldown_seconds=0,
    )
    assert decision["recovery_action"] == "STUCK_RESTART_NOW"
    assert decision["cooldown_required"] is False


def test_stuck_cycle_recovery_budget_exhausted():
    parent = _stuck()
    state = build_recovery_state(cycle_id=parent["cycle_id"], attempts_used=3)
    decision = _decision(parent, recovery_state=state)
    assert decision["recovery_action"] == "RECOVERY_EXHAUSTED_RELEASE"
    assert decision["retry_authorized"] is False
    assert decision["restart_authorized"] is False
    assert decision["stuck_cycle_release_authorized"] is True


@pytest.mark.parametrize(
    "parent_factory,expected_action",
    [
        (_ready, "NO_RECOVERY"),
        (_running, "NO_RECOVERY"),
        (_blocked, "BLOCKED_NO_RECOVERY"),
    ],
)
def test_non_failure_lifecycle_states_do_not_trigger_recovery(parent_factory, expected_action):
    parent = parent_factory()
    decision = _decision(parent)
    assert decision["recovery_action"] == expected_action
    assert decision["retry_authorized"] is False
    assert decision["restart_authorized"] is False


def test_recovery_decision_is_deterministic():
    parent = _failed("PROVIDER.TIMEOUT")
    first = _decision(parent)
    second = _decision(parent)
    assert first == second
    assert first["reliability_sha256"] == second["reliability_sha256"]
    assert first["recovery_token_sha256"] == second["recovery_token_sha256"]


def test_recovery_decision_validation_round_trip():
    decision = _decision(_failed("PROVIDER.TIMEOUT"))
    validation = validate_recovery_decision(decision)
    assert validation["recovery_decision_valid"] is True
    assert validation["failures"] == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("retry_authorized", False),
        ("restart_authorized", False),
        ("cooldown_seconds", 999),
        ("recovery_reason", "TAMPERED"),
        ("recovery_token_sha256", "0" * 64),
        ("runtime_mode", "PRODUCTION"),
        ("network_io_performed", True),
        ("production_database_writes", 1),
    ],
)
def test_recovery_decision_validation_detects_tampering(field, value):
    decision = _decision(_failed("PROVIDER.TIMEOUT"))
    tampered = deepcopy(decision)
    tampered[field] = value
    validation = validate_recovery_decision(tampered)
    assert validation["recovery_decision_valid"] is False


def test_recovery_state_hash_tampering_is_rejected():
    parent = _failed()
    state = build_recovery_state(cycle_id=parent["cycle_id"], attempts_used=1)
    tampered = deepcopy(state)
    tampered["attempts_used"] = 2
    with pytest.raises(MLBStep13CReliabilityRecoveryError):
        _decision(parent, recovery_state=tampered)


def test_recovery_state_cycle_identity_mismatch_is_rejected():
    state = build_recovery_state(cycle_id="0" * 64, attempts_used=0)
    with pytest.raises(MLBStep13CReliabilityRecoveryError):
        _decision(_failed(), recovery_state=state)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_recovery_attempts": 0},
        {"max_recovery_attempts": 6},
        {"max_recovery_attempts": True},
        {"base_cooldown_seconds": -1},
        {"base_cooldown_seconds": 301},
        {"base_cooldown_seconds": 1.5},
        {"max_cooldown_seconds": -1},
        {"max_cooldown_seconds": 901},
        {"max_cooldown_seconds": False},
        {"stuck_grace_seconds": -1},
        {"stuck_grace_seconds": 601},
        {"stuck_grace_seconds": "30"},
    ],
)
def test_invalid_policy_values_are_rejected(kwargs):
    with pytest.raises(MLBStep13CReliabilityRecoveryError):
        _decision(_failed(), **kwargs)


def test_max_cooldown_cannot_be_less_than_base():
    with pytest.raises(MLBStep13CReliabilityRecoveryError):
        _decision(
            _failed(),
            base_cooldown_seconds=30,
            max_cooldown_seconds=15,
        )


@pytest.mark.parametrize(
    "bad_time",
    [
        "2026-09-01T19:10:59Z",
        "2026-09-01 19:13:00Z",
        "2026-09-01T19:13:00+00:00",
        "not-a-time",
        "",
    ],
)
def test_bad_or_reversed_evaluation_time_is_rejected(bad_time):
    with pytest.raises(MLBStep13CReliabilityRecoveryError):
        _decision(_failed(), evaluated_at_utc=bad_time)


def test_parent_supervision_tampering_is_rejected():
    parent = _failed()
    parent["failure_code"] = "NETWORK.TIMEOUT"
    with pytest.raises(MLBStep13CReliabilityRecoveryError):
        _decision(parent)


def test_process_local_token_lease_acquire_release():
    registry = set()
    decision = _decision(_failed("PROVIDER.TIMEOUT"))
    token = acquire_process_local_recovery_token(decision, active_registry=registry)
    assert token in registry
    release_process_local_recovery_token(token, active_registry=registry)
    assert token not in registry


def test_process_local_duplicate_token_is_refused():
    registry = set()
    decision = _decision(_failed("PROVIDER.TIMEOUT"))
    token = acquire_process_local_recovery_token(decision, active_registry=registry)
    with pytest.raises(MLBStep13CDuplicateRecoveryError):
        acquire_process_local_recovery_token(decision, active_registry=registry)
    release_process_local_recovery_token(token, active_registry=registry)


@pytest.mark.parametrize("factory", [_completed, _running, _ready, _blocked])
def test_token_lease_requires_authorized_retry_or_restart(factory):
    registry = set()
    decision = _decision(factory())
    with pytest.raises(MLBStep13CReliabilityRecoveryError):
        acquire_process_local_recovery_token(decision, active_registry=registry)


@pytest.mark.parametrize("bad", ["", "x", "0" * 63, "G" * 64, None])
def test_release_rejects_invalid_token(bad):
    with pytest.raises(MLBStep13CReliabilityRecoveryError):
        release_process_local_recovery_token(bad, active_registry=set())


@pytest.mark.parametrize(
    "field,expected",
    [
        ("scheduler_state_mutated", False),
        ("stuck_cycle_released", False),
        ("retry_executed", False),
        ("restart_executed", False),
        ("runtime_cycle_executed", False),
        ("network_io_performed", False),
        ("provider_network_calls", 0),
        ("production_api_wiring", False),
        ("production_runtime_wiring", False),
        ("production_scheduler_activation", False),
        ("production_database_writes", 0),
        ("persistence_schema_changed", False),
        ("actionable_output_enabled", False),
        ("production_provider_consensus_used", False),
        ("production_provider_failover_used", False),
        ("best_price_selection_used", False),
        ("provider_weighting_used", False),
        ("price_fabrication_used", False),
        ("fallback_price_fabrication_used", False),
        ("team_name_join_used", False),
        ("player_name_join_used", False),
        ("fuzzy_matching_used", False),
        ("synthetic_game_id_used", False),
        ("shadow_output_as_model_input", False),
        ("shadow_output_as_sportsbook_input", False),
        ("live_board_as_model_input", False),
        ("live_board_as_sportsbook_input", False),
        ("persisted_snapshot_as_model_input", False),
        ("persisted_snapshot_as_sportsbook_input", False),
    ],
)
def test_every_recovery_decision_preserves_shadow_safety(field, expected):
    decision = _decision(_failed("PROVIDER.TIMEOUT"))
    assert decision[field] == expected


@pytest.mark.parametrize("attempts_used", [0, 1, 2])
@pytest.mark.parametrize(
    "code",
    [
        "PROVIDER.TIMEOUT",
        "NETWORK.CONNECTION_ERROR",
        "TRANSPORT.CONNECTION_RESET",
    ],
)
def test_next_recovery_state_advances_exactly_one_attempt(attempts_used, code):
    parent = _failed(code)
    state = build_recovery_state(cycle_id=parent["cycle_id"], attempts_used=attempts_used)
    decision = _decision(parent, recovery_state=state)
    next_state = decision["next_recovery_state"]
    assert next_state["attempts_used"] == attempts_used + 1
    assert next_state["cycle_id"] == parent["cycle_id"]
    assert next_state["last_recovery_token_sha256"] == decision["recovery_token_sha256"]
    assert next_state["last_transition_at_utc"] == decision["evaluated_at_utc"]


@pytest.mark.parametrize(
    "eval_time,expected_until",
    [
        ("2026-09-01T19:13:00Z", "2026-09-01T19:13:15Z"),
        ("2026-09-01T20:00:00Z", "2026-09-01T20:00:15Z"),
        ("2026-09-02T00:00:00Z", "2026-09-02T00:00:15Z"),
    ],
)
def test_cooldown_until_is_exact_utc(eval_time, expected_until):
    decision = _decision(
        _failed("PROVIDER.TIMEOUT"),
        evaluated_at_utc=eval_time,
    )
    assert decision["cooldown_until_utc"] == expected_until


def test_recovery_token_changes_when_prior_state_changes():
    parent = _failed()
    first = _decision(parent)
    state = build_recovery_state(cycle_id=parent["cycle_id"], attempts_used=1)
    second = _decision(parent, recovery_state=state)
    assert first["recovery_token_sha256"] != second["recovery_token_sha256"]


def test_recovery_token_changes_when_evaluation_time_changes():
    parent = _failed()
    first = _decision(parent, evaluated_at_utc="2026-09-01T19:13:00Z")
    second = _decision(parent, evaluated_at_utc="2026-09-01T19:13:01Z")
    assert first["recovery_token_sha256"] != second["recovery_token_sha256"]


def test_recovery_decision_deep_copies_parent_and_prior_state():
    parent = _failed()
    state = build_recovery_state(cycle_id=parent["cycle_id"], attempts_used=0)
    decision = _decision(parent, recovery_state=state)
    parent["failure_code"] = "MODEL.INTEGRITY"
    state["attempts_used"] = 3
    assert decision["step13b_supervision"]["failure_code"] == "PROVIDER.TIMEOUT"
    assert decision["prior_recovery_state"]["attempts_used"] == 0
