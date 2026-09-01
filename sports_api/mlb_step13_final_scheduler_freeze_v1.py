"""MLB Step 13D — final scheduler and recovery release freeze.

Steps 13A-13C established bounded cadence control, deterministic lifecycle
supervision, and bounded recovery authorization above the frozen Step 12 shadow
runtime. Step 13D adds no new runtime behavior. It freezes those three layers as
one content-addressed, non-actionable scheduler/recovery release boundary.

This module never runs a cycle, performs a retry or restart, mutates scheduler
or recovery state, sleeps, performs network I/O, writes persistence, activates
production scheduling, or makes a live-board row actionable. Any durable
recovery state or always-on activation remains a separate future step.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import hashlib
import json
from typing import Any

from sports_api.mlb_step9_final_freeze_v1 import PROTECTED_INVARIANTS
from sports_api.mlb_step12_final_runtime_freeze_v1 import (
    FINAL_CERTIFICATION_MARKER as STEP12_FINAL_CERTIFICATION_MARKER,
    FINAL_FREEZE_STATUS as STEP12_FINAL_FREEZE_STATUS,
    RUNTIME_MODE as STEP12_RUNTIME_MODE,
    final_runtime_freeze_manifest,
)
from sports_api.mlb_step13a_bounded_scheduler_v1 import (
    DEFAULT_INTERVAL_SECONDS,
    FINAL_CERTIFICATION_MARKER as STEP13A_FINAL_CERTIFICATION_MARKER,
    MAX_PERMITS_PER_TICK,
    RUNTIME_MODE as STEP13A_RUNTIME_MODE,
    SCHEDULER_STATUS as STEP13A_SCHEDULER_STATUS,
    bounded_scheduler_manifest,
)
from sports_api.mlb_step13b_runtime_supervisor_v1 import (
    DEFAULT_MAX_CYCLE_RUNTIME_SECONDS,
    FINAL_CERTIFICATION_MARKER as STEP13B_FINAL_CERTIFICATION_MARKER,
    RUNTIME_MODE as STEP13B_RUNTIME_MODE,
    SUPERVISOR_STATUS as STEP13B_SUPERVISOR_STATUS,
    runtime_supervisor_manifest,
)
from sports_api.mlb_step13c_reliability_recovery_v1 import (
    DEFAULT_BASE_COOLDOWN_SECONDS,
    DEFAULT_MAX_COOLDOWN_SECONDS,
    DEFAULT_MAX_RECOVERY_ATTEMPTS,
    DEFAULT_STUCK_GRACE_SECONDS,
    FINAL_CERTIFICATION_MARKER as STEP13C_FINAL_CERTIFICATION_MARKER,
    MAX_MAX_RECOVERY_ATTEMPTS,
    RELIABILITY_STATUS as STEP13C_RELIABILITY_STATUS,
    RUNTIME_MODE as STEP13C_RUNTIME_MODE,
    reliability_recovery_manifest,
)

DATA_TYPE = "mlb_step13_final_scheduler_freeze_v1"
CERTIFICATION_DATA_TYPE = "mlb_step13d_final_scheduler_certification_v1"
SCHEMA_VERSION = 1
STEP13D_BASE_MAIN_SHA = "73e81b5dd6edab04e4e13d654f1a2c5a8d3eabe1"
FINAL_FREEZE_STATUS = "STEP13_FROZEN_SCHEDULER_RECOVERY_COMPLETE"
RUNTIME_MODE = "SHADOW_ONLY"
FINAL_CERTIFICATION_MARKER = "MLB_STEP13D_FINAL_SCHEDULER_FREEZE_GREEN"

STEP13_STAGE_CHAIN = (
    "13A_BOUNDED_SCHEDULER",
    "13B_RUNTIME_SUPERVISOR",
    "13C_RELIABILITY_RECOVERY",
)

STEP13_CERTIFICATION_MARKERS = (
    STEP13A_FINAL_CERTIFICATION_MARKER,
    STEP13B_FINAL_CERTIFICATION_MARKER,
    STEP13C_FINAL_CERTIFICATION_MARKER,
)

# Merge boundaries at which each Step-13 parent became the mainline baseline.
STEP13_PARENT_MERGE_SHAS = {
    "step13a_merge_sha": "1587b4825ad5ce01c8dcd669417da6046ede6921",
    "step13b_merge_sha": "7895eb6699630025fd49698e4b7fc2d3ff013fb6",
    "step13c_merge_sha": STEP13D_BASE_MAIN_SHA,
}

# Exact Git blob identities at the Step-13D base. The certification workflow
# independently proves these paths resolve to these blobs before merge.
FROZEN_PARENT_SOURCE_BLOBS = {
    "step12_final_runtime_freeze_blob": "ae0555e01c9c2787511ae9b7ee85e1e1a861d781",
    "step13a_bounded_scheduler_blob": "fbb61033835afb76f5f49fa990001f8e5877a696",
    "step13b_runtime_supervisor_blob": "fe0d415f4a5e41c834735f8cc81a13cf0398f583",
    "step13c_reliability_recovery_blob": "0d78c484d2f9c6e3162f55961c43688303882643",
}

_CERTIFICATION_EVIDENCE_KEYS = (
    "step13a_scheduler_evidence_ok",
    "step13b_supervisor_evidence_ok",
    "step13c_recovery_evidence_ok",
    "bounded_recovery_limits_evidence_ok",
    "zero_parent_drift_ok",
    "zero_runtime_execution_ok",
    "zero_retry_restart_execution_ok",
    "zero_network_calls_ok",
    "zero_production_database_writes_ok",
    "zero_production_activation_ok",
    "zero_actionable_output_ok",
)


class MLBStep13DFinalSchedulerFreezeError(ValueError):
    """Raised when Step 13D cannot certify the frozen Step-13 boundary."""


def _hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _parent_manifests() -> dict[str, dict[str, Any]]:
    return {
        "step12": final_runtime_freeze_manifest(),
        "step13a": bounded_scheduler_manifest(),
        "step13b": runtime_supervisor_manifest(),
        "step13c": reliability_recovery_manifest(),
    }


def _parent_manifest_hashes() -> dict[str, str]:
    return {
        name: _hash(manifest)
        for name, manifest in _parent_manifests().items()
    }


def final_scheduler_freeze_manifest() -> dict[str, Any]:
    """Return the immutable final Step-13 scheduler/recovery release boundary."""
    manifest: dict[str, Any] = {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "step13d_base_main_sha": STEP13D_BASE_MAIN_SHA,
        "final_freeze_status": FINAL_FREEZE_STATUS,
        "runtime_mode": RUNTIME_MODE,
        "final_certification_marker": FINAL_CERTIFICATION_MARKER,
        "step12_final_freeze_status_required": STEP12_FINAL_FREEZE_STATUS,
        "step12_runtime_mode_required": STEP12_RUNTIME_MODE,
        "step12_final_certification_marker_required": STEP12_FINAL_CERTIFICATION_MARKER,
        "step13a_scheduler_status_required": STEP13A_SCHEDULER_STATUS,
        "step13a_runtime_mode_required": STEP13A_RUNTIME_MODE,
        "step13a_final_certification_marker_required": STEP13A_FINAL_CERTIFICATION_MARKER,
        "step13b_supervisor_status_required": STEP13B_SUPERVISOR_STATUS,
        "step13b_runtime_mode_required": STEP13B_RUNTIME_MODE,
        "step13b_final_certification_marker_required": STEP13B_FINAL_CERTIFICATION_MARKER,
        "step13c_reliability_status_required": STEP13C_RELIABILITY_STATUS,
        "step13c_runtime_mode_required": STEP13C_RUNTIME_MODE,
        "step13c_final_certification_marker_required": STEP13C_FINAL_CERTIFICATION_MARKER,
        "step13_stage_chain": list(STEP13_STAGE_CHAIN),
        "step13_certification_markers": list(STEP13_CERTIFICATION_MARKERS),
        "step13_parent_merge_shas": deepcopy(STEP13_PARENT_MERGE_SHAS),
        "frozen_parent_source_blobs": deepcopy(FROZEN_PARENT_SOURCE_BLOBS),
        "parent_manifest_sha256": _parent_manifest_hashes(),
        "step13_scheduler_recovery_block_frozen": True,
        "step13a_bounded_scheduler_frozen": True,
        "step13b_runtime_supervisor_frozen": True,
        "step13c_reliability_recovery_frozen": True,
        "step13c_future_scheduler_freeze_requirement_satisfied": True,
        "exact_parent_manifests_required": True,
        "exact_parent_source_blobs_required": True,
        "fixed_cadence_certified": True,
        "overlap_prevention_certified": True,
        "lifecycle_supervision_certified": True,
        "failure_isolation_certified": True,
        "bounded_retry_authorization_certified": True,
        "exponential_cooldown_certified": True,
        "stuck_cycle_grace_certified": True,
        "stuck_cycle_restart_authorization_certified": True,
        "process_local_duplicate_recovery_guard_certified": True,
        "terminal_release_authorization_certified": True,
        "default_scheduler_interval_seconds": DEFAULT_INTERVAL_SECONDS,
        "maximum_permits_per_tick": MAX_PERMITS_PER_TICK,
        "default_max_cycle_runtime_seconds": DEFAULT_MAX_CYCLE_RUNTIME_SECONDS,
        "default_max_recovery_attempts": DEFAULT_MAX_RECOVERY_ATTEMPTS,
        "maximum_max_recovery_attempts": MAX_MAX_RECOVERY_ATTEMPTS,
        "default_base_cooldown_seconds": DEFAULT_BASE_COOLDOWN_SECONDS,
        "default_max_cooldown_seconds": DEFAULT_MAX_COOLDOWN_SECONDS,
        "default_stuck_grace_seconds": DEFAULT_STUCK_GRACE_SECONDS,
        "observational_and_authorization_only": True,
        "scheduler_state_mutation_added_by_step13d": False,
        "recovery_state_mutation_added_by_step13d": False,
        "stuck_cycle_release_performed_by_step13d": False,
        "retry_execution_performed_by_step13d": False,
        "restart_execution_performed_by_step13d": False,
        "runtime_cycle_execution_added_by_step13d": False,
        "scheduler_sleep_loop_added_by_step13d": False,
        "background_thread_added_by_step13d": False,
        "background_process_added_by_step13d": False,
        "network_io_added_by_step13d": False,
        "provider_network_calls_enabled_by_step13d": False,
        "production_api_wiring_added_by_step13d": False,
        "production_runtime_wiring_added_by_step13d": False,
        "production_scheduler_activation_enabled": False,
        "production_database_writes_enabled": False,
        "persistence_schema_changed_by_step13d": False,
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
        "durable_cross_process_recovery_added_by_step13d": False,
        "always_on_runtime_added_by_step13d": False,
        "future_durable_recovery_persistence_step_required": True,
        "future_explicit_activation_step_required": True,
        **PROTECTED_INVARIANTS,
    }
    manifest["freeze_manifest_sha256"] = _hash(manifest)
    return manifest


def _exact_manifest(value: Mapping[str, Any] | None, expected: Mapping[str, Any]) -> bool:
    return isinstance(value, Mapping) and dict(value) == dict(expected)


def validate_final_scheduler_freeze(
    *,
    step12_manifest: Mapping[str, Any] | None,
    step13a_manifest: Mapping[str, Any] | None,
    step13b_manifest: Mapping[str, Any] | None,
    step13c_manifest: Mapping[str, Any] | None,
    step13a_scheduler_evidence_ok: bool,
    step13b_supervisor_evidence_ok: bool,
    step13c_recovery_evidence_ok: bool,
    bounded_recovery_limits_evidence_ok: bool,
    zero_parent_drift_ok: bool,
    zero_runtime_execution_ok: bool,
    zero_retry_restart_execution_ok: bool,
    zero_network_calls_ok: bool,
    zero_production_database_writes_ok: bool,
    zero_production_activation_ok: bool,
    zero_actionable_output_ok: bool,
) -> dict[str, Any]:
    """Certify Step 13A/B/C as one final immutable scheduler/recovery block."""
    expected_parents = _parent_manifests()
    supplied = {
        "step12": step12_manifest,
        "step13a": step13a_manifest,
        "step13b": step13b_manifest,
        "step13c": step13c_manifest,
    }
    failures: list[str] = []
    for name, expected in expected_parents.items():
        if not _exact_manifest(supplied[name], expected):
            failures.append(f"{name.upper()}_MANIFEST_MISMATCH")

    evidence = {
        "step13a_scheduler_evidence_ok": step13a_scheduler_evidence_ok,
        "step13b_supervisor_evidence_ok": step13b_supervisor_evidence_ok,
        "step13c_recovery_evidence_ok": step13c_recovery_evidence_ok,
        "bounded_recovery_limits_evidence_ok": bounded_recovery_limits_evidence_ok,
        "zero_parent_drift_ok": zero_parent_drift_ok,
        "zero_runtime_execution_ok": zero_runtime_execution_ok,
        "zero_retry_restart_execution_ok": zero_retry_restart_execution_ok,
        "zero_network_calls_ok": zero_network_calls_ok,
        "zero_production_database_writes_ok": zero_production_database_writes_ok,
        "zero_production_activation_ok": zero_production_activation_ok,
        "zero_actionable_output_ok": zero_actionable_output_ok,
    }
    for key in _CERTIFICATION_EVIDENCE_KEYS:
        if evidence[key] is not True:
            failures.append(f"{key.upper()}_REQUIRED")

    boundary = final_scheduler_freeze_manifest()
    if boundary["runtime_mode"] != "SHADOW_ONLY":
        failures.append("STEP13D_RUNTIME_MODE_DRIFT")
    if boundary["maximum_permits_per_tick"] != 1:
        failures.append("STEP13D_PERMIT_BOUND_DRIFT")
    if boundary["maximum_max_recovery_attempts"] != 5:
        failures.append("STEP13D_RECOVERY_CEILING_DRIFT")

    for key, value in PROTECTED_INVARIANTS.items():
        if value is not False or boundary.get(key) is not False:
            failures.append(f"STEP13D_PROTECTED_INVARIANT_DRIFT:{key}")

    forbidden_true = (
        "scheduler_state_mutation_added_by_step13d",
        "recovery_state_mutation_added_by_step13d",
        "stuck_cycle_release_performed_by_step13d",
        "retry_execution_performed_by_step13d",
        "restart_execution_performed_by_step13d",
        "runtime_cycle_execution_added_by_step13d",
        "scheduler_sleep_loop_added_by_step13d",
        "background_thread_added_by_step13d",
        "background_process_added_by_step13d",
        "network_io_added_by_step13d",
        "provider_network_calls_enabled_by_step13d",
        "production_api_wiring_added_by_step13d",
        "production_runtime_wiring_added_by_step13d",
        "production_scheduler_activation_enabled",
        "production_database_writes_enabled",
        "persistence_schema_changed_by_step13d",
        "actionable_output_enabled",
        "production_provider_consensus_enabled",
        "production_provider_failover_enabled",
        "best_price_selection_enabled",
        "provider_weighting_enabled",
        "price_fabrication_allowed",
        "fallback_price_fabrication_allowed",
        "durable_cross_process_recovery_added_by_step13d",
        "always_on_runtime_added_by_step13d",
    )
    for key in forbidden_true:
        if boundary.get(key) is not False:
            failures.append(f"STEP13D_FORBIDDEN_CAPABILITY_ENABLED:{key}")

    result: dict[str, Any] = {
        "data_type": CERTIFICATION_DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "certified": not failures,
        "failures": failures,
        "runtime_mode": RUNTIME_MODE,
        "final_freeze_status": FINAL_FREEZE_STATUS if not failures else "NOT_CERTIFIED",
        "final_certification_marker": FINAL_CERTIFICATION_MARKER if not failures else None,
        "parent_manifest_sha256": _parent_manifest_hashes(),
        "evidence": deepcopy(evidence),
        "freeze_manifest": boundary,
        "runtime_cycle_executed": False,
        "retry_executed": False,
        "restart_executed": False,
        "scheduler_state_mutated": False,
        "recovery_state_mutated": False,
        "network_io_performed": False,
        "provider_network_calls": 0,
        "production_database_writes": 0,
        "production_scheduler_activation": False,
        "actionable_output_enabled": False,
    }
    result["certification_sha256"] = _hash(result)
    return result


def validate_final_scheduler_freeze_manifest(
    manifest: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Rebuild and exact-compare the final Step-13 freeze manifest."""
    if not isinstance(manifest, Mapping):
        return {
            "data_type": DATA_TYPE,
            "schema_version": SCHEMA_VERSION,
            "freeze_manifest_valid": False,
            "failures": ["STEP13D_FREEZE_MANIFEST_NOT_MAPPING"],
        }
    expected = final_scheduler_freeze_manifest()
    failures = [] if dict(manifest) == expected else ["STEP13D_FREEZE_MANIFEST_EXACT_CONTRACT_MISMATCH"]
    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "freeze_manifest_valid": not failures,
        "failures": failures,
    }


__all__ = [
    "DATA_TYPE",
    "CERTIFICATION_DATA_TYPE",
    "SCHEMA_VERSION",
    "STEP13D_BASE_MAIN_SHA",
    "FINAL_FREEZE_STATUS",
    "RUNTIME_MODE",
    "FINAL_CERTIFICATION_MARKER",
    "STEP13_STAGE_CHAIN",
    "STEP13_CERTIFICATION_MARKERS",
    "STEP13_PARENT_MERGE_SHAS",
    "FROZEN_PARENT_SOURCE_BLOBS",
    "MLBStep13DFinalSchedulerFreezeError",
    "final_scheduler_freeze_manifest",
    "validate_final_scheduler_freeze",
    "validate_final_scheduler_freeze_manifest",
]
