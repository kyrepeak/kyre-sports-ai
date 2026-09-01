from __future__ import annotations

from copy import deepcopy
import hashlib
import json

import pytest

from sports_api.mlb_step9_final_freeze_v1 import PROTECTED_INVARIANTS
from sports_api.mlb_step13_final_scheduler_freeze_v1 import final_scheduler_freeze_manifest
from sports_api import mlb_step14a_persistence_contract_v1 as step14a
from sports_api import mlb_step14b_database_checkpoint_adapter_v1 as step14b
from sports_api import mlb_step14c_durable_restart_lease_v1 as step14c
from sports_api import mlb_step14_final_persistence_freeze_v1 as s14d


def _hash(value):
    raw = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _parents():
    return {
        "step13d_manifest": final_scheduler_freeze_manifest(),
        "step14a_manifest": step14a.persistence_contract_manifest(),
        "step14b_manifest": step14b.database_checkpoint_adapter_manifest(),
        "step14c_manifest": step14c.durable_restart_lease_manifest(),
    }


def _evidence():
    return {
        "step14a_contract_evidence_ok": True,
        "step14b_adapter_evidence_ok": True,
        "step14c_restart_restore_evidence_ok": True,
        "step14c_duplicate_lease_fencing_evidence_ok": True,
        "step14c_lost_lease_fencing_evidence_ok": True,
        "checkpoint_cas_evidence_ok": True,
        "append_only_history_evidence_ok": True,
        "zero_parent_drift_ok": True,
        "zero_runtime_retry_restart_execution_ok": True,
        "zero_provider_sportsbook_calls_ok": True,
        "zero_live_database_connections_ok": True,
        "zero_production_activation_ok": True,
        "zero_actionable_output_ok": True,
    }


def _certify(**overrides):
    kwargs = {**_parents(), **_evidence()}
    kwargs.update(overrides)
    return s14d.validate_final_persistence_freeze(**kwargs)


def test_step14d_identity_constants_are_pinned():
    assert s14d.DATA_TYPE == "mlb_step14_final_persistence_freeze_v1"
    assert s14d.CERTIFICATION_DATA_TYPE == "mlb_step14d_final_persistence_certification_v1"
    assert s14d.SCHEMA_VERSION == 1
    assert s14d.STEP14D_BASE_MAIN_SHA == "9435d9db84b34a276281b2528205030ac27dd3c6"
    assert s14d.FINAL_FREEZE_STATUS == "STEP14_FROZEN_DURABLE_PERSISTENCE_COMPLETE"
    assert s14d.RUNTIME_MODE == "SHADOW_ONLY"
    assert s14d.FINAL_CERTIFICATION_MARKER == "MLB_STEP14D_FINAL_PERSISTENCE_FREEZE_GREEN"
    assert s14d.RELEASE_ID == "mlb_step14_durable_persistence_restart_lease_2026_frozen_v1"


def test_step14_stage_chain_is_exact():
    assert s14d.STEP14_STAGE_CHAIN == (
        "14A_PERSISTENCE_CONTRACT",
        "14B_DATABASE_CHECKPOINT_ADAPTER",
        "14C_DURABLE_RESTART_LEASE",
    )


def test_step14_markers_are_exact():
    assert s14d.STEP14_CERTIFICATION_MARKERS == (
        "MLB_STEP14A_PERSISTENCE_CONTRACT_GREEN",
        "MLB_STEP14B_DATABASE_CHECKPOINT_ADAPTER_GREEN",
        "MLB_STEP14C_DURABLE_RESTART_LEASE_GREEN",
    )


def test_step14_parent_merge_shas_are_exact():
    assert s14d.STEP14_PARENT_MERGE_SHAS == {
        "step14a_merge_sha": "3dae5181571dbfea45f6f0db87e916d25e971170",
        "step14b_merge_sha": "195df0c15de1998754204080f9db4a76bca74e4b",
        "step14c_merge_sha": "9435d9db84b34a276281b2528205030ac27dd3c6",
    }


def test_frozen_parent_source_blobs_are_exact():
    assert s14d.FROZEN_PARENT_SOURCE_BLOBS == {
        "step13_final_scheduler_freeze_blob": "b53400fe205717ca075231f841b4ca7aabed90bc",
        "step14a_persistence_contract_blob": "373996a35959e5ad2252325062b250ddffd4286c",
        "step14a_persistence_schema_blob": "969c88c529486c8cde54f7928919e2a393a0f588",
        "step14b_database_checkpoint_adapter_blob": "ee7ffe3117edc33b1377f883c25613d63760095b",
        "step14c_durable_restart_lease_blob": "2ea48e2badc73750f96cc8d3b5ef3927fb40a08e",
        "step14c_runtime_lease_schema_blob": "e341e41ae7b21d1781c0b96be05ad924fcccab86",
    }


@pytest.mark.parametrize(
    "manifest,validator,key",
    [
        (final_scheduler_freeze_manifest(), s14d.validate_final_persistence_freeze_manifest, "step13d"),
        (step14a.persistence_contract_manifest(), step14a.validate_persistence_contract_manifest, "step14a"),
        (step14b.database_checkpoint_adapter_manifest(), step14b.validate_database_checkpoint_adapter_manifest, "step14b"),
        (step14c.durable_restart_lease_manifest(), step14c.validate_durable_restart_lease_manifest, "step14c"),
    ],
)
def test_parent_manifests_exist_and_are_mappings(manifest, validator, key):
    assert isinstance(manifest, dict)
    assert key.startswith("step")
    if key != "step13d":
        assert validator(manifest)["manifest_valid"] is True


def test_step13d_parent_manifest_validates():
    from sports_api.mlb_step13_final_scheduler_freeze_v1 import validate_final_scheduler_freeze_manifest
    result = validate_final_scheduler_freeze_manifest(final_scheduler_freeze_manifest())
    assert result["freeze_manifest_valid"] is True


def test_final_manifest_validates_exactly():
    manifest = s14d.final_persistence_freeze_manifest()
    result = s14d.validate_final_persistence_freeze_manifest(manifest)
    assert result == {
        "data_type": s14d.DATA_TYPE,
        "schema_version": 1,
        "freeze_manifest_valid": True,
        "failures": [],
    }


def test_final_manifest_is_deterministic():
    assert s14d.final_persistence_freeze_manifest() == s14d.final_persistence_freeze_manifest()


def test_final_manifest_hash_is_exact_surface_hash():
    manifest = s14d.final_persistence_freeze_manifest()
    surface = deepcopy(manifest)
    observed = surface.pop("freeze_manifest_sha256")
    assert observed == _hash(surface)
    assert len(observed) == 64


def test_final_manifest_tamper_fails_validation():
    manifest = s14d.final_persistence_freeze_manifest()
    manifest["runtime_mode"] = "TAMPERED"
    result = s14d.validate_final_persistence_freeze_manifest(manifest)
    assert result["freeze_manifest_valid"] is False
    assert result["failures"] == ["STEP14D_FREEZE_MANIFEST_EXACT_CONTRACT_MISMATCH"]


def test_non_mapping_manifest_fails_closed():
    result = s14d.validate_final_persistence_freeze_manifest(None)
    assert result["freeze_manifest_valid"] is False
    assert result["failures"] == ["STEP14D_FREEZE_MANIFEST_NOT_MAPPING"]


TRUE_CAPABILITIES = (
    "step14_durable_persistence_block_frozen",
    "step14a_persistence_contract_frozen",
    "step14b_database_checkpoint_adapter_frozen",
    "step14c_durable_restart_lease_frozen",
    "step14c_future_step14d_requirement_satisfied",
    "exact_parent_manifests_required",
    "exact_parent_source_blobs_required",
    "postgresql_checkpoint_adapter_certified",
    "append_only_checkpoint_history_certified",
    "checkpoint_head_compare_and_swap_certified",
    "deterministic_checkpoint_identity_certified",
    "exact_scheduler_state_restart_restore_certified",
    "exact_recovery_state_restart_restore_certified",
    "exact_recovery_handoff_restart_restore_certified",
    "fresh_start_without_checkpoint_certified",
    "durable_restart_recovery_certified",
    "durable_distributed_lease_certified",
    "cross_process_duplicate_run_guard_certified",
    "uuid_lease_ownership_token_certified",
    "monotonic_fencing_generation_certified",
    "lease_expiry_and_takeover_certified",
    "stale_owner_fencing_certified",
    "lease_revalidation_before_checkpoint_save_certified",
    "checkpoint_persist_under_valid_lease_certified",
    "foreground_only_certified",
    "explicit_invocation_required",
    "future_step15_live_postgres_preflight_required",
    "future_explicit_production_activation_step_required",
)


@pytest.mark.parametrize("key", TRUE_CAPABILITIES)
def test_final_manifest_certified_capabilities_are_true(key):
    assert s14d.final_persistence_freeze_manifest()[key] is True


FALSE_CAPABILITIES = (
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
)


@pytest.mark.parametrize("key", FALSE_CAPABILITIES)
def test_final_manifest_forbidden_capabilities_are_false(key):
    assert s14d.final_persistence_freeze_manifest()[key] is False


@pytest.mark.parametrize("key", sorted(PROTECTED_INVARIANTS))
def test_final_manifest_preserves_every_step9_protected_invariant(key):
    assert PROTECTED_INVARIANTS[key] is False
    assert s14d.final_persistence_freeze_manifest()[key] is False


def test_final_manifest_storage_names_are_exact():
    manifest = s14d.final_persistence_freeze_manifest()
    assert manifest["database_schema_name"] == "kyre_runtime"
    assert manifest["checkpoint_table_name"] == "mlb_runtime_checkpoints"
    assert manifest["checkpoint_head_table_name"] == "mlb_runtime_checkpoint_heads"
    assert manifest["lease_table_name"] == "mlb_runtime_leases"


def test_final_manifest_schema_paths_are_exact():
    manifest = s14d.final_persistence_freeze_manifest()
    assert manifest["step14a_sql_schema_path"] == "sports_api/sql/mlb_step14a_persistence_schema.sql"
    assert manifest["step14c_lease_sql_schema_path"] == "sports_api/sql/mlb_step14c_runtime_lease_schema.sql"
    assert manifest["step14c_lease_sql_schema_sha256"] == step14c.LEASE_SQL_SCHEMA_SHA256


@pytest.mark.parametrize(
    "key,expected",
    [
        ("default_lease_ttl_seconds", 300),
        ("minimum_lease_ttl_seconds", 60),
        ("maximum_lease_ttl_seconds", 3600),
    ],
)
def test_final_manifest_lease_bounds_are_pinned(key, expected):
    assert s14d.final_persistence_freeze_manifest()[key] == expected


def test_parent_manifest_hashes_match_exact_current_parents():
    manifest = s14d.final_persistence_freeze_manifest()
    expected = {
        "step13d": _hash(final_scheduler_freeze_manifest()),
        "step14a": _hash(step14a.persistence_contract_manifest()),
        "step14b": _hash(step14b.database_checkpoint_adapter_manifest()),
        "step14c": _hash(step14c.durable_restart_lease_manifest()),
    }
    assert manifest["parent_manifest_sha256"] == expected


def test_successful_certification_is_green():
    result = _certify()
    assert result["certified"] is True
    assert result["failures"] == []
    assert result["final_freeze_status"] == s14d.FINAL_FREEZE_STATUS
    assert result["final_certification_marker"] == s14d.FINAL_CERTIFICATION_MARKER


def test_successful_certification_hash_is_exact():
    result = _certify()
    surface = deepcopy(result)
    observed = surface.pop("certification_sha256")
    assert observed == _hash(surface)
    assert len(observed) == 64


def test_successful_certification_is_deterministic():
    assert _certify() == _certify()


@pytest.mark.parametrize("key", tuple(_evidence()))
def test_each_missing_certification_evidence_fails_closed(key):
    result = _certify(**{key: False})
    assert result["certified"] is False
    assert f"{key.upper()}_REQUIRED" in result["failures"]
    assert result["final_certification_marker"] is None
    assert result["final_freeze_status"] == "NOT_CERTIFIED"


@pytest.mark.parametrize(
    "parent_key,failure",
    [
        ("step13d_manifest", "STEP13D_MANIFEST_MISMATCH"),
        ("step14a_manifest", "STEP14A_MANIFEST_MISMATCH"),
        ("step14b_manifest", "STEP14B_MANIFEST_MISMATCH"),
        ("step14c_manifest", "STEP14C_MANIFEST_MISMATCH"),
    ],
)
def test_parent_manifest_tamper_fails_certification(parent_key, failure):
    parents = _parents()
    tampered = deepcopy(parents[parent_key])
    tampered["runtime_mode"] = "TAMPERED"
    result = _certify(**{parent_key: tampered})
    assert result["certified"] is False
    assert failure in result["failures"]


@pytest.mark.parametrize(
    "parent_key,failure",
    [
        ("step13d_manifest", "STEP13D_MANIFEST_MISMATCH"),
        ("step14a_manifest", "STEP14A_MANIFEST_MISMATCH"),
        ("step14b_manifest", "STEP14B_MANIFEST_MISMATCH"),
        ("step14c_manifest", "STEP14C_MANIFEST_MISMATCH"),
    ],
)
def test_missing_parent_manifest_fails_certification(parent_key, failure):
    result = _certify(**{parent_key: None})
    assert result["certified"] is False
    assert failure in result["failures"]


@pytest.mark.parametrize(
    "key,expected",
    [
        ("runtime_cycle_executed", False),
        ("retry_executed", False),
        ("restart_executed", False),
        ("lease_operation_executed", False),
        ("checkpoint_read_executed", False),
        ("checkpoint_write_executed", False),
        ("network_io_performed", False),
        ("provider_network_calls", 0),
        ("sportsbook_network_calls", 0),
        ("live_database_connections", 0),
        ("production_database_writes", 0),
        ("production_runtime_activation", False),
        ("production_scheduler_activation", False),
        ("actionable_output_enabled", False),
    ],
)
def test_certification_reports_zero_side_effect_boundary(key, expected):
    assert _certify()[key] == expected


def test_certification_embeds_exact_freeze_manifest():
    assert _certify()["freeze_manifest"] == s14d.final_persistence_freeze_manifest()


def test_certification_embeds_all_true_evidence():
    assert _certify()["evidence"] == _evidence()


def test_certification_parent_hashes_match_manifest_parent_hashes():
    result = _certify()
    manifest = s14d.final_persistence_freeze_manifest()
    assert result["parent_manifest_sha256"] == manifest["parent_manifest_sha256"]


def test_step14a_boundary_is_still_definition_only():
    assert step14a.DATABASE_READ_ALLOWED is False
    assert step14a.DATABASE_WRITE_ALLOWED is False
    assert step14a.PERSISTENCE_RUNTIME_ENABLED is False
    assert step14a.DURABLE_RESTART_RECOVERY_ALLOWED is False
    assert step14a.DURABLE_DISTRIBUTED_LEASE_ALLOWED is False


def test_step14b_boundary_is_isolated_adapter_only():
    assert step14b.POSTGRESQL_DATABASE_READ_ALLOWED is True
    assert step14b.POSTGRESQL_DATABASE_WRITE_ALLOWED is True
    assert step14b.CHECKPOINT_LOAD_ALLOWED is True
    assert step14b.CHECKPOINT_SAVE_ALLOWED is True
    assert step14b.ATOMIC_HEAD_COMPARE_AND_SWAP_ALLOWED is True
    assert step14b.APPEND_ONLY_HISTORY_REQUIRED is True
    assert step14b.PERSISTENCE_RUNTIME_ENABLED is False
    assert step14b.DURABLE_RESTART_RECOVERY_ALLOWED is False
    assert step14b.DURABLE_DISTRIBUTED_LEASE_ALLOWED is False
    assert step14b.CROSS_PROCESS_DUPLICATE_RUN_GUARD_ALLOWED is False


def test_step14c_boundary_is_foreground_durable_ownership_only():
    assert step14c.FOREGROUND_DURABLE_RESTART_CONTEXT_ALLOWED is True
    assert step14c.DURABLE_RESTART_RECOVERY_ALLOWED is True
    assert step14c.DURABLE_DISTRIBUTED_LEASE_ALLOWED is True
    assert step14c.CROSS_PROCESS_DUPLICATE_RUN_GUARD_ALLOWED is True
    assert step14c.FENCING_GENERATION_REQUIRED is True
    assert step14c.LEASE_EXPIRY_REQUIRED is True
    assert step14c.LEASE_REVALIDATION_BEFORE_SAVE_REQUIRED is True
    assert step14c.CHECKPOINT_CAS_REQUIRED is True
    assert step14c.PERSISTENCE_RUNTIME_ENABLED is False
    assert step14c.AUTOMATIC_RESTART_EXECUTION_ALLOWED is False
    assert step14c.PRODUCTION_ACTIVATION_ALLOWED is False
    assert step14c.BACKGROUND_WORKER_ALLOWED is False
    assert step14c.BACKGROUND_THREAD_ALLOWED is False


def test_final_freeze_does_not_relax_step13_shadow_only_boundary():
    manifest = s14d.final_persistence_freeze_manifest()
    assert manifest["runtime_mode"] == "SHADOW_ONLY"
    assert manifest["step13d_runtime_mode_required"] == "SHADOW_ONLY"
    assert manifest["step13d_final_certification_marker_required"] == "MLB_STEP13D_FINAL_SCHEDULER_FREEZE_GREEN"


def test_final_freeze_marks_step14_complete_but_activation_not_started():
    manifest = s14d.final_persistence_freeze_manifest()
    assert manifest["step14_durable_persistence_block_frozen"] is True
    assert manifest["production_runtime_activation_allowed"] is False
    assert manifest["production_scheduler_activation_allowed"] is False
    assert manifest["future_step15_live_postgres_preflight_required"] is True


def test_deep_copy_isolation_for_manifest_nested_structures():
    first = s14d.final_persistence_freeze_manifest()
    second = s14d.final_persistence_freeze_manifest()
    first["step14_parent_merge_shas"]["step14a_merge_sha"] = "x"
    first["frozen_parent_source_blobs"]["step14a_persistence_contract_blob"] = "x"
    first["parent_manifest_sha256"]["step14a"] = "x"
    assert first != second
    assert second == s14d.final_persistence_freeze_manifest()


def test_deep_copy_isolation_for_certification_result():
    first = _certify()
    second = _certify()
    first["evidence"]["step14a_contract_evidence_ok"] = False
    first["freeze_manifest"]["release_id"] = "tampered"
    assert second == _certify()


def test_release_id_is_content_stable_across_rebuilds():
    a = s14d.final_persistence_freeze_manifest()
    b = s14d.final_persistence_freeze_manifest()
    assert a["release_id"] == b["release_id"] == s14d.RELEASE_ID
    assert a["freeze_manifest_sha256"] == b["freeze_manifest_sha256"]


def test_all_parent_markers_are_carried_into_final_manifest():
    manifest = s14d.final_persistence_freeze_manifest()
    assert manifest["step14_certification_markers"] == list(s14d.STEP14_CERTIFICATION_MARKERS)
    assert manifest["step14a_final_certification_marker_required"] == step14a.FINAL_CERTIFICATION_MARKER
    assert manifest["step14b_final_certification_marker_required"] == step14b.FINAL_CERTIFICATION_MARKER
    assert manifest["step14c_final_certification_marker_required"] == step14c.FINAL_CERTIFICATION_MARKER


def test_exact_parent_source_blob_requirement_is_explicit():
    manifest = s14d.final_persistence_freeze_manifest()
    assert manifest["exact_parent_source_blobs_required"] is True
    assert len(manifest["frozen_parent_source_blobs"]) == 6
    assert all(len(value) == 40 for value in manifest["frozen_parent_source_blobs"].values())


def test_exact_parent_manifest_requirement_is_explicit():
    manifest = s14d.final_persistence_freeze_manifest()
    assert manifest["exact_parent_manifests_required"] is True
    assert set(manifest["parent_manifest_sha256"]) == {"step13d", "step14a", "step14b", "step14c"}
    assert all(len(value) == 64 for value in manifest["parent_manifest_sha256"].values())


def test_step14d_adds_no_database_or_network_execution_api():
    exported = set(s14d.__all__)
    forbidden_fragments = ("connect", "acquire", "renew", "release_lease", "save", "load", "run_runtime", "execute")
    for name in exported:
        assert not any(fragment in name for fragment in forbidden_fragments)


def test_step14d_exports_only_freeze_contract_surface():
    assert set(s14d.__all__) == {
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
    }
