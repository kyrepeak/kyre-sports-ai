"""MLB Step 13B — deterministic shadow runtime supervisor.

Step 13A introduced a caller-owned bounded scheduler permit contract over the
frozen Step 12 runtime. Step 13B adds lifecycle supervision around those
permits. It can classify a caller-reported cycle as ready, running, completed,
failed, blocked, or potentially stuck while preserving exact Step 13A identity.

This module is deliberately observational and fail-closed. It does not execute
Step 12, sleep, retry, restart, release a stuck cycle, mutate scheduler state,
perform network I/O, write persistence, activate production scheduling, or make
any live-board row actionable. Recovery remains a later Step 13 stage.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any

from sports_api.mlb_step9_final_freeze_v1 import PROTECTED_INVARIANTS
from sports_api.mlb_step13a_bounded_scheduler_v1 import (
    FINAL_CERTIFICATION_MARKER as STEP13A_FINAL_CERTIFICATION_MARKER,
    RUNTIME_MODE as STEP13A_RUNTIME_MODE,
    SCHEDULER_STATUS as STEP13A_SCHEDULER_STATUS,
    bounded_scheduler_manifest,
    validate_bounded_scheduler_tick,
)

DATA_TYPE = "mlb_step13b_runtime_supervisor_v1"
SCHEMA_VERSION = 1
STEP13B_BASE_MAIN_SHA = "1587b4825ad5ce01c8dcd669417da6046ede6921"
SUPERVISOR_STATUS = "STEP13B_RUNTIME_SUPERVISOR_READY"
RUNTIME_MODE = "SHADOW_ONLY"
FINAL_CERTIFICATION_MARKER = "MLB_STEP13B_RUNTIME_SUPERVISOR_GREEN"

DEFAULT_MAX_CYCLE_RUNTIME_SECONDS = 120
MIN_MAX_CYCLE_RUNTIME_SECONDS = 15
MAX_MAX_CYCLE_RUNTIME_SECONDS = 3600

SUPERVISION_STATES = (
    "READY_TO_START",
    "RUNNING",
    "COMPLETED",
    "FAILED",
    "BLOCKED",
    "IDLE",
    "POTENTIALLY_STUCK",
)
TERMINAL_OUTCOMES = ("SUCCESS", "FAILURE")

_OBSERVATION_KEYS = {
    "cycle_id",
    "cycle_slot_utc",
    "started_at_utc",
    "finished_at_utc",
    "outcome",
    "failure_code",
}
_CYCLE_ID_RE = re.compile(r"^[0-9a-f]{64}$")
_FAILURE_CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9_.:-]{0,127}$")


class MLBStep13BRuntimeSupervisorError(ValueError):
    """Raised when Step 13B cannot safely classify runtime lifecycle state."""


def runtime_supervisor_manifest() -> dict[str, Any]:
    """Return the immutable Step 13B shadow supervisor boundary."""
    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "step13b_base_main_sha": STEP13B_BASE_MAIN_SHA,
        "supervisor_status": SUPERVISOR_STATUS,
        "runtime_mode": RUNTIME_MODE,
        "final_certification_marker": FINAL_CERTIFICATION_MARKER,
        "step13a_scheduler_status_required": STEP13A_SCHEDULER_STATUS,
        "step13a_runtime_mode_required": STEP13A_RUNTIME_MODE,
        "step13a_final_certification_marker_required": STEP13A_FINAL_CERTIFICATION_MARKER,
        "supervision_states": list(SUPERVISION_STATES),
        "terminal_outcomes": list(TERMINAL_OUTCOMES),
        "default_max_cycle_runtime_seconds": DEFAULT_MAX_CYCLE_RUNTIME_SECONDS,
        "minimum_max_cycle_runtime_seconds": MIN_MAX_CYCLE_RUNTIME_SECONDS,
        "maximum_max_cycle_runtime_seconds": MAX_MAX_CYCLE_RUNTIME_SECONDS,
        "exact_step13a_tick_required": True,
        "exact_cycle_id_required": True,
        "exact_cycle_slot_required": True,
        "caller_supplied_cycle_observation_required_for_active_cycle": True,
        "running_cycle_age_monitored": True,
        "potentially_stuck_detection_enabled": True,
        "terminal_success_observed": True,
        "terminal_failure_observed": True,
        "scheduler_overlap_blocking_preserved": True,
        "failure_isolation_preserved": True,
        "supervisor_is_observational_only": True,
        "scheduler_state_mutation_added_by_step13b": False,
        "stuck_cycle_release_added_by_step13b": False,
        "retry_added_by_step13b": False,
        "restart_added_by_step13b": False,
        "cooldown_added_by_step13b": False,
        "runtime_cycle_execution_added_by_step13b": False,
        "scheduler_sleep_loop_added_by_step13b": False,
        "background_thread_added_by_step13b": False,
        "background_process_added_by_step13b": False,
        "network_io_added_by_step13b": False,
        "provider_network_calls_enabled_by_step13b": False,
        "production_api_wiring_added_by_step13b": False,
        "production_runtime_wiring_added_by_step13b": False,
        "production_scheduler_activation_enabled": False,
        "production_database_writes_enabled": False,
        "persistence_schema_changed_by_step13b": False,
        "actionable_output_enabled": False,
        "production_provider_consensus_enabled": False,
        "production_provider_failover_enabled": False,
        "best_price_selection_enabled": False,
        "provider_weighting_enabled": False,
        "price_fabrication_allowed": False,
        "fallback_price_fabrication_allowed": False,
        "team_name_join_allowed": False,
        "player_name_join_allowed": False,
        "fuzzy_matching_allowed": False,
        "synthetic_game_id_allowed": False,
        "shadow_output_as_model_input_allowed": False,
        "shadow_output_as_sportsbook_input_allowed": False,
        "live_board_as_model_input_allowed": False,
        "live_board_as_sportsbook_input_allowed": False,
        "persisted_snapshot_as_model_input_allowed": False,
        "persisted_snapshot_as_sportsbook_input_allowed": False,
        "future_reliability_recovery_step_required": True,
        "future_scheduler_freeze_required": True,
        **PROTECTED_INVARIANTS,
    }


def _hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _utc_z(value: Any, field: str) -> tuple[str, datetime]:
    if (
        not isinstance(value, str)
        or not value.endswith("Z")
        or "T" not in value
        or " " in value
    ):
        raise MLBStep13BRuntimeSupervisorError(
            f"{field} must be UTC RFC3339 ending in Z"
        )
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise MLBStep13BRuntimeSupervisorError(f"{field} is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise MLBStep13BRuntimeSupervisorError(f"{field} must be UTC")
    parsed = parsed.astimezone(timezone.utc)
    return parsed.isoformat().replace("+00:00", "Z"), parsed


def _runtime_limit(value: Any) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise MLBStep13BRuntimeSupervisorError(
            "max_cycle_runtime_seconds must be an integer"
        )
    if value < MIN_MAX_CYCLE_RUNTIME_SECONDS or value > MAX_MAX_CYCLE_RUNTIME_SECONDS:
        raise MLBStep13BRuntimeSupervisorError(
            "max_cycle_runtime_seconds must be between "
            f"{MIN_MAX_CYCLE_RUNTIME_SECONDS} and {MAX_MAX_CYCLE_RUNTIME_SECONDS}"
        )
    return value


def _cycle_identity_from_tick(tick: Mapping[str, Any]) -> tuple[str | None, str | None, str]:
    state = tick.get("scheduler_state")
    if not isinstance(state, Mapping):
        raise MLBStep13BRuntimeSupervisorError("Step 13A scheduler_state missing")

    active_id = state.get("active_cycle_id")
    active_slot = state.get("active_cycle_slot_utc")
    permit_granted = tick.get("permit_granted") is True
    permit_id = tick.get("permit_cycle_id")
    permit_slot = tick.get("permit_slot_utc")

    if active_id is not None:
        return active_id, active_slot, "ACTIVE"
    if permit_granted:
        return permit_id, permit_slot, "PERMITTED"
    return None, None, "NONE"


def _normalize_observation(
    value: Mapping[str, Any] | None,
    *,
    expected_cycle_id: str | None,
    expected_slot_utc: str | None,
    observed_at_dt: datetime,
) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise MLBStep13BRuntimeSupervisorError(
            "cycle_observation must be a mapping or None"
        )
    unknown = set(value) - _OBSERVATION_KEYS
    if unknown:
        raise MLBStep13BRuntimeSupervisorError(
            f"cycle_observation has unsupported keys: {sorted(unknown)!r}"
        )
    if expected_cycle_id is None or expected_slot_utc is None:
        raise MLBStep13BRuntimeSupervisorError(
            "cycle_observation is forbidden when the scheduler tick has no cycle identity"
        )

    cycle_id = value.get("cycle_id")
    if not isinstance(cycle_id, str) or _CYCLE_ID_RE.fullmatch(cycle_id) is None:
        raise MLBStep13BRuntimeSupervisorError(
            "cycle_observation.cycle_id must be lowercase 64-character SHA-256 hex"
        )
    if cycle_id != expected_cycle_id:
        raise MLBStep13BRuntimeSupervisorError(
            "cycle_observation.cycle_id does not match Step 13A cycle identity"
        )

    slot, _ = _utc_z(value.get("cycle_slot_utc"), "cycle_observation.cycle_slot_utc")
    if slot != expected_slot_utc:
        raise MLBStep13BRuntimeSupervisorError(
            "cycle_observation.cycle_slot_utc does not match Step 13A cycle slot"
        )

    started, started_dt = _utc_z(
        value.get("started_at_utc"), "cycle_observation.started_at_utc"
    )
    if started_dt > observed_at_dt:
        raise MLBStep13BRuntimeSupervisorError(
            "cycle_observation.started_at_utc cannot be after observed_at_utc"
        )

    finished_raw = value.get("finished_at_utc")
    finished: str | None = None
    finished_dt: datetime | None = None
    if finished_raw is not None:
        finished, finished_dt = _utc_z(
            finished_raw, "cycle_observation.finished_at_utc"
        )
        if finished_dt < started_dt:
            raise MLBStep13BRuntimeSupervisorError(
                "cycle_observation.finished_at_utc cannot be before started_at_utc"
            )
        if finished_dt > observed_at_dt:
            raise MLBStep13BRuntimeSupervisorError(
                "cycle_observation.finished_at_utc cannot be after observed_at_utc"
            )

    outcome_raw = value.get("outcome")
    outcome: str | None
    if outcome_raw is None:
        outcome = None
    elif isinstance(outcome_raw, str):
        outcome = outcome_raw.strip().upper()
    else:
        raise MLBStep13BRuntimeSupervisorError(
            "cycle_observation.outcome must be SUCCESS, FAILURE, or None"
        )
    if outcome is not None and outcome not in TERMINAL_OUTCOMES:
        raise MLBStep13BRuntimeSupervisorError(
            "cycle_observation.outcome must be SUCCESS, FAILURE, or None"
        )
    if finished is None and outcome is not None:
        raise MLBStep13BRuntimeSupervisorError(
            "cycle_observation.outcome requires finished_at_utc"
        )
    if finished is not None and outcome is None:
        raise MLBStep13BRuntimeSupervisorError(
            "finished cycle_observation requires terminal outcome"
        )

    failure_code_raw = value.get("failure_code")
    failure_code: str | None = None
    if failure_code_raw is not None:
        if not isinstance(failure_code_raw, str):
            raise MLBStep13BRuntimeSupervisorError(
                "cycle_observation.failure_code must be a string or None"
            )
        failure_code = failure_code_raw.strip().upper()
        if _FAILURE_CODE_RE.fullmatch(failure_code) is None:
            raise MLBStep13BRuntimeSupervisorError(
                "cycle_observation.failure_code has invalid format"
            )
    if outcome == "FAILURE" and failure_code is None:
        raise MLBStep13BRuntimeSupervisorError(
            "FAILURE outcome requires failure_code"
        )
    if outcome != "FAILURE" and failure_code is not None:
        raise MLBStep13BRuntimeSupervisorError(
            "failure_code is allowed only with FAILURE outcome"
        )

    return {
        "cycle_id": cycle_id,
        "cycle_slot_utc": slot,
        "started_at_utc": started,
        "finished_at_utc": finished,
        "outcome": outcome,
        "failure_code": failure_code,
    }


def build_runtime_supervision(
    scheduler_tick: Mapping[str, Any],
    *,
    observed_at_utc: str,
    cycle_observation: Mapping[str, Any] | None,
    step13a_manifest: Mapping[str, Any],
    max_cycle_runtime_seconds: int = DEFAULT_MAX_CYCLE_RUNTIME_SECONDS,
) -> dict[str, Any]:
    """Classify one Step 13A cycle lifecycle without mutating or recovering it."""
    if not isinstance(step13a_manifest, Mapping):
        raise MLBStep13BRuntimeSupervisorError("step13a_manifest must be a mapping")
    if dict(step13a_manifest) != bounded_scheduler_manifest():
        raise MLBStep13BRuntimeSupervisorError("Step 13A bounded scheduler manifest mismatch")
    if not isinstance(scheduler_tick, Mapping):
        raise MLBStep13BRuntimeSupervisorError("scheduler_tick must be a mapping")
    tick_validation = validate_bounded_scheduler_tick(scheduler_tick)
    if tick_validation.get("tick_valid") is not True:
        raise MLBStep13BRuntimeSupervisorError(
            f"Step 13A scheduler tick validation failed: {tick_validation.get('failures')}"
        )

    observed, observed_dt = _utc_z(observed_at_utc, "observed_at_utc")
    limit = _runtime_limit(max_cycle_runtime_seconds)
    tick_evaluated, tick_evaluated_dt = _utc_z(
        scheduler_tick.get("evaluated_at_utc"), "scheduler_tick.evaluated_at_utc"
    )
    if observed_dt < tick_evaluated_dt:
        raise MLBStep13BRuntimeSupervisorError(
            "observed_at_utc cannot be before scheduler_tick.evaluated_at_utc"
        )

    expected_cycle_id, expected_slot, identity_source = _cycle_identity_from_tick(
        scheduler_tick
    )
    observation = _normalize_observation(
        deepcopy(cycle_observation),
        expected_cycle_id=expected_cycle_id,
        expected_slot_utc=expected_slot,
        observed_at_dt=observed_dt,
    )

    scheduler_reason = scheduler_tick.get("decision_reason")
    overlap_blocked = scheduler_reason == "ACTIVE_CYCLE_OVERLAP_BLOCKED"
    cycle_age_seconds: float | None = None
    runtime_over_limit = False
    state: str
    terminal = False
    success = False
    failure = False

    if expected_cycle_id is None:
        if observation is not None:
            raise MLBStep13BRuntimeSupervisorError(
                "cycle observation cannot exist without Step 13A cycle identity"
            )
        if scheduler_reason == "SCHEDULER_DISABLED":
            state = "BLOCKED"
        else:
            state = "IDLE"
    elif observation is None:
        if identity_source == "ACTIVE":
            raise MLBStep13BRuntimeSupervisorError(
                "active Step 13A cycle requires caller-supplied cycle_observation"
            )
        state = "READY_TO_START"
    else:
        _, started_dt = _utc_z(
            observation["started_at_utc"], "cycle_observation.started_at_utc"
        )
        end_dt = observed_dt
        if observation["finished_at_utc"] is not None:
            _, end_dt = _utc_z(
                observation["finished_at_utc"], "cycle_observation.finished_at_utc"
            )
        cycle_age_seconds = (end_dt - started_dt).total_seconds()
        runtime_over_limit = (
            observation["finished_at_utc"] is None
            and cycle_age_seconds > float(limit)
        )

        if observation["finished_at_utc"] is None:
            state = "POTENTIALLY_STUCK" if runtime_over_limit else "RUNNING"
        elif observation["outcome"] == "SUCCESS":
            state = "COMPLETED"
            terminal = True
            success = True
        elif observation["outcome"] == "FAILURE":
            state = "FAILED"
            terminal = True
            failure = True
        else:
            raise MLBStep13BRuntimeSupervisorError(
                "terminal cycle observation has unsupported outcome"
            )

    scheduler_state_release_candidate = terminal and identity_source == "ACTIVE"
    result: dict[str, Any] = {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "supervisor_status": SUPERVISOR_STATUS,
        "runtime_mode": RUNTIME_MODE,
        "step13a_scheduler_status": STEP13A_SCHEDULER_STATUS,
        "step13a_runtime_mode": STEP13A_RUNTIME_MODE,
        "step13a_final_certification_marker": STEP13A_FINAL_CERTIFICATION_MARKER,
        "observed_at_utc": observed,
        "scheduler_tick_evaluated_at_utc": tick_evaluated,
        "max_cycle_runtime_seconds": limit,
        "scheduler_tick": deepcopy(dict(scheduler_tick)),
        "cycle_identity_source": identity_source,
        "cycle_id": expected_cycle_id,
        "cycle_slot_utc": expected_slot,
        "cycle_observation": observation,
        "supervision_state": state,
        "cycle_age_seconds": cycle_age_seconds,
        "runtime_over_limit": runtime_over_limit,
        "potentially_stuck": state == "POTENTIALLY_STUCK",
        "terminal": terminal,
        "success_observed": success,
        "failure_observed": failure,
        "failure_code": None if observation is None else observation["failure_code"],
        "scheduler_overlap_blocked": overlap_blocked,
        "scheduler_state_release_candidate": scheduler_state_release_candidate,
        "scheduler_state_mutated": False,
        "stuck_cycle_released": False,
        "retry_authorized": False,
        "restart_authorized": False,
        "cooldown_applied": False,
        "runtime_cycle_executed": False,
        "network_io_performed": False,
        "provider_network_calls": 0,
        "production_api_wiring": False,
        "production_runtime_wiring": False,
        "production_scheduler_activation": False,
        "production_database_writes": 0,
        "actionable_output_enabled": False,
        "production_provider_consensus_used": False,
        "production_provider_failover_used": False,
        "best_price_selection_used": False,
        "provider_weighting_used": False,
        "price_fabrication_used": False,
        "fallback_price_fabrication_used": False,
        "team_name_join_used": False,
        "player_name_join_used": False,
        "fuzzy_matching_used": False,
        "synthetic_game_id_used": False,
        "shadow_output_as_model_input": False,
        "shadow_output_as_sportsbook_input": False,
        "live_board_as_model_input": False,
        "live_board_as_sportsbook_input": False,
        "persisted_snapshot_as_model_input": False,
        "persisted_snapshot_as_sportsbook_input": False,
    }
    result["supervision_sha256"] = _hash(result)
    return result


def validate_runtime_supervision(
    supervision: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Rebuild and exact-compare a Step 13B supervision record."""
    if not isinstance(supervision, Mapping):
        return {
            "data_type": DATA_TYPE,
            "schema_version": SCHEMA_VERSION,
            "supervision_valid": False,
            "failures": ["STEP13B_SUPERVISION_NOT_MAPPING"],
        }

    failures: list[str] = []
    try:
        rebuilt = build_runtime_supervision(
            supervision.get("scheduler_tick"),
            observed_at_utc=supervision.get("observed_at_utc"),
            cycle_observation=supervision.get("cycle_observation"),
            step13a_manifest=bounded_scheduler_manifest(),
            max_cycle_runtime_seconds=supervision.get("max_cycle_runtime_seconds"),
        )
    except Exception as exc:
        failures.append(f"STEP13B_REBUILD_FAILED:{type(exc).__name__}:{exc}")
    else:
        if dict(supervision) != rebuilt:
            failures.append("STEP13B_SUPERVISION_EXACT_CONTRACT_MISMATCH")

    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "supervision_valid": not failures,
        "failures": failures,
    }


__all__ = [
    "DATA_TYPE",
    "SCHEMA_VERSION",
    "STEP13B_BASE_MAIN_SHA",
    "SUPERVISOR_STATUS",
    "RUNTIME_MODE",
    "FINAL_CERTIFICATION_MARKER",
    "DEFAULT_MAX_CYCLE_RUNTIME_SECONDS",
    "MIN_MAX_CYCLE_RUNTIME_SECONDS",
    "MAX_MAX_CYCLE_RUNTIME_SECONDS",
    "SUPERVISION_STATES",
    "TERMINAL_OUTCOMES",
    "MLBStep13BRuntimeSupervisorError",
    "runtime_supervisor_manifest",
    "build_runtime_supervision",
    "validate_runtime_supervision",
]
