"""MLB Step 13A — bounded shadow scheduler.

Step 12 froze the complete MLB live runtime chain in ``SHADOW_ONLY`` mode.
Step 13A adds the first reliability layer around that frozen runtime: a pure,
deterministic scheduler decision that can grant at most one shadow-cycle permit
for the current fixed-cadence slot.

This module deliberately does not sleep, spawn threads, create background jobs,
perform network I/O, call providers, write persistence, wire a production
runtime, or make any Step 12 live-board row actionable. Scheduler state remains
caller-owned. An active cycle always blocks a new permit; stale-cycle recovery
belongs to a later Step 13 reliability stage.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import re
from typing import Any

from sports_api.mlb_step9_final_freeze_v1 import PROTECTED_INVARIANTS
from sports_api.mlb_step12_final_runtime_freeze_v1 import (
    FINAL_CERTIFICATION_MARKER as STEP12_FINAL_CERTIFICATION_MARKER,
    FINAL_FREEZE_STATUS as STEP12_FINAL_FREEZE_STATUS,
    FUTURE_RUNTIME_ACTIVATION_REQUIREMENTS,
    RUNTIME_MODE as STEP12_RUNTIME_MODE,
    final_runtime_freeze_manifest,
)

DATA_TYPE = "mlb_step13a_bounded_scheduler_v1"
SCHEMA_VERSION = 1
STEP13A_BASE_MAIN_SHA = "6f67626c064facf3402c8fdcb66b00832bdb47d1"
SCHEDULER_STATUS = "STEP13A_BOUNDED_SCHEDULER_READY"
RUNTIME_MODE = "SHADOW_ONLY"
FINAL_CERTIFICATION_MARKER = "MLB_STEP13A_BOUNDED_SCHEDULER_GREEN"

DEFAULT_INTERVAL_SECONDS = 30
MIN_INTERVAL_SECONDS = 15
MAX_INTERVAL_SECONDS = 300
MAX_PERMITS_PER_TICK = 1

_STATE_KEYS = {
    "last_granted_slot_utc",
    "active_cycle_id",
    "active_cycle_slot_utc",
}
_CYCLE_ID_RE = re.compile(r"^[0-9a-f]{64}$")


class MLBStep13ABoundedSchedulerError(ValueError):
    """Raised when Step 13A cannot make a safe scheduler decision."""


def bounded_scheduler_manifest() -> dict[str, Any]:
    """Return the immutable Step 13A scheduler boundary."""
    requirements = tuple(FUTURE_RUNTIME_ACTIVATION_REQUIREMENTS)
    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "step13a_base_main_sha": STEP13A_BASE_MAIN_SHA,
        "scheduler_status": SCHEDULER_STATUS,
        "runtime_mode": RUNTIME_MODE,
        "final_certification_marker": FINAL_CERTIFICATION_MARKER,
        "step12_final_freeze_status_required": STEP12_FINAL_FREEZE_STATUS,
        "step12_final_runtime_mode_required": STEP12_RUNTIME_MODE,
        "step12_final_certification_marker_required": STEP12_FINAL_CERTIFICATION_MARKER,
        "bounded_scheduler_requirement_present": (
            "bounded_scheduler_or_supervisor_required_before_always_on_runtime"
            in requirements
        ),
        "default_interval_seconds": DEFAULT_INTERVAL_SECONDS,
        "minimum_interval_seconds": MIN_INTERVAL_SECONDS,
        "maximum_interval_seconds": MAX_INTERVAL_SECONDS,
        "maximum_permits_per_tick": MAX_PERMITS_PER_TICK,
        "fixed_cadence_required": True,
        "utc_anchor_required": True,
        "caller_owned_scheduler_state_required": True,
        "at_most_one_permit_per_tick": True,
        "duplicate_slot_permits_forbidden": True,
        "overlapping_cycles_forbidden": True,
        "active_cycle_blocks_new_permit": True,
        "catch_up_bursts_forbidden": True,
        "missed_slots_are_not_replayed": True,
        "stale_active_cycle_recovery_added_by_step13a": False,
        "scheduler_sleep_loop_added_by_step13a": False,
        "background_thread_added_by_step13a": False,
        "background_process_added_by_step13a": False,
        "network_io_added_by_step13a": False,
        "provider_network_calls_enabled_by_step13a": False,
        "production_api_wiring_added_by_step13a": False,
        "production_runtime_wiring_added_by_step13a": False,
        "production_scheduler_activation_enabled": False,
        "production_database_writes_enabled": False,
        "persistence_schema_changed_by_step13a": False,
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
        "future_runtime_supervisor_required": True,
        "future_reliability_recovery_step_required": True,
        "future_scheduler_freeze_required": True,
        **PROTECTED_INVARIANTS,
    }


def _hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _utc_z(value: Any, field: str, *, whole_second: bool = False) -> tuple[str, datetime]:
    if (
        not isinstance(value, str)
        or not value.endswith("Z")
        or "T" not in value
        or " " in value
    ):
        raise MLBStep13ABoundedSchedulerError(
            f"{field} must be UTC RFC3339 ending in Z"
        )
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise MLBStep13ABoundedSchedulerError(f"{field} is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise MLBStep13ABoundedSchedulerError(f"{field} must be UTC")
    parsed = parsed.astimezone(timezone.utc)
    if whole_second and parsed.microsecond != 0:
        raise MLBStep13ABoundedSchedulerError(f"{field} must use whole-second precision")
    return parsed.isoformat().replace("+00:00", "Z"), parsed


def _interval_seconds(value: Any) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise MLBStep13ABoundedSchedulerError("interval_seconds must be an integer")
    if value < MIN_INTERVAL_SECONDS or value > MAX_INTERVAL_SECONDS:
        raise MLBStep13ABoundedSchedulerError(
            f"interval_seconds must be between {MIN_INTERVAL_SECONDS} and "
            f"{MAX_INTERVAL_SECONDS}"
        )
    return value


def _slot_distance(anchor_dt: datetime, slot_dt: datetime, interval_seconds: int) -> int:
    delta_us = int((slot_dt - anchor_dt).total_seconds() * 1_000_000)
    interval_us = interval_seconds * 1_000_000
    if delta_us < 0 or delta_us % interval_us != 0:
        raise MLBStep13ABoundedSchedulerError(
            "scheduler state slot is not aligned to scheduler_anchor_utc cadence"
        )
    return delta_us // interval_us


def _cycle_id(
    *,
    scheduler_anchor_utc: str,
    interval_seconds: int,
    slot_utc: str,
) -> str:
    return _hash(
        {
            "step12_final_certification_marker": STEP12_FINAL_CERTIFICATION_MARKER,
            "scheduler_anchor_utc": scheduler_anchor_utc,
            "interval_seconds": interval_seconds,
            "slot_utc": slot_utc,
            "runtime_mode": RUNTIME_MODE,
        }
    )


def _normalize_state(
    value: Mapping[str, Any] | None,
    *,
    scheduler_anchor_utc: str,
    anchor_dt: datetime,
    interval_seconds: int,
) -> dict[str, Any]:
    if value is None:
        value = {}
    if not isinstance(value, Mapping):
        raise MLBStep13ABoundedSchedulerError("scheduler_state must be a mapping or None")
    unknown = set(value) - _STATE_KEYS
    if unknown:
        raise MLBStep13ABoundedSchedulerError(
            f"scheduler_state has unsupported keys: {sorted(unknown)!r}"
        )

    last_slot_raw = value.get("last_granted_slot_utc")
    active_id = value.get("active_cycle_id")
    active_slot_raw = value.get("active_cycle_slot_utc")

    last_slot: str | None = None
    last_slot_dt: datetime | None = None
    if last_slot_raw is not None:
        last_slot, last_slot_dt = _utc_z(
            last_slot_raw,
            "scheduler_state.last_granted_slot_utc",
            whole_second=True,
        )
        _slot_distance(anchor_dt, last_slot_dt, interval_seconds)

    active_slot: str | None = None
    active_slot_dt: datetime | None = None
    if active_slot_raw is not None:
        active_slot, active_slot_dt = _utc_z(
            active_slot_raw,
            "scheduler_state.active_cycle_slot_utc",
            whole_second=True,
        )
        _slot_distance(anchor_dt, active_slot_dt, interval_seconds)

    if active_id is None and active_slot is not None:
        raise MLBStep13ABoundedSchedulerError(
            "active_cycle_slot_utc requires active_cycle_id"
        )
    if active_id is not None and active_slot is None:
        raise MLBStep13ABoundedSchedulerError(
            "active_cycle_id requires active_cycle_slot_utc"
        )
    if active_id is not None:
        if not isinstance(active_id, str) or _CYCLE_ID_RE.fullmatch(active_id) is None:
            raise MLBStep13ABoundedSchedulerError(
                "active_cycle_id must be a lowercase 64-character SHA-256 hex string"
            )
        expected_active_id = _cycle_id(
            scheduler_anchor_utc=scheduler_anchor_utc,
            interval_seconds=interval_seconds,
            slot_utc=active_slot,
        )
        if active_id != expected_active_id:
            raise MLBStep13ABoundedSchedulerError(
                "active_cycle_id does not match the deterministic active slot id"
            )
        if last_slot is None:
            raise MLBStep13ABoundedSchedulerError(
                "active cycle requires last_granted_slot_utc"
            )
        if active_slot != last_slot:
            raise MLBStep13ABoundedSchedulerError(
                "active_cycle_slot_utc must equal last_granted_slot_utc"
            )

    return {
        "last_granted_slot_utc": last_slot,
        "active_cycle_id": active_id,
        "active_cycle_slot_utc": active_slot,
    }


def build_bounded_scheduler_tick(
    *,
    evaluated_at_utc: str,
    scheduler_anchor_utc: str,
    scheduler_state: Mapping[str, Any] | None,
    step12_final_manifest: Mapping[str, Any],
    scheduler_enabled: bool = False,
    interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
) -> dict[str, Any]:
    """Return one deterministic, fail-closed scheduler decision.

    A granted permit authorizes only one caller-managed Step 12 shadow cycle for
    the current cadence slot. This function never executes that cycle itself.
    """
    if not isinstance(step12_final_manifest, Mapping):
        raise MLBStep13ABoundedSchedulerError("step12_final_manifest must be a mapping")
    if dict(step12_final_manifest) != final_runtime_freeze_manifest():
        raise MLBStep13ABoundedSchedulerError("Step 12 final runtime freeze manifest mismatch")
    if scheduler_enabled is not True and scheduler_enabled is not False:
        raise MLBStep13ABoundedSchedulerError("scheduler_enabled must be a boolean")

    interval = _interval_seconds(interval_seconds)
    evaluated, evaluated_dt = _utc_z(evaluated_at_utc, "evaluated_at_utc")
    anchor, anchor_dt = _utc_z(
        scheduler_anchor_utc,
        "scheduler_anchor_utc",
        whole_second=True,
    )
    if anchor_dt > evaluated_dt:
        raise MLBStep13ABoundedSchedulerError(
            "scheduler_anchor_utc cannot be after evaluated_at_utc"
        )

    state = _normalize_state(
        deepcopy(scheduler_state),
        scheduler_anchor_utc=anchor,
        anchor_dt=anchor_dt,
        interval_seconds=interval,
    )

    delta_us = int((evaluated_dt - anchor_dt).total_seconds() * 1_000_000)
    interval_us = interval * 1_000_000
    current_slot_index = delta_us // interval_us
    current_slot_dt = anchor_dt + timedelta(seconds=current_slot_index * interval)
    current_slot = current_slot_dt.isoformat().replace("+00:00", "Z")
    next_slot = (current_slot_dt + timedelta(seconds=interval)).isoformat().replace(
        "+00:00", "Z"
    )

    last_slot = state["last_granted_slot_utc"]
    last_slot_index: int | None = None
    if last_slot is not None:
        _, last_slot_dt = _utc_z(
            last_slot,
            "scheduler_state.last_granted_slot_utc",
            whole_second=True,
        )
        last_slot_index = _slot_distance(anchor_dt, last_slot_dt, interval)
        if last_slot_index > current_slot_index:
            raise MLBStep13ABoundedSchedulerError(
                "scheduler state is ahead of the current cadence slot"
            )

    active_cycle_id = state["active_cycle_id"]
    active_cycle_slot = state["active_cycle_slot_utc"]
    active_cycle_age_slots: int | None = None
    if active_cycle_slot is not None:
        _, active_slot_dt = _utc_z(
            active_cycle_slot,
            "scheduler_state.active_cycle_slot_utc",
            whole_second=True,
        )
        active_slot_index = _slot_distance(anchor_dt, active_slot_dt, interval)
        if active_slot_index > current_slot_index:
            raise MLBStep13ABoundedSchedulerError(
                "active cycle slot is ahead of the current cadence slot"
            )
        active_cycle_age_slots = current_slot_index - active_slot_index

    missed_slot_count = 0
    if last_slot_index is not None and current_slot_index > last_slot_index + 1:
        missed_slot_count = current_slot_index - last_slot_index - 1

    permit_granted = False
    decision_reason: str
    if scheduler_enabled is False:
        decision_reason = "SCHEDULER_DISABLED"
    elif active_cycle_id is not None:
        decision_reason = "ACTIVE_CYCLE_OVERLAP_BLOCKED"
    elif last_slot_index == current_slot_index:
        decision_reason = "CURRENT_SLOT_ALREADY_GRANTED"
    else:
        permit_granted = True
        decision_reason = (
            "FIRST_CURRENT_SLOT_ELIGIBLE"
            if last_slot_index is None
            else "CURRENT_SLOT_ELIGIBLE"
        )

    permit_cycle_id = (
        _cycle_id(
            scheduler_anchor_utc=anchor,
            interval_seconds=interval,
            slot_utc=current_slot,
        )
        if permit_granted
        else None
    )

    result: dict[str, Any] = {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "scheduler_status": SCHEDULER_STATUS,
        "runtime_mode": RUNTIME_MODE,
        "step12_final_freeze_status": STEP12_FINAL_FREEZE_STATUS,
        "step12_final_runtime_mode": STEP12_RUNTIME_MODE,
        "step12_final_certification_marker": STEP12_FINAL_CERTIFICATION_MARKER,
        "scheduler_enabled": scheduler_enabled,
        "interval_seconds": interval,
        "scheduler_anchor_utc": anchor,
        "evaluated_at_utc": evaluated,
        "current_slot_index": current_slot_index,
        "current_slot_utc": current_slot,
        "next_slot_utc": next_slot,
        "scheduler_state": state,
        "missed_slot_count": missed_slot_count,
        "missed_slots_replayed": 0,
        "catch_up_cycles_granted": 0,
        "active_cycle_age_slots": active_cycle_age_slots,
        "overlap_blocked": active_cycle_id is not None,
        "decision_reason": decision_reason,
        "permit_granted": permit_granted,
        "permits_granted": 1 if permit_granted else 0,
        "permit_cycle_id": permit_cycle_id,
        "permit_slot_utc": current_slot if permit_granted else None,
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
    result["decision_sha256"] = _hash(result)
    return result


def validate_bounded_scheduler_tick(tick: Mapping[str, Any] | None) -> dict[str, Any]:
    """Rebuild and exact-compare a Step 13A scheduler decision."""
    if not isinstance(tick, Mapping):
        return {
            "data_type": DATA_TYPE,
            "schema_version": SCHEMA_VERSION,
            "tick_valid": False,
            "failures": ["STEP13A_TICK_NOT_MAPPING"],
        }

    failures: list[str] = []
    try:
        rebuilt = build_bounded_scheduler_tick(
            evaluated_at_utc=tick.get("evaluated_at_utc"),
            scheduler_anchor_utc=tick.get("scheduler_anchor_utc"),
            scheduler_state=tick.get("scheduler_state"),
            step12_final_manifest=final_runtime_freeze_manifest(),
            scheduler_enabled=tick.get("scheduler_enabled"),
            interval_seconds=tick.get("interval_seconds"),
        )
    except Exception as exc:
        failures.append(f"STEP13A_REBUILD_FAILED:{type(exc).__name__}:{exc}")
    else:
        if dict(tick) != rebuilt:
            failures.append("STEP13A_TICK_EXACT_CONTRACT_MISMATCH")

    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "tick_valid": not failures,
        "failures": failures,
    }


__all__ = [
    "DATA_TYPE",
    "SCHEMA_VERSION",
    "STEP13A_BASE_MAIN_SHA",
    "SCHEDULER_STATUS",
    "RUNTIME_MODE",
    "FINAL_CERTIFICATION_MARKER",
    "DEFAULT_INTERVAL_SECONDS",
    "MIN_INTERVAL_SECONDS",
    "MAX_INTERVAL_SECONDS",
    "MAX_PERMITS_PER_TICK",
    "MLBStep13ABoundedSchedulerError",
    "bounded_scheduler_manifest",
    "build_bounded_scheduler_tick",
    "validate_bounded_scheduler_tick",
]
