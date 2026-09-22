"""MLB Step 14D — final durable persistence/restart/lease release freeze.

Steps 14A-14C established the durable checkpoint contract, isolated PostgreSQL
checkpoint adapter, and foreground durable restart plus cross-process lease
protection above the frozen Step 13 scheduler/recovery block. Step 14D adds no
new runtime behavior. It seals those layers as one content-addressed release
boundary for later live persistence preflight and explicit activation work.

This module never opens a database connection, runs a scheduler/runtime cycle,
executes a retry or restart, acquires a lease, persists a checkpoint, performs
provider/sportsbook network I/O, starts a worker/thread, or activates production.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import hashlib
import json
from typing import Any

from sports_api.mlb_step9_final_freeze_v1 import PROTECTED_INVARIANTS
from sports_api.mlb_step13_final_scheduler_freeze_v1 import (
    FINAL_CERTIFICATION_MARKER as STEP13D_FINAL_CERTIFICATION_MARKER,
    RUNTIME_MODE as STEP13D_RUNTIME_MODE,
    final_scheduler_freeze_manifest,
    validate_final_scheduler_freeze_manifest,
)
from sports_api import mlb_step14a_persistence_contract_v1 as step14a
from sports_api import mlb_step14b_database_checkpoint_adapter_v1 as step14b
from sports_api import mlb_step14c_durable_restart_lease_v1 as step14c

DATA_TYPE = "mlb_step14_final_persistence_freeze_v1"
CERTIFICATION_DATA_TYPE = "mlb_step14d_final_persistence_certification_v1"
SCHEMA_VERSION = 1
STEP14D_BASE_MAIN_SHA = "9435d9db84b34a276281b2528205030ac27dd3c6"
FINAL_FREEZE_STATUS = "STEP14_FROZEN_DURABLE_PERSISTENCE_COMPLETE"
RUNTIME_MODE = "SHADOW_ONLY"
FINAL_CERTIFICATION_MARKER = "MLB_STEP14D_FINAL_PERSISTENCE_FREEZE_GREEN"
RELEASE_ID = "mlb_step14_durable_persistence_restart_lease_2026_frozen_v1"

STEP14_STAGE_CHAIN = (
    "14A_PERSISTENCE_CONTRACT",
    "14B_DATABASE_CHECKPOINT_ADAPTER",
    "14C_DURABLE_RESTART_LEASE",
)

STEP14_CERTIFICATION_MARKERS = (
    step14a.FINAL_CERTIFICATION_MARKER,
    step14b.FINAL_CERTIFICATION_MARKER,
    step14c.FINAL_CERTIFICATION_MARKER,
)

STEP14_PARENT_MERGE_SHAS = {
    "step14a_merge_sha": "3dae5181571dbfea45f6f0db87e916d25e971170",
    "step14b_merge_sha": "195df0c15de1998754204080f9db4a76bca74e4b",
    "step14c_merge_sha": STEP14D_BASE_MAIN_SHA,
}

FROZEN_PARENT_SOURCE_BLOBS = {
    "step13_final_scheduler_freeze_blob": "b53400fe205717ca075231f841b4ca7aabed90bc",
    "step14a_persistence_contract_blob": "373996a35959e5ad2252325062b250ddffd4286c",
    "step14a_persistence_schema_blob": "969c88c529486c8cde54f7928919e2a393a0f588",
    "step14b_database_checkpoint_adapter_blob": "ee7ffe3117edc33b1377f883c25613d63760095b",
    "step14c_durable_restart_lease_blob": "2ea48e2badc73750f96cc8d3b5ef3927fb40a08e",
    "step14c_runtime_lease_schema_blob": "e341e41ae7b21d1781c0b96be05ad924fcccab86",
}

_CERTIFICATION_EVIDENCE_KEYS = (
    "step14a_contract_evidence_ok",
    "step14b_adapter_evidence_ok",
    "step14c_restart_restore_evidence_ok",
    "step14c_duplicate_lease_fencing_evidence_ok",
    "step14c_lost_lease_fencing_evidence_ok",
    "checkpoint_cas_evidence_ok",
    "append_only_history_evidence_ok",
    "zero_parent_drift_ok",
    "zero_runtime_retry_restart_execution_ok",
    "zero_provider_sportsbook_calls_ok",
    "zero_live_database_connections_ok",
    "zero_production_activation_ok",
    "zero_actionable_output_ok",
)


class MLBStep14DFinalPersistenceFreezeError(ValueError):
    """Raised when Step 14D cannot certify the frozen persistence boundary."""


def _hash(value: Any) -> str:
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _parent_manifests() -> dict[str, dict[str, Any]]:
    return {
        "step13d": final_scheduler_freeze_manifest(),
        "step14a": step14a.persistence_contract_manifest(),
        "step14b": step14b.database_checkpoint_adapter_manifest(),
        "step14c": step14c.durable_restart_lease_manifest(),
    }


def _parent_manifest_hashes() -> dict[str, str]:
    return {name: _hash(value) for name, value in _parent_manifests().items()}


def _validate_parent_contracts() -> list[str]:
    failures: list[str] = []
    parents = _parent_manifests()
    step13_validation = validate_final_scheduler_freeze_manifest(parents["step13d"])
    if step13_validation.get("freeze_manifest_valid") is not True:
        failures.append("STEP13D_PARENT_INVALID")
    step14a_validation = step14a.validate_persistence_contract_manifest(parents["step14a"])
    if step14a_validation.get("manifest_valid") is not True:
        failures.append("STEP14A_PARENT_INVALID")
    step14b_validation = step14b.validate_database_checkpoint_adapter_manifest(parents["step14b"])
    if step14b_validation.get("manifest_valid") is not True:
        failures.append("STEP14B_PARENT_INVALID")
    step14c_validation = step14c.validate_durable_restart_lease_manifest(parents["step14c"])
    if step14c_validation.get("manifest_valid") is not True:
        failures.append("STEP14C_PARENT_INVALID")
    return failures


def final_persistence_freeze_manifest() -> dict[str, Any]:
    """Return the immutable final Step-14 durable persistence release boundary."""
    parent_failures = _validate_parent_contracts()
    if parent_failures:
        raise MLBStep14DFinalPersistenceFreezeError(
            "frozen parent contract validation failed: " + ", ".join(parent_failures)
        )

    manifest: dict[str, Any] = {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "step14d_base_main_sha": STEP14D_BASE_MAIN_SHA,
        "release_id": RELEASE_ID,
        "final_freeze_status": FINAL_FREEZE_STATUS,
        "runtime_mode": RUNTIME_MODE,
        "final_certification_marker": FINAL_CERTIFICATION_MARKER,
        "step13d_runtime_mode_required": STEP13D_RUNTIME_MODE,
        "step13d_final_certification_marker_required": STEP13D_FINAL_CERTIFICATION_MARKER,
        "step14a_final_certification_marker_required": step14a.FINAL_CERTIFICATION_MARKER,
        "step14b_final_certification_marker_required": step14b.FINAL_CERTIFICATION_MARKER,
        "step14c_final_certification_marker_required": step14c.FINAL_CERTIFICATION_MARKER,
        "step14_stage_chain": list(STEP14_STAGE_CHAIN),
        "step14_certification_markers": list(STEP14_CERTIFICATION_MARKERS),
        "step14_parent_merge_shas": deepcopy(STEP14_PARENT_MERGE_SHAS),
        "frozen_parent_source_blobs": deepcopy(FROZEN_PARENT_SOURCE_BLOBS),
        "parent_manifest_sha256": _parent_manifest_hashes(),
        "step14_durable_persistence_block_frozen": True,
        "step14a_persistence_contract_frozen": True,
        "step14b_database_checkpoint_adapter_frozen": True,
        "step14c_durable_restart_lease_frozen": True,
        "step14c_future_step14d_requirement_satisfied": True,
        "exact_parent_manifests_required": True,
        "exact_parent_source_blobs_required": True,
        "postgresql_checkpoint_adapter_certified": True,
        "append_only_checkpoint_history_certified": True,
        "checkpoint_head_compare_and_swap_certified": True,
        "deterministic_checkpoint_identity_certified": True,
        "exact_scheduler_state_restart_restore_certified": True,
        "exact_recovery_state_restart_restore_certified": True,
        "exact_recovery_handoff_restart_restore_certified": True,
        "fresh_start_without_checkpoint_certified": True,
        "durable_restart_recovery_certified": True,
        "durable_distributed_lease_certified": True,
        "cross_process_duplicate_run_guard_certified": True,
        "uuid_lease_ownership_token_certified": True,
        "monotonic_fencing_generation_certified": True,
        "lease_expiry_and_takeover_certified": True,
        "stale_owner_fencing_certified": True,
        "lease_revalidation_before_checkpoint_save_certified": True,
        "checkpoint_persist_under_valid_lease_certified": True,
        "foreground_only_certified": True,
        "explicit_invocation_required": True,
        "database_schema_name": step14a.DATABASE_SCHEMA_NAME,
        "checkpoint_table_name": step14a.CHECKPOINT_TABLE_NAME,
        "checkpoint_head_table_name": step14a.CHECKPOINT_HEAD_TABLE_NAME,
        "lease_table_name": step14c.LEASE_TABLE_NAME,
        "step14a_sql_schema_path": step14a.SQL_SCHEMA_PATH,
        "step14c_lease_sql_schema_path": step14c.LEASE_SQL_SCHEMA_PATH,
        "step14c_lease_sql_schema_sha256": step14c.LEASE_SQL_SCHEMA_SHA256,
        "default_lease_ttl_seconds": step14c.DEFAULT_LEASE_TTL_SECONDS,
        "minimum_lease_ttl_seconds": step14c.MIN_LEASE_TTL_SECONDS,
        "maximum_lease_ttl_seconds": step14c.MAX_LEASE_TTL_SECONDS,
        "global_persistence_runtime_enabled": False,
        "automatic_restart_execution_allowed": False,
        "automatic_production_restart_activation_allowed": False,
        "production_runtime_activation_allowed": False,
        "production_scheduler_activation_allowed": False,
        "public_api_activation_allowed": False,
        "actionable_output_allowed": False,
        "background_worker_allowed": False,
        "background_thread_allowed": False,
        "schema_auto_apply_allowed": False,
        "supabase_rest_write_allowed": False,
        "runtime_cycle_execution_added_by_step14d": False,
        "retry_execution_added_by_step14d": False,
        "restart_execution_added_by_step14d": False,
        "lease_operation_executed_by_step14d": False,
        "checkpoint_read_executed_by_step14d": False,
        "checkpoint_write_executed_by_step14d": False,
        "network_io_added_by_step14d": False,
        "provider_network_calls_enabled_by_step14d": False,
        "sportsbook_network_calls_enabled_by_step14d": False,
        "production_database_writes_enabled_by_step14d": False,
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
        "future_step15_live_postgres_preflight_required": True,
        "future_explicit_production_activation_step_required": True,
        **PROTECTED_INVARIANTS,
    }
    manifest["freeze_manifest_sha256"] = _hash(manifest)
    return manifest


def validate_final_persistence_freeze_manifest(
    manifest: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Rebuild and exact-compare the final Step-14 freeze manifest."""
    if not isinstance(manifest, Mapping):
        return {
            "data_type": DATA_TYPE,
            "schema_version": SCHEMA_VERSION,
            "freeze_manifest_valid": False,
            "failures": ["STEP14D_FREEZE_MANIFEST_NOT_MAPPING"],
        }
    expected = final_persistence_freeze_manifest()
    failures = [] if dict(manifest) == expected else [
        "STEP14D_FREEZE_MANIFEST_EXACT_CONTRACT_MISMATCH"
    ]
    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "freeze_manifest_valid": not failures,
        "failures": failures,
    }


def _exact_manifest(value: Mapping[str, Any] | None, expected: Mapping[str, Any]) -> bool:
    return isinstance(value, Mapping) and dict(value) == dict(expected)


def validate_final_persistence_freeze(
    *,
    step13d_manifest: Mapping[str, Any] | None,
    step14a_manifest: Mapping[str, Any] | None,
    step14b_manifest: Mapping[str, Any] | None,
    step14c_manifest: Mapping[str, Any] | None,
    step14a_contract_evidence_ok: bool,
    step14b_adapter_evidence_ok: bool,
    step14c_restart_restore_evidence_ok: bool,
    step14c_duplicate_lease_fencing_evidence_ok: bool,
    step14c_lost_lease_fencing_evidence_ok: bool,
    checkpoint_cas_evidence_ok: bool,
    append_only_history_evidence_ok: bool,
    zero_parent_drift_ok: bool,
    zero_runtime_retry_restart_execution_ok: bool,
    zero_provider_sportsbook_calls_ok: bool,
    zero_live_database_connections_ok: bool,
    zero_production_activation_ok: bool,
    zero_actionable_output_ok: bool,
) -> dict[str, Any]:
    """Certify Steps 14A/B/C as one immutable durable persistence block."""
    expected_parents = _parent_manifests()
    supplied = {
        "step13d": step13d_manifest,
        "step14a": step14a_manifest,
        "step14b": step14b_manifest,
        "step14c": step14c_manifest,
    }
    failures: list[str] = []
    for name, expected in expected_parents.items():
        if not _exact_manifest(supplied[name], expected):
            failures.append(f"{name.upper()}_MANIFEST_MISMATCH")

    evidence = {
        "step14a_contract_evidence_ok": step14a_contract_evidence_ok,
        "step14b_adapter_evidence_ok": step14b_adapter_evidence_ok,
        "step14c_restart_restore_evidence_ok": step14c_restart_restore_evidence_ok,
        "step14c_duplicate_lease_fencing_evidence_ok": step14c_duplicate_lease_fencing_evidence_ok,
        "step14c_lost_lease_fencing_evidence_ok": step14c_lost_lease_fencing_evidence_ok,
        "checkpoint_cas_evidence_ok": checkpoint_cas_evidence_ok,
        "append_only_history_evidence_ok": append_only_history_evidence_ok,
        "zero_parent_drift_ok": zero_parent_drift_ok,
        "zero_runtime_retry_restart_execution_ok": zero_runtime_retry_restart_execution_ok,
        "zero_provider_sportsbook_calls_ok": zero_provider_sportsbook_calls_ok,
        "zero_live_database_connections_ok": zero_live_database_connections_ok,
        "zero_production_activation_ok": zero_production_activation_ok,
        "zero_actionable_output_ok": zero_actionable_output_ok,
    }
    for key in _CERTIFICATION_EVIDENCE_KEYS:
        if evidence[key] is not True:
            failures.append(f"{key.upper()}_REQUIRED")

    boundary = final_persistence_freeze_manifest()
    if boundary["runtime_mode"] != "SHADOW_ONLY":
        failures.append("STEP14D_RUNTIME_MODE_DRIFT")
    if boundary["default_lease_ttl_seconds"] != 300:
        failures.append("STEP14D_DEFAULT_LEASE_TTL_DRIFT")
    if boundary["minimum_lease_ttl_seconds"] != 60:
        failures.append("STEP14D_MINIMUM_LEASE_TTL_DRIFT")
    if boundary["maximum_lease_ttl_seconds"] != 3600:
        failures.append("STEP14D_MAXIMUM_LEASE_TTL_DRIFT")

    for key, value in PROTECTED_INVARIANTS.items():
        if value is not False or boundary.get(key) is not False:
            failures.append(f"STEP14D_PROTECTED_INVARIANT_DRIFT:{key}")

    forbidden_true = (
        "global_persistence_runtime_enabled",
        "automatic_restart_execution_allowed",
        "automatic_production_restart_activation_allowed",
        "production_runtime_activation_allowed",
        "production_scheduler_activation_allowed",
        "public_api_activation_allowed",
        "actionable_output_allowed",
        "background_worker_allowed",
        "background_thread_allowed",
        "schema_auto_apply_allowed",
        "supabase_rest_write_allowed",
        "runtime_cycle_execution_added_by_step14d",
        "retry_execution_added_by_step14d",
        "restart_execution_added_by_step14d",
        "lease_operation_executed_by_step14d",
        "checkpoint_read_executed_by_step14d",
        "checkpoint_write_executed_by_step14d",
        "network_io_added_by_step14d",
        "provider_network_calls_enabled_by_step14d",
        "sportsbook_network_calls_enabled_by_step14d",
        "production_database_writes_enabled_by_step14d",
        "production_provider_consensus_enabled",
        "production_provider_failover_enabled",
        "best_price_selection_enabled",
        "provider_weighting_enabled",
        "price_fabrication_allowed",
        "fallback_price_fabrication_allowed",
    )
    for key in forbidden_true:
        if boundary.get(key) is not False:
            failures.append(f"STEP14D_FORBIDDEN_CAPABILITY_ENABLED:{key}")

    result: dict[str, Any] = {
        "data_type": CERTIFICATION_DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "certified": not failures,
        "failures": failures,
        "runtime_mode": RUNTIME_MODE,
        "release_id": RELEASE_ID,
        "final_freeze_status": FINAL_FREEZE_STATUS if not failures else "NOT_CERTIFIED",
        "final_certification_marker": FINAL_CERTIFICATION_MARKER if not failures else None,
        "parent_manifest_sha256": _parent_manifest_hashes(),
        "evidence": deepcopy(evidence),
        "freeze_manifest": boundary,
        "runtime_cycle_executed": False,
        "retry_executed": False,
        "restart_executed": False,
        "lease_operation_executed": False,
        "checkpoint_read_executed": False,
        "checkpoint_write_executed": False,
        "network_io_performed": False,
        "provider_network_calls": 0,
        "sportsbook_network_calls": 0,
        "live_database_connections": 0,
        "production_database_writes": 0,
        "production_runtime_activation": False,
        "production_scheduler_activation": False,
        "actionable_output_enabled": False,
    }
    result["certification_sha256"] = _hash(result)
    return result


__all__ = [
    "DATA_TYPE",
    "CERTIFICATION_DATA_TYPE",
    "SCHEMA_VERSION",
    "STEP14D_BASE_MAIN_SHA",
    "FINAL_FREEZE_STATUS",
    "RUNTIME_MODE",
    "FINAL_CERTIFICATION_MARKER",
    "RELEASE_ID",
    "STEP14_STAGE_CHAIN",
    "STEP14_CERTIFICATION_MARKERS",
    "STEP14_PARENT_MERGE_SHAS",
    "FROZEN_PARENT_SOURCE_BLOBS",
    "MLBStep14DFinalPersistenceFreezeError",
    "final_persistence_freeze_manifest",
    "validate_final_persistence_freeze_manifest",
    "validate_final_persistence_freeze",
]
