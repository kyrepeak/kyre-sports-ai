"""MLB Step 13C — bounded reliability and recovery policy over frozen Step 13B.

Step 13A owns bounded scheduling. Step 13B owns lifecycle observation. Step 13C
adds deterministic, caller-owned recovery policy: bounded retry authorization,
exponential cooldowns, terminal release authorization, and conservative stuck
cycle restart authorization.

This module never performs a provider call, sleeps, starts threads/processes,
mutates caller state in place, writes persistence, activates production, or
executes a runtime cycle. It produces a validated recovery directive and a
hash-bound next recovery state. Durable persistence and always-on activation
remain future steps.
"""
from __future__ import annotations

from collections.abc import Mapping, MutableSet
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import re
from typing import Any

from sports_api.mlb_step9_final_freeze_v1 import PROTECTED_INVARIANTS
from sports_api.mlb_step13b_runtime_supervisor_v1 import (
    FINAL_CERTIFICATION_MARKER as STEP13B_FINAL_CERTIFICATION_MARKER,
    RUNTIME_MODE as STEP13B_RUNTIME_MODE,
    SUPERVISOR_STATUS as STEP13B_SUPERVISOR_STATUS,
    runtime_supervisor_manifest,
    validate_runtime_supervision,
)

DATA_TYPE = "mlb_step13c_reliability_recovery_v1"
RECOVERY_STATE_DATA_TYPE = "mlb_step13c_recovery_state_v1"
SCHEMA_VERSION = 1
STEP13C_BASE_MAIN_SHA = "7895eb6699630025fd49698e4b7fc2d3ff013fb6"
RELIABILITY_STATUS = "STEP13C_RELIABILITY_RECOVERY_READY"
RUNTIME_MODE = "SHADOW_ONLY"
FINAL_CERTIFICATION_MARKER = "MLB_STEP13C_RELIABILITY_RECOVERY_GREEN"

DEFAULT_MAX_RECOVERY_ATTEMPTS = 3
MIN_MAX_RECOVERY_ATTEMPTS = 1
MAX_MAX_RECOVERY_ATTEMPTS = 5

DEFAULT_BASE_COOLDOWN_SECONDS = 15
MIN_BASE_COOLDOWN_SECONDS = 0
MAX_BASE_COOLDOWN_SECONDS = 300

DEFAULT_MAX_COOLDOWN_SECONDS = 120
MIN_MAX_COOLDOWN_SECONDS = 0
MAX_MAX_COOLDOWN_SECONDS = 900

DEFAULT_STUCK_GRACE_SECONDS = 30
MIN_STUCK_GRACE_SECONDS = 0
MAX_STUCK_GRACE_SECONDS = 600

RECOVERY_ACTIONS = (
    "NO_RECOVERY",
    "TERMINAL_SUCCESS_RELEASE",
    "TERMINAL_FAILURE_RELEASE",
    "RETRY_SAME_CYCLE_AFTER_COOLDOWN",
    "RETRY_SAME_CYCLE_NOW",
    "WAIT_STUCK_GRACE",
    "STUCK_RESTART_AFTER_COOLDOWN",
    "STUCK_RESTART_NOW",
    "RECOVERY_EXHAUSTED_RELEASE",
    "BLOCKED_NO_RECOVERY",
    "IDLE_NO_RECOVERY",
)

RECOVERABLE_FAILURE_PREFIXES = (
    "PROVIDER.",
    "NETWORK.",
    "TRANSPORT.",
)
RECOVERABLE_FAILURE_SUFFIXES = (
    "TIMEOUT",
    "CONNECTION_ERROR",
    "CONNECTIONRESET",
    "CONNECTION_RESET",
)

_CYCLE_ID_RE = re.compile(r"^[0-9a-f]{64}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ALLOWED_RECOVERY_STATE_KEYS = {
    "data_type",
    "schema_version",
    "cycle_id",
    "attempts_used",
    "last_action",
    "last_failure_code",
    "last_transition_at_utc",
    "last_recovery_token_sha256",
    "recovery_state_sha256",
}
_ACTIVE_RECOVERY_TOKENS: set[str] = set()


class MLBStep13CReliabilityRecoveryError(ValueError):
    """Raised when Step 13C cannot safely build or validate recovery policy."""


class MLBStep13CDuplicateRecoveryError(RuntimeError):
    """Raised when a recovery token is already active in the local process registry."""


def reliability_recovery_manifest() -> dict[str, Any]:
    """Return the immutable Step 13C shadow reliability boundary."""
    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "step13c_base_main_sha": STEP13C_BASE_MAIN_SHA,
        "reliability_status": RELIABILITY_STATUS,
        "runtime_mode": RUNTIME_MODE,
        "final_certification_marker": FINAL_CERTIFICATION_MARKER,
        "step13b_supervisor_status_required": STEP13B_SUPERVISOR_STATUS,
        "step13b_runtime_mode_required": STEP13B_RUNTIME_MODE,
        "step13b_final_certification_marker_required": STEP13B_FINAL_CERTIFICATION_MARKER,
        "default_max_recovery_attempts": DEFAULT_MAX_RECOVERY_ATTEMPTS,
        "minimum_max_recovery_attempts": MIN_MAX_RECOVERY_ATTEMPTS,
        "maximum_max_recovery_attempts": MAX_MAX_RECOVERY_ATTEMPTS,
        "default_base_cooldown_seconds": DEFAULT_BASE_COOLDOWN_SECONDS,
        "maximum_base_cooldown_seconds": MAX_BASE_COOLDOWN_SECONDS,
        "default_max_cooldown_seconds": DEFAULT_MAX_COOLDOWN_SECONDS,
        "maximum_max_cooldown_seconds": MAX_MAX_COOLDOWN_SECONDS,
        "default_stuck_grace_seconds": DEFAULT_STUCK_GRACE_SECONDS,
        "maximum_stuck_grace_seconds": MAX_STUCK_GRACE_SECONDS,
        "recovery_actions": list(RECOVERY_ACTIONS),
        "recoverable_failure_prefixes": list(RECOVERABLE_FAILURE_PREFIXES),
        "recoverable_failure_suffixes": list(RECOVERABLE_FAILURE_SUFFIXES),
        "exact_step13b_supervision_required": True,
        "bounded_retry_authorization_enabled": True,
        "exponential_cooldown_policy_enabled": True,
        "cooldown_capped": True,
        "terminal_scheduler_state_release_authorization_enabled": True,
        "stuck_cycle_grace_enabled": True,
        "stuck_cycle_restart_authorization_enabled": True,
        "retry_reuses_exact_cycle_identity": True,
        "recovery_token_hash_binding_enabled": True,
        "caller_owned_recovery_state_enabled": True,
        "process_local_duplicate_recovery_guard_available": True,
        "cross_process_duplicate_recovery_guard_available": False,
        "scheduler_state_mutation_performed_by_step13c": False,
        "stuck_cycle_release_performed_by_step13c": False,
        "retry_execution_performed_by_step13c": False,
        "restart_execution_performed_by_step13c": False,
        "runtime_cycle_execution_added_by_step13c": False,
        "scheduler_sleep_loop_added_by_step13c": False,
        "background_thread_added_by_step13c": False,
        "background_process_added_by_step13c": False,
        "network_io_added_by_step13c": False,
        "provider_network_calls_enabled_by_step13c": False,
        "production_api_wiring_added_by_step13c": False,
        "production_runtime_wiring_added_by_step13c": False,
        "production_scheduler_activation_enabled": False,
        "production_database_writes_enabled": False,
        "persistence_schema_changed_by_step13c": False,
        "actionable_output_enabled": False,
        "production_provider_consensus_enabled": False,
        "production_provider_failover_enabled": False,
        "best_price_selection_enabled": False,
        "provider_weighting_enabled": False,
        "price_fabrication_allowed": False,
        "fallback_price_fabrication_allowed": False,
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
        raise MLBStep13CReliabilityRecoveryError(
            f"{field} must be UTC RFC3339 ending in Z"
        )
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise MLBStep13CReliabilityRecoveryError(f"{field} is invalid") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise MLBStep13CReliabilityRecoveryError(f"{field} must be UTC")
    parsed = parsed.astimezone(timezone.utc)
    return parsed.isoformat().replace("+00:00", "Z"), parsed


def _strict_int(value: Any, field: str, minimum: int, maximum: int) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise MLBStep13CReliabilityRecoveryError(f"{field} must be an integer")
    if value < minimum or value > maximum:
        raise MLBStep13CReliabilityRecoveryError(
            f"{field} must be between {minimum} and {maximum}"
        )
    return value


def _recovery_policy(
    *,
    max_recovery_attempts: int,
    base_cooldown_seconds: int,
    max_cooldown_seconds: int,
    stuck_grace_seconds: int,
) -> dict[str, int]:
    attempts = _strict_int(
        max_recovery_attempts,
        "max_recovery_attempts",
        MIN_MAX_RECOVERY_ATTEMPTS,
        MAX_MAX_RECOVERY_ATTEMPTS,
    )
    base = _strict_int(
        base_cooldown_seconds,
        "base_cooldown_seconds",
        MIN_BASE_COOLDOWN_SECONDS,
        MAX_BASE_COOLDOWN_SECONDS,
    )
    cap = _strict_int(
        max_cooldown_seconds,
        "max_cooldown_seconds",
        MIN_MAX_COOLDOWN_SECONDS,
        MAX_MAX_COOLDOWN_SECONDS,
    )
    grace = _strict_int(
        stuck_grace_seconds,
        "stuck_grace_seconds",
        MIN_STUCK_GRACE_SECONDS,
        MAX_STUCK_GRACE_SECONDS,
    )
    if cap < base:
        raise MLBStep13CReliabilityRecoveryError(
            "max_cooldown_seconds cannot be less than base_cooldown_seconds"
        )
    return {
        "max_recovery_attempts": attempts,
        "base_cooldown_seconds": base,
        "max_cooldown_seconds": cap,
        "stuck_grace_seconds": grace,
    }


def _empty_recovery_state(cycle_id: str | None) -> dict[str, Any]:
    state = {
        "data_type": RECOVERY_STATE_DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "cycle_id": cycle_id,
        "attempts_used": 0,
        "last_action": None,
        "last_failure_code": None,
        "last_transition_at_utc": None,
        "last_recovery_token_sha256": None,
    }
    state["recovery_state_sha256"] = _hash(state)
    return state


def build_recovery_state(
    *,
    cycle_id: str | None,
    attempts_used: int,
    last_action: str | None = None,
    last_failure_code: str | None = None,
    last_transition_at_utc: str | None = None,
    last_recovery_token_sha256: str | None = None,
) -> dict[str, Any]:
    """Build a hash-bound caller-owned Step 13C recovery state."""
    if cycle_id is not None:
        if not isinstance(cycle_id, str) or _CYCLE_ID_RE.fullmatch(cycle_id) is None:
            raise MLBStep13CReliabilityRecoveryError(
                "cycle_id must be lowercase 64-character SHA-256 hex or None"
            )
    used = _strict_int(
        attempts_used,
        "attempts_used",
        0,
        MAX_MAX_RECOVERY_ATTEMPTS,
    )
    action = None
    if last_action is not None:
        if not isinstance(last_action, str) or last_action not in RECOVERY_ACTIONS:
            raise MLBStep13CReliabilityRecoveryError(
                "last_action must be a certified Step 13C recovery action or None"
            )
        action = last_action
    failure = None
    if last_failure_code is not None:
        if not isinstance(last_failure_code, str) or not last_failure_code.strip():
            raise MLBStep13CReliabilityRecoveryError(
                "last_failure_code must be a non-empty string or None"
            )
        failure = last_failure_code.strip().upper()
    transition = None
    if last_transition_at_utc is not None:
        transition, _ = _utc_z(
            last_transition_at_utc,
            "last_transition_at_utc",
        )
    token = None
    if last_recovery_token_sha256 is not None:
        if (
            not isinstance(last_recovery_token_sha256, str)
            or _SHA256_RE.fullmatch(last_recovery_token_sha256) is None
        ):
            raise MLBStep13CReliabilityRecoveryError(
                "last_recovery_token_sha256 must be lowercase SHA-256 hex or None"
            )
        token = last_recovery_token_sha256

    state = {
        "data_type": RECOVERY_STATE_DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "cycle_id": cycle_id,
        "attempts_used": used,
        "last_action": action,
        "last_failure_code": failure,
        "last_transition_at_utc": transition,
        "last_recovery_token_sha256": token,
    }
    state["recovery_state_sha256"] = _hash(state)
    return state


def _normalize_recovery_state(
    value: Mapping[str, Any] | None,
    *,
    expected_cycle_id: str | None,
) -> dict[str, Any]:
    if value is None:
        return _empty_recovery_state(expected_cycle_id)
    if not isinstance(value, Mapping):
        raise MLBStep13CReliabilityRecoveryError(
            "recovery_state must be a mapping or None"
        )
    unknown = set(value) - _ALLOWED_RECOVERY_STATE_KEYS
    if unknown:
        raise MLBStep13CReliabilityRecoveryError(
            f"recovery_state has unsupported keys: {sorted(unknown)!r}"
        )
    rebuilt = build_recovery_state(
        cycle_id=value.get("cycle_id"),
        attempts_used=value.get("attempts_used"),
        last_action=value.get("last_action"),
        last_failure_code=value.get("last_failure_code"),
        last_transition_at_utc=value.get("last_transition_at_utc"),
        last_recovery_token_sha256=value.get("last_recovery_token_sha256"),
    )
    if dict(value) != rebuilt:
        raise MLBStep13CReliabilityRecoveryError(
            "recovery_state exact contract or content hash mismatch"
        )
    if rebuilt["cycle_id"] != expected_cycle_id:
        raise MLBStep13CReliabilityRecoveryError(
            "recovery_state cycle_id does not match Step 13B cycle identity"
        )
    return rebuilt


def _is_recoverable_failure(code: str | None) -> bool:
    if not isinstance(code, str):
        return False
    normalized = code.strip().upper()
    if not any(normalized.startswith(prefix) for prefix in RECOVERABLE_FAILURE_PREFIXES):
        return False
    return any(normalized.endswith(suffix) for suffix in RECOVERABLE_FAILURE_SUFFIXES)


def _cooldown_seconds(policy: Mapping[str, int], attempts_used: int) -> int:
    base = policy["base_cooldown_seconds"]
    cap = policy["max_cooldown_seconds"]
    if base == 0 or cap == 0:
        return 0
    raw = float(base) * (2.0 ** attempts_used)
    if not math.isfinite(raw) or raw < 0:
        raise MLBStep13CReliabilityRecoveryError("recovery cooldown is invalid")
    return int(min(raw, float(cap)))


def _recovery_token(
    *,
    supervision_sha256: str,
    recovery_state_sha256: str,
    action: str,
    recovery_attempt_number: int | None,
    evaluated_at_utc: str,
    cooldown_until_utc: str | None,
) -> str:
    return _hash(
        {
            "data_type": "mlb_step13c_recovery_token_v1",
            "step13c_base_main_sha": STEP13C_BASE_MAIN_SHA,
            "step13b_supervision_sha256": supervision_sha256,
            "prior_recovery_state_sha256": recovery_state_sha256,
            "action": action,
            "recovery_attempt_number": recovery_attempt_number,
            "evaluated_at_utc": evaluated_at_utc,
            "cooldown_until_utc": cooldown_until_utc,
        }
    )


def build_recovery_decision(
    supervision: Mapping[str, Any],
    *,
    evaluated_at_utc: str,
    recovery_state: Mapping[str, Any] | None = None,
    max_recovery_attempts: int = DEFAULT_MAX_RECOVERY_ATTEMPTS,
    base_cooldown_seconds: int = DEFAULT_BASE_COOLDOWN_SECONDS,
    max_cooldown_seconds: int = DEFAULT_MAX_COOLDOWN_SECONDS,
    stuck_grace_seconds: int = DEFAULT_STUCK_GRACE_SECONDS,
) -> dict[str, Any]:
    """Build one deterministic Step 13C recovery directive over exact Step 13B output."""
    if not isinstance(supervision, Mapping):
        raise MLBStep13CReliabilityRecoveryError("supervision must be a mapping")
    validation = validate_runtime_supervision(supervision)
    if validation.get("supervision_valid") is not True:
        raise MLBStep13CReliabilityRecoveryError(
            f"Step 13B supervision validation failed: {validation.get('failures')}"
        )
    if runtime_supervisor_manifest()["final_certification_marker"] != STEP13B_FINAL_CERTIFICATION_MARKER:
        raise MLBStep13CReliabilityRecoveryError(
            "Step 13B final certification marker drift"
        )
    if supervision.get("runtime_mode") != RUNTIME_MODE:
        raise MLBStep13CReliabilityRecoveryError("Step 13B runtime mode drift")

    evaluated, evaluated_dt = _utc_z(evaluated_at_utc, "evaluated_at_utc")
    _, parent_observed_dt = _utc_z(
        supervision.get("observed_at_utc"),
        "supervision.observed_at_utc",
    )
    if evaluated_dt < parent_observed_dt:
        raise MLBStep13CReliabilityRecoveryError(
            "evaluated_at_utc cannot be before Step 13B observed_at_utc"
        )

    policy = _recovery_policy(
        max_recovery_attempts=max_recovery_attempts,
        base_cooldown_seconds=base_cooldown_seconds,
        max_cooldown_seconds=max_cooldown_seconds,
        stuck_grace_seconds=stuck_grace_seconds,
    )
    cycle_id = supervision.get("cycle_id")
    prior = _normalize_recovery_state(
        recovery_state,
        expected_cycle_id=cycle_id,
    )
    if prior["attempts_used"] > policy["max_recovery_attempts"]:
        raise MLBStep13CReliabilityRecoveryError(
            "recovery_state attempts_used exceeds configured max_recovery_attempts"
        )

    state = supervision.get("supervision_state")
    failure_code = supervision.get("failure_code")
    recoverable_failure = _is_recoverable_failure(failure_code)
    attempts_used = prior["attempts_used"]
    attempts_remaining_before = policy["max_recovery_attempts"] - attempts_used

    action = "NO_RECOVERY"
    reason = "NO_RECOVERY_REQUIRED"
    retry_authorized = False
    restart_authorized = False
    scheduler_state_release_authorized = False
    stuck_cycle_release_authorized = False
    cooldown_required = False
    cooldown_seconds = 0
    cooldown_until: str | None = None
    recovery_attempt_number: int | None = None
    next_attempts_used = attempts_used

    identity_source = supervision.get("cycle_identity_source")
    active_cycle = identity_source == "ACTIVE"
    terminal_release_candidate = (
        supervision.get("scheduler_state_release_candidate") is True
        and active_cycle
    )

    if state == "COMPLETED":
        action = "TERMINAL_SUCCESS_RELEASE" if terminal_release_candidate else "NO_RECOVERY"
        reason = (
            "TERMINAL_SUCCESS_ACTIVE_STATE_RELEASE_AUTHORIZED"
            if terminal_release_candidate
            else "TERMINAL_SUCCESS_NO_ACTIVE_STATE"
        )
        scheduler_state_release_authorized = terminal_release_candidate
    elif state == "FAILED":
        scheduler_state_release_authorized = terminal_release_candidate
        if recoverable_failure and attempts_used < policy["max_recovery_attempts"]:
            retry_authorized = True
            restart_authorized = True
            recovery_attempt_number = attempts_used + 1
            next_attempts_used = recovery_attempt_number
            cooldown_seconds = _cooldown_seconds(policy, attempts_used)
            cooldown_required = cooldown_seconds > 0
            if cooldown_required:
                cooldown_until = (
                    evaluated_dt + timedelta(seconds=cooldown_seconds)
                ).isoformat().replace("+00:00", "Z")
                action = "RETRY_SAME_CYCLE_AFTER_COOLDOWN"
                reason = "RECOVERABLE_FAILURE_BOUNDED_RETRY_AUTHORIZED"
            else:
                action = "RETRY_SAME_CYCLE_NOW"
                reason = "RECOVERABLE_FAILURE_ZERO_COOLDOWN_RETRY_AUTHORIZED"
        elif recoverable_failure:
            action = (
                "RECOVERY_EXHAUSTED_RELEASE"
                if terminal_release_candidate
                else "NO_RECOVERY"
            )
            reason = "RECOVERABLE_FAILURE_RETRY_BUDGET_EXHAUSTED"
        else:
            action = (
                "TERMINAL_FAILURE_RELEASE"
                if terminal_release_candidate
                else "NO_RECOVERY"
            )
            reason = "NONRECOVERABLE_FAILURE_FAIL_CLOSED"
    elif state == "POTENTIALLY_STUCK":
        cycle_age = supervision.get("cycle_age_seconds")
        max_runtime = supervision.get("max_cycle_runtime_seconds")
        if not isinstance(cycle_age, (int, float)) or isinstance(cycle_age, bool):
            raise MLBStep13CReliabilityRecoveryError(
                "POTENTIALLY_STUCK supervision requires numeric cycle_age_seconds"
            )
        if not isinstance(max_runtime, int) or isinstance(max_runtime, bool):
            raise MLBStep13CReliabilityRecoveryError(
                "POTENTIALLY_STUCK supervision requires integer max_cycle_runtime_seconds"
            )
        grace_deadline_age = float(max_runtime + policy["stuck_grace_seconds"])
        if float(cycle_age) <= grace_deadline_age:
            action = "WAIT_STUCK_GRACE"
            reason = "POTENTIALLY_STUCK_WITHIN_RECOVERY_GRACE"
        else:
            stuck_cycle_release_authorized = active_cycle
            scheduler_state_release_authorized = False
            if attempts_used < policy["max_recovery_attempts"]:
                retry_authorized = True
                restart_authorized = True
                recovery_attempt_number = attempts_used + 1
                next_attempts_used = recovery_attempt_number
                cooldown_seconds = _cooldown_seconds(policy, attempts_used)
                cooldown_required = cooldown_seconds > 0
                if cooldown_required:
                    cooldown_until = (
                        evaluated_dt + timedelta(seconds=cooldown_seconds)
                    ).isoformat().replace("+00:00", "Z")
                    action = "STUCK_RESTART_AFTER_COOLDOWN"
                    reason = "STUCK_GRACE_EXCEEDED_BOUNDED_RESTART_AUTHORIZED"
                else:
                    action = "STUCK_RESTART_NOW"
                    reason = "STUCK_GRACE_EXCEEDED_ZERO_COOLDOWN_RESTART_AUTHORIZED"
            else:
                action = "RECOVERY_EXHAUSTED_RELEASE" if active_cycle else "NO_RECOVERY"
                reason = "STUCK_RECOVERY_BUDGET_EXHAUSTED"
    elif state == "BLOCKED":
        action = "BLOCKED_NO_RECOVERY"
        reason = "SCHEDULER_BLOCKED_FAIL_CLOSED"
    elif state == "IDLE":
        action = "IDLE_NO_RECOVERY"
        reason = "SCHEDULER_IDLE"
    elif state in {"READY_TO_START", "RUNNING"}:
        action = "NO_RECOVERY"
        reason = "CYCLE_HEALTHY_OR_NOT_STARTED"
    else:
        raise MLBStep13CReliabilityRecoveryError(
            f"unsupported Step 13B supervision_state: {state!r}"
        )

    attempts_remaining_after = (
        policy["max_recovery_attempts"] - next_attempts_used
    )
    parent_sha = supervision.get("supervision_sha256")
    if not isinstance(parent_sha, str) or _SHA256_RE.fullmatch(parent_sha) is None:
        raise MLBStep13CReliabilityRecoveryError(
            "Step 13B supervision_sha256 is invalid"
        )
    token = _recovery_token(
        supervision_sha256=parent_sha,
        recovery_state_sha256=prior["recovery_state_sha256"],
        action=action,
        recovery_attempt_number=recovery_attempt_number,
        evaluated_at_utc=evaluated,
        cooldown_until_utc=cooldown_until,
    )

    next_state = build_recovery_state(
        cycle_id=cycle_id,
        attempts_used=next_attempts_used,
        last_action=action,
        last_failure_code=failure_code,
        last_transition_at_utc=evaluated,
        last_recovery_token_sha256=token,
    )

    result: dict[str, Any] = {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "reliability_status": RELIABILITY_STATUS,
        "runtime_mode": RUNTIME_MODE,
        "step13b_supervisor_status": STEP13B_SUPERVISOR_STATUS,
        "step13b_runtime_mode": STEP13B_RUNTIME_MODE,
        "step13b_final_certification_marker": STEP13B_FINAL_CERTIFICATION_MARKER,
        "evaluated_at_utc": evaluated,
        "step13b_supervision": deepcopy(dict(supervision)),
        "prior_recovery_state": deepcopy(prior),
        "recovery_policy": policy,
        "supervision_state": state,
        "cycle_id": cycle_id,
        "cycle_slot_utc": supervision.get("cycle_slot_utc"),
        "cycle_identity_source": identity_source,
        "failure_code": failure_code,
        "recoverable_failure": recoverable_failure,
        "recovery_action": action,
        "recovery_reason": reason,
        "retry_authorized": retry_authorized,
        "restart_authorized": restart_authorized,
        "retry_reuses_exact_cycle_identity": retry_authorized,
        "scheduler_state_release_authorized": scheduler_state_release_authorized,
        "stuck_cycle_release_authorized": stuck_cycle_release_authorized,
        "cooldown_required": cooldown_required,
        "cooldown_seconds": cooldown_seconds,
        "cooldown_until_utc": cooldown_until,
        "recovery_attempt_number": recovery_attempt_number,
        "attempts_used_before": attempts_used,
        "attempts_used_after": next_attempts_used,
        "attempts_remaining_before": attempts_remaining_before,
        "attempts_remaining_after": attempts_remaining_after,
        "recovery_token_sha256": token,
        "next_recovery_state": next_state,
        "scheduler_state_mutated": False,
        "stuck_cycle_released": False,
        "retry_executed": False,
        "restart_executed": False,
        "runtime_cycle_executed": False,
        "network_io_performed": False,
        "provider_network_calls": 0,
        "production_api_wiring": False,
        "production_runtime_wiring": False,
        "production_scheduler_activation": False,
        "production_database_writes": 0,
        "persistence_schema_changed": False,
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
    result["reliability_sha256"] = _hash(result)
    return result


def validate_recovery_decision(
    decision: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Rebuild and exact-compare one Step 13C recovery directive."""
    if not isinstance(decision, Mapping):
        return {
            "data_type": DATA_TYPE,
            "schema_version": SCHEMA_VERSION,
            "recovery_decision_valid": False,
            "failures": ["STEP13C_DECISION_NOT_MAPPING"],
        }

    failures: list[str] = []
    policy = decision.get("recovery_policy")
    if not isinstance(policy, Mapping):
        failures.append("STEP13C_RECOVERY_POLICY_NOT_MAPPING")
    else:
        try:
            rebuilt = build_recovery_decision(
                decision.get("step13b_supervision"),
                evaluated_at_utc=decision.get("evaluated_at_utc"),
                recovery_state=decision.get("prior_recovery_state"),
                max_recovery_attempts=policy.get("max_recovery_attempts"),
                base_cooldown_seconds=policy.get("base_cooldown_seconds"),
                max_cooldown_seconds=policy.get("max_cooldown_seconds"),
                stuck_grace_seconds=policy.get("stuck_grace_seconds"),
            )
        except Exception as exc:
            failures.append(
                f"STEP13C_REBUILD_FAILED:{type(exc).__name__}:{exc}"
            )
        else:
            if dict(decision) != rebuilt:
                failures.append("STEP13C_DECISION_EXACT_CONTRACT_MISMATCH")

    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "recovery_decision_valid": not failures,
        "failures": failures,
    }


def acquire_process_local_recovery_token(
    decision: Mapping[str, Any],
    *,
    active_registry: MutableSet[str] | None = None,
) -> str:
    """Acquire one caller-managed process-local recovery token lease."""
    validation = validate_recovery_decision(decision)
    if validation.get("recovery_decision_valid") is not True:
        raise MLBStep13CReliabilityRecoveryError(
            f"invalid recovery decision: {validation.get('failures')}"
        )
    if decision.get("retry_authorized") is not True and decision.get("restart_authorized") is not True:
        raise MLBStep13CReliabilityRecoveryError(
            "process-local recovery token may be acquired only for authorized retry/restart"
        )
    token = decision.get("recovery_token_sha256")
    if not isinstance(token, str) or _SHA256_RE.fullmatch(token) is None:
        raise MLBStep13CReliabilityRecoveryError("recovery token is invalid")
    registry = _ACTIVE_RECOVERY_TOKENS if active_registry is None else active_registry
    if token in registry:
        raise MLBStep13CDuplicateRecoveryError(
            "duplicate active Step 13C recovery token refused"
        )
    registry.add(token)
    return token


def release_process_local_recovery_token(
    token: str,
    *,
    active_registry: MutableSet[str] | None = None,
) -> None:
    """Release a previously acquired caller-managed process-local token lease."""
    if not isinstance(token, str) or _SHA256_RE.fullmatch(token) is None:
        raise MLBStep13CReliabilityRecoveryError("recovery token is invalid")
    registry = _ACTIVE_RECOVERY_TOKENS if active_registry is None else active_registry
    registry.discard(token)


__all__ = [
    "DATA_TYPE",
    "RECOVERY_STATE_DATA_TYPE",
    "SCHEMA_VERSION",
    "STEP13C_BASE_MAIN_SHA",
    "RELIABILITY_STATUS",
    "RUNTIME_MODE",
    "FINAL_CERTIFICATION_MARKER",
    "DEFAULT_MAX_RECOVERY_ATTEMPTS",
    "MIN_MAX_RECOVERY_ATTEMPTS",
    "MAX_MAX_RECOVERY_ATTEMPTS",
    "DEFAULT_BASE_COOLDOWN_SECONDS",
    "MIN_BASE_COOLDOWN_SECONDS",
    "MAX_BASE_COOLDOWN_SECONDS",
    "DEFAULT_MAX_COOLDOWN_SECONDS",
    "MIN_MAX_COOLDOWN_SECONDS",
    "MAX_MAX_COOLDOWN_SECONDS",
    "DEFAULT_STUCK_GRACE_SECONDS",
    "MIN_STUCK_GRACE_SECONDS",
    "MAX_STUCK_GRACE_SECONDS",
    "RECOVERY_ACTIONS",
    "RECOVERABLE_FAILURE_PREFIXES",
    "RECOVERABLE_FAILURE_SUFFIXES",
    "MLBStep13CReliabilityRecoveryError",
    "MLBStep13CDuplicateRecoveryError",
    "reliability_recovery_manifest",
    "build_recovery_state",
    "build_recovery_decision",
    "validate_recovery_decision",
    "acquire_process_local_recovery_token",
    "release_process_local_recovery_token",
]
