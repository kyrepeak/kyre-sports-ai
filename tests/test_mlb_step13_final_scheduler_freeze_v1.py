from __future__ import annotations

from copy import deepcopy
import hashlib
import json

import pytest

from sports_api.mlb_step9_final_freeze_v1 import PROTECTED_INVARIANTS
from sports_api.mlb_step12_final_runtime_freeze_v1 import (
    FINAL_CERTIFICATION_MARKER as STEP12_MARKER,
    FINAL_FREEZE_STATUS as STEP12_STATUS,
    RUNTIME_MODE as STEP12_MODE,
    final_runtime_freeze_manifest,
)
from sports_api.mlb_step13a_bounded_scheduler_v1 import (
    FINAL_CERTIFICATION_MARKER as STEP13A_MARKER,
    RUNTIME_MODE as STEP13A_MODE,
    SCHEDULER_STATUS as STEP13A_STATUS,
    bounded_scheduler_manifest,
)
from sports_api.mlb_step13b_runtime_supervisor_v1 import (
    FINAL_CERTIFICATION_MARKER as STEP13B_MARKER,
    RUNTIME_MODE as STEP13B_MODE,
    SUPERVISOR_STATUS as STEP13B_STATUS,
    runtime_supervisor_manifest,
)
from sports_api.mlb_step13c_reliability_recovery_v1 import (
    FINAL_CERTIFICATION_MARKER as STEP13C_MARKER,
    RELIABILITY_STATUS as STEP13C_STATUS,
    RUNTIME_MODE as STEP13C_MODE,
    reliability_recovery_manifest,
)
from sports_api.mlb_step13_final_scheduler_freeze_v1 import (
    CERTIFICATION_DATA_TYPE,
    DATA_TYPE,
    FINAL_CERTIFICATION_MARKER,
    FINAL_FREEZE_STATUS,
    FROZEN_PARENT_SOURCE_BLOBS,
    RUNTIME_MODE,
    SCHEMA_VERSION,
    STEP13_CERTIFICATION_MARKERS,
    STEP13_PARENT_MERGE_SHAS,
    STEP13_STAGE_CHAIN,
    STEP13D_BASE_MAIN_SHA,
    final_scheduler_freeze_manifest,
    validate_final_scheduler_freeze,
    validate_final_scheduler_freeze_manifest,
)

BASE_SHA = "73e81b5dd6edab04e4e13d654f1a2c5a8d3eabe1"


def _hash(value):
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _valid_kwargs():
    return {
        "step12_manifest": final_runtime_freeze_manifest(),
        "step13a_manifest": bounded_scheduler_manifest(),
        "step13b_manifest": runtime_supervisor_manifest(),
        "step13c_manifest": reliability_recovery_manifest(),
        "step13a_scheduler_evidence_ok": True,
        "step13b_supervisor_evidence_ok": True,
        "step13c_recovery_evidence_ok": True,
        "bounded_recovery_limits_evidence_ok": True,
        "zero_parent_drift_ok": True,
        "zero_runtime_execution_ok": True,
        "zero_retry_restart_execution_ok": True,
        "zero_network_calls_ok": True,
        "zero_production_database_writes_ok": True,
        "zero_production_activation_ok": True,
        "zero_actionable_output_ok": True,
    }


def test_constants_are_exact():
    assert DATA_TYPE == "mlb_step13_final_scheduler_freeze_v1"
    assert CERTIFICATION_DATA_TYPE == "mlb_step13d_final_scheduler_certification_v1"
    assert SCHEMA_VERSION == 1
    assert STEP13D_BASE_MAIN_SHA == BASE_SHA
    assert FINAL_FREEZE_STATUS == "STEP13_FROZEN_SCHEDULER_RECOVERY_COMPLETE"
    assert RUNTIME_MODE == "SHADOW_ONLY"
    assert FINAL_CERTIFICATION_MARKER == "MLB_STEP13D_FINAL_SCHEDULER_FREEZE_GREEN"


def test_stage_chain_is_exact():
    assert STEP13_STAGE_CHAIN == (
        "13A_BOUNDED_SCHEDULER",
        "13B_RUNTIME_SUPERVISOR",
        "13C_RELIABILITY_RECOVERY",
    )


def test_certification_markers_are_exact():
    assert STEP13_CERTIFICATION_MARKERS == (
        STEP13A_MARKER,
        STEP13B_MARKER,
        STEP13C_MARKER,
    )


def test_parent_merge_shas_are_exact():
    assert STEP13_PARENT_MERGE_SHAS == {
        "step13a_merge_sha": "1587b4825ad5ce01c8dcd669417da6046ede6921",
        "step13b_merge_sha": "7895eb6699630025fd49698e4b7fc2d3ff013fb6",
        "step13c_merge_sha": BASE_SHA,
    }


def test_frozen_parent_source_blobs_are_exact():
    assert FROZEN_PARENT_SOURCE_BLOBS == {
        "step12_final_runtime_freeze_blob": "ae0555e01c9c2787511ae9b7ee85e1e1a861d781",
        "step13a_bounded_scheduler_blob": "fbb61033835afb76f5f49fa990001f8e5877a696",
        "step13b_runtime_supervisor_blob": "fe0d415f4a5e41c834735f8cc81a13cf0398f583",
        "step13c_reliability_recovery_blob": "0d78c484d2f9c6e3162f55961c43688303882643",
    }


@pytest.mark.parametrize("value", FROZEN_PARENT_SOURCE_BLOBS.values())
def test_frozen_source_blob_format(value):
    assert len(value) == 40
    assert value == value.lower()
    assert all(ch in "0123456789abcdef" for ch in value)


def test_manifest_is_bit_deterministic():
    assert final_scheduler_freeze_manifest() == final_scheduler_freeze_manifest()


def test_manifest_freeze_hash_is_self_consistent():
    manifest = final_scheduler_freeze_manifest()
    observed = manifest.pop("freeze_manifest_sha256")
    assert observed == _hash(manifest)


def test_manifest_pins_step12_exact_boundary():
    manifest = final_scheduler_freeze_manifest()
    assert manifest["step12_final_freeze_status_required"] == STEP12_STATUS
    assert manifest["step12_runtime_mode_required"] == STEP12_MODE == "SHADOW_ONLY"
    assert manifest["step12_final_certification_marker_required"] == STEP12_MARKER


def test_manifest_pins_step13a_exact_boundary():
    manifest = final_scheduler_freeze_manifest()
    assert manifest["step13a_scheduler_status_required"] == STEP13A_STATUS
    assert manifest["step13a_runtime_mode_required"] == STEP13A_MODE == "SHADOW_ONLY"
    assert manifest["step13a_final_certification_marker_required"] == STEP13A_MARKER


def test_manifest_pins_step13b_exact_boundary():
    manifest = final_scheduler_freeze_manifest()
    assert manifest["step13b_supervisor_status_required"] == STEP13B_STATUS
    assert manifest["step13b_runtime_mode_required"] == STEP13B_MODE == "SHADOW_ONLY"
    assert manifest["step13b_final_certification_marker_required"] == STEP13B_MARKER


def test_manifest_pins_step13c_exact_boundary():
    manifest = final_scheduler_freeze_manifest()
    assert manifest["step13c_reliability_status_required"] == STEP13C_STATUS
    assert manifest["step13c_runtime_mode_required"] == STEP13C_MODE == "SHADOW_ONLY"
    assert manifest["step13c_final_certification_marker_required"] == STEP13C_MARKER


def test_parent_manifest_hashes_match_live_frozen_contracts():
    manifest = final_scheduler_freeze_manifest()
    expected = {
        "step12": _hash(final_runtime_freeze_manifest()),
        "step13a": _hash(bounded_scheduler_manifest()),
        "step13b": _hash(runtime_supervisor_manifest()),
        "step13c": _hash(reliability_recovery_manifest()),
    }
    assert manifest["parent_manifest_sha256"] == expected


@pytest.mark.parametrize("name", ["step12", "step13a", "step13b", "step13c"])
def test_parent_manifest_hashes_are_sha256(name):
    value = final_scheduler_freeze_manifest()["parent_manifest_sha256"][name]
    assert len(value) == 64
    assert all(ch in "0123456789abcdef" for ch in value)


@pytest.mark.parametrize(
    "key",
    [
        "step13_scheduler_recovery_block_frozen",
        "step13a_bounded_scheduler_frozen",
        "step13b_runtime_supervisor_frozen",
        "step13c_reliability_recovery_frozen",
        "step13c_future_scheduler_freeze_requirement_satisfied",
        "exact_parent_manifests_required",
        "exact_parent_source_blobs_required",
        "fixed_cadence_certified",
        "overlap_prevention_certified",
        "lifecycle_supervision_certified",
        "failure_isolation_certified",
        "bounded_retry_authorization_certified",
        "exponential_cooldown_certified",
        "stuck_cycle_grace_certified",
        "stuck_cycle_restart_authorization_certified",
        "process_local_duplicate_recovery_guard_certified",
        "terminal_release_authorization_certified",
        "observational_and_authorization_only",
        "future_durable_recovery_persistence_step_required",
        "future_explicit_activation_step_required",
    ],
)
def test_required_final_freeze_guards_are_true(key):
    assert final_scheduler_freeze_manifest()[key] is True


@pytest.mark.parametrize(
    "key",
    [
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
        "durable_cross_process_recovery_added_by_step13d",
        "always_on_runtime_added_by_step13d",
    ],
)
def test_forbidden_final_freeze_capabilities_are_false(key):
    assert final_scheduler_freeze_manifest()[key] is False


def test_all_protected_invariants_remain_false():
    manifest = final_scheduler_freeze_manifest()
    assert PROTECTED_INVARIANTS
    for key, value in PROTECTED_INVARIANTS.items():
        assert value is False
        assert manifest[key] is False


@pytest.mark.parametrize(
    ("key", "expected"),
    [
        ("default_scheduler_interval_seconds", 30),
        ("maximum_permits_per_tick", 1),
        ("default_max_cycle_runtime_seconds", 120),
        ("default_max_recovery_attempts", 3),
        ("maximum_max_recovery_attempts", 5),
        ("default_base_cooldown_seconds", 15),
        ("default_max_cooldown_seconds", 120),
        ("default_stuck_grace_seconds", 30),
    ],
)
def test_certified_operating_bounds_are_exact(key, expected):
    assert final_scheduler_freeze_manifest()[key] == expected


def test_valid_final_certification_is_green():
    result = validate_final_scheduler_freeze(**_valid_kwargs())
    assert result["certified"] is True
    assert result["failures"] == []
    assert result["runtime_mode"] == "SHADOW_ONLY"
    assert result["final_freeze_status"] == FINAL_FREEZE_STATUS
    assert result["final_certification_marker"] == FINAL_CERTIFICATION_MARKER


def test_certification_hash_is_self_consistent():
    result = validate_final_scheduler_freeze(**_valid_kwargs())
    observed = result.pop("certification_sha256")
    assert observed == _hash(result)


def test_certification_is_bit_deterministic():
    assert validate_final_scheduler_freeze(**_valid_kwargs()) == validate_final_scheduler_freeze(**_valid_kwargs())


@pytest.mark.parametrize(
    "key",
    [
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
    ],
)
def test_each_missing_evidence_gate_fails_certification(key):
    kwargs = _valid_kwargs()
    kwargs[key] = False
    result = validate_final_scheduler_freeze(**kwargs)
    assert result["certified"] is False
    assert result["final_freeze_status"] == "NOT_CERTIFIED"
    assert result["final_certification_marker"] is None
    assert f"{key.upper()}_REQUIRED" in result["failures"]


@pytest.mark.parametrize(
    "key",
    [
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
    ],
)
@pytest.mark.parametrize("bad_value", [1, "true", None])
def test_evidence_gates_require_exact_true(key, bad_value):
    kwargs = _valid_kwargs()
    kwargs[key] = bad_value
    result = validate_final_scheduler_freeze(**kwargs)
    assert result["certified"] is False
    assert f"{key.upper()}_REQUIRED" in result["failures"]


@pytest.mark.parametrize(
    ("key", "failure"),
    [
        ("step12_manifest", "STEP12_MANIFEST_MISMATCH"),
        ("step13a_manifest", "STEP13A_MANIFEST_MISMATCH"),
        ("step13b_manifest", "STEP13B_MANIFEST_MISMATCH"),
        ("step13c_manifest", "STEP13C_MANIFEST_MISMATCH"),
    ],
)
def test_each_parent_manifest_is_required_exactly(key, failure):
    kwargs = _valid_kwargs()
    tampered = deepcopy(kwargs[key])
    tampered["tampered"] = True
    kwargs[key] = tampered
    result = validate_final_scheduler_freeze(**kwargs)
    assert result["certified"] is False
    assert failure in result["failures"]


@pytest.mark.parametrize(
    ("key", "failure"),
    [
        ("step12_manifest", "STEP12_MANIFEST_MISMATCH"),
        ("step13a_manifest", "STEP13A_MANIFEST_MISMATCH"),
        ("step13b_manifest", "STEP13B_MANIFEST_MISMATCH"),
        ("step13c_manifest", "STEP13C_MANIFEST_MISMATCH"),
    ],
)
@pytest.mark.parametrize("bad_value", [None, [], "manifest", 1, True])
def test_non_mapping_or_missing_parent_manifest_fails_closed(key, failure, bad_value):
    kwargs = _valid_kwargs()
    kwargs[key] = bad_value
    result = validate_final_scheduler_freeze(**kwargs)
    assert result["certified"] is False
    assert failure in result["failures"]


def test_validation_does_not_mutate_parent_manifests():
    kwargs = _valid_kwargs()
    before = deepcopy(kwargs)
    validate_final_scheduler_freeze(**kwargs)
    assert kwargs == before


@pytest.mark.parametrize(
    "field",
    [
        "data_type",
        "schema_version",
        "step13d_base_main_sha",
        "final_freeze_status",
        "runtime_mode",
        "final_certification_marker",
        "step12_final_freeze_status_required",
        "step13a_scheduler_status_required",
        "step13b_supervisor_status_required",
        "step13c_reliability_status_required",
        "step13_stage_chain",
        "step13_certification_markers",
        "step13_parent_merge_shas",
        "frozen_parent_source_blobs",
        "parent_manifest_sha256",
        "step13_scheduler_recovery_block_frozen",
        "fixed_cadence_certified",
        "bounded_retry_authorization_certified",
        "maximum_permits_per_tick",
        "maximum_max_recovery_attempts",
        "production_scheduler_activation_enabled",
        "freeze_manifest_sha256",
    ],
)
def test_tampered_final_manifest_fails_exact_validation(field):
    manifest = final_scheduler_freeze_manifest()
    value = manifest[field]
    if isinstance(value, bool):
        manifest[field] = not value
    elif isinstance(value, int):
        manifest[field] = value + 1
    elif isinstance(value, list):
        manifest[field] = list(value) + ["TAMPERED"]
    elif isinstance(value, dict):
        manifest[field] = dict(value)
        manifest[field]["tampered"] = True
    else:
        manifest[field] = f"{value}-tampered"
    result = validate_final_scheduler_freeze_manifest(manifest)
    assert result["freeze_manifest_valid"] is False
    assert result["failures"] == ["STEP13D_FREEZE_MANIFEST_EXACT_CONTRACT_MISMATCH"]


@pytest.mark.parametrize("value", [None, [], "manifest", 1, True])
def test_non_mapping_final_manifest_validation_fails_closed(value):
    result = validate_final_scheduler_freeze_manifest(value)
    assert result["freeze_manifest_valid"] is False
    assert result["failures"] == ["STEP13D_FREEZE_MANIFEST_NOT_MAPPING"]


def test_valid_final_manifest_exact_validation_is_green():
    result = validate_final_scheduler_freeze_manifest(final_scheduler_freeze_manifest())
    assert result["freeze_manifest_valid"] is True
    assert result["failures"] == []


def test_added_manifest_field_fails_exact_validation():
    manifest = final_scheduler_freeze_manifest()
    manifest["unexpected"] = True
    assert validate_final_scheduler_freeze_manifest(manifest)["freeze_manifest_valid"] is False


def test_removed_manifest_field_fails_exact_validation():
    manifest = final_scheduler_freeze_manifest()
    manifest.pop("runtime_mode")
    assert validate_final_scheduler_freeze_manifest(manifest)["freeze_manifest_valid"] is False


@pytest.mark.parametrize(
    "field",
    [
        "runtime_cycle_executed",
        "retry_executed",
        "restart_executed",
        "scheduler_state_mutated",
        "recovery_state_mutated",
        "network_io_performed",
        "production_scheduler_activation",
        "actionable_output_enabled",
    ],
)
def test_green_certification_performs_no_forbidden_action(field):
    assert validate_final_scheduler_freeze(**_valid_kwargs())[field] is False


def test_green_certification_has_zero_provider_calls_and_database_writes():
    result = validate_final_scheduler_freeze(**_valid_kwargs())
    assert result["provider_network_calls"] == 0
    assert result["production_database_writes"] == 0


def test_green_certification_embeds_exact_freeze_manifest():
    result = validate_final_scheduler_freeze(**_valid_kwargs())
    assert result["freeze_manifest"] == final_scheduler_freeze_manifest()


def test_green_certification_embeds_exact_parent_hashes():
    result = validate_final_scheduler_freeze(**_valid_kwargs())
    assert result["parent_manifest_sha256"] == final_scheduler_freeze_manifest()["parent_manifest_sha256"]


def test_green_certification_evidence_surface_is_exact():
    result = validate_final_scheduler_freeze(**_valid_kwargs())
    assert set(result["evidence"]) == {
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
    }
    assert all(value is True for value in result["evidence"].values())


def test_parent_manifests_remain_independently_deterministic():
    assert final_runtime_freeze_manifest() == final_runtime_freeze_manifest()
    assert bounded_scheduler_manifest() == bounded_scheduler_manifest()
    assert runtime_supervisor_manifest() == runtime_supervisor_manifest()
    assert reliability_recovery_manifest() == reliability_recovery_manifest()


def test_parent_runtime_modes_are_all_shadow_only():
    assert final_runtime_freeze_manifest()["runtime_mode"] == "SHADOW_ONLY"
    assert bounded_scheduler_manifest()["runtime_mode"] == "SHADOW_ONLY"
    assert runtime_supervisor_manifest()["runtime_mode"] == "SHADOW_ONLY"
    assert reliability_recovery_manifest()["runtime_mode"] == "SHADOW_ONLY"


def test_step13c_freeze_requirement_is_closed_by_step13d():
    assert reliability_recovery_manifest()["future_scheduler_freeze_required"] is True
    assert final_scheduler_freeze_manifest()["step13c_future_scheduler_freeze_requirement_satisfied"] is True


def test_final_freeze_does_not_claim_durable_cross_process_recovery():
    manifest = final_scheduler_freeze_manifest()
    assert manifest["durable_cross_process_recovery_added_by_step13d"] is False
    assert manifest["future_durable_recovery_persistence_step_required"] is True


def test_final_freeze_does_not_claim_always_on_activation():
    manifest = final_scheduler_freeze_manifest()
    assert manifest["always_on_runtime_added_by_step13d"] is False
    assert manifest["future_explicit_activation_step_required"] is True
