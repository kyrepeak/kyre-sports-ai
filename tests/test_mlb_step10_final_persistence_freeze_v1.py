from copy import deepcopy

import pytest

from sports_api.mlb_step9_final_freeze_v1 import PROTECTED_INVARIANTS
from sports_api.mlb_step10a_live_snapshot_persistence_contract_v1 import (
    persistence_contract_manifest,
)
from sports_api.database.mlb_live_snapshot_store import adapter_manifest
from sports_api.database.mlb_live_snapshot_recovery import recovery_manifest
from sports_api.mlb_step10_final_persistence_freeze_v1 import (
    ACTIVATION_REQUIREMENTS,
    DATA_TYPE,
    FINAL_CERTIFICATION_MARKER,
    FINAL_FREEZE_STATUS,
    SCHEMA_VERSION,
    STEP10_CERTIFICATION_MARKERS,
    STEP10_STAGE_CHAIN,
    STEP10D_BASE_MAIN_SHA,
    final_persistence_freeze_manifest,
    validate_final_persistence_freeze,
)


def _green(**overrides):
    kwargs = {
        "step10a_manifest": persistence_contract_manifest(),
        "step10b_manifest": adapter_manifest(),
        "step10c_manifest": recovery_manifest(),
        "append_only_evidence_ok": True,
        "restart_recovery_evidence_ok": True,
        "zero_production_writes_ok": True,
    }
    kwargs.update(overrides)
    return validate_final_persistence_freeze(**kwargs)


def test_manifest_anchors_exact_step10c_merge_and_final_freeze_identity():
    m = final_persistence_freeze_manifest()
    assert m["data_type"] == DATA_TYPE == "mlb_step10_final_persistence_freeze_v1"
    assert m["schema_version"] == SCHEMA_VERSION == 1
    assert m["step10d_base_main_sha"] == STEP10D_BASE_MAIN_SHA == "a043c6a1cd0a68540332f01da15f350d3fb2b0b9"
    assert m["final_freeze_status"] == FINAL_FREEZE_STATUS
    assert m["final_certification_marker"] == FINAL_CERTIFICATION_MARKER


def test_manifest_freezes_exact_step10_chain_and_markers():
    m = final_persistence_freeze_manifest()
    assert tuple(m["step10_stage_chain"]) == STEP10_STAGE_CHAIN
    assert tuple(m["step10_certification_markers"]) == STEP10_CERTIFICATION_MARKERS
    assert STEP10_STAGE_CHAIN == (
        "10A_DURABLE_LIVE_SNAPSHOT_PERSISTENCE_CONTRACT",
        "10B_APPEND_ONLY_LIVE_SNAPSHOT_STORE",
        "10C_DURABLE_RESTART_RECOVERY",
    )


def test_manifest_freezes_all_three_persistence_layers():
    m = final_persistence_freeze_manifest()
    assert m["persistence_block_frozen"] is True
    assert m["step10a_contract_frozen"] is True
    assert m["step10b_adapter_frozen"] is True
    assert m["step10c_recovery_frozen"] is True


def test_manifest_preserves_append_only_guards():
    m = final_persistence_freeze_manifest()
    assert m["append_only_required"] is True
    assert m["update_allowed"] is False
    assert m["upsert_allowed"] is False
    assert m["delete_allowed"] is False
    assert m["backfill_fabrication_allowed"] is False


def test_manifest_requires_restart_and_integrity_verification():
    m = final_persistence_freeze_manifest()
    assert m["restart_recovery_required"] is True
    assert m["read_only_recovery_required"] is True
    assert m["sqlite_integrity_check_required"] is True
    assert m["payload_sha256_reverification_required"] is True


def test_step10d_does_not_activate_production_writes_or_runtime_wiring():
    m = final_persistence_freeze_manifest()
    assert m["production_runtime_wiring_added_by_step10d"] is False
    assert m["automatic_production_writes_enabled"] is False
    assert m["production_activation_allowed_by_step10d"] is False
    assert m["explicit_future_activation_step_required"] is True


def test_future_activation_boundary_is_complete_and_unique():
    m = final_persistence_freeze_manifest()
    assert tuple(m["activation_requirements"]) == ACTIVATION_REQUIREMENTS
    assert len(ACTIVATION_REQUIREMENTS) == len(set(ACTIVATION_REQUIREMENTS))
    assert "startup_recovery_verification_required" in ACTIVATION_REQUIREMENTS
    assert "rollback_or_disable_switch_required" in ACTIVATION_REQUIREMENTS
    assert "production_smoke_certification_required" in ACTIVATION_REQUIREMENTS
    assert "no_fabricated_market_records_required" in ACTIVATION_REQUIREMENTS


def test_persisted_snapshots_remain_forbidden_as_model_or_sportsbook_inputs():
    m = final_persistence_freeze_manifest()
    assert m["persisted_snapshot_as_model_input_allowed"] is False
    assert m["persisted_snapshot_as_sportsbook_input_allowed"] is False


def test_all_protected_model_runtime_invariants_remain_false():
    m = final_persistence_freeze_manifest()
    for key, value in PROTECTED_INVARIANTS.items():
        assert value is False
        assert m[key] is False


def test_exact_prerequisite_manifests_and_green_evidence_pass():
    result = _green()
    assert result["freeze_valid"] is True
    assert result["failures"] == []
    assert result["append_only_evidence_ok"] is True
    assert result["restart_recovery_evidence_ok"] is True
    assert result["zero_production_writes_ok"] is True


def test_tampered_step10a_manifest_rejected():
    bad = persistence_contract_manifest()
    bad["append_only_required"] = False
    result = _green(step10a_manifest=bad)
    assert result["freeze_valid"] is False
    assert "STEP10D_STEP10A_MANIFEST_MISMATCH" in result["failures"]


def test_tampered_step10b_manifest_rejected():
    bad = adapter_manifest()
    bad["update_allowed"] = True
    result = _green(step10b_manifest=bad)
    assert result["freeze_valid"] is False
    assert "STEP10D_STEP10B_MANIFEST_MISMATCH" in result["failures"]


def test_tampered_step10c_manifest_rejected():
    bad = recovery_manifest()
    bad["read_only_database_open"] = False
    result = _green(step10c_manifest=bad)
    assert result["freeze_valid"] is False
    assert "STEP10D_STEP10C_MANIFEST_MISMATCH" in result["failures"]


@pytest.mark.parametrize(
    ("field", "failure"),
    [
        ("append_only_evidence_ok", "STEP10D_APPEND_ONLY_EVIDENCE_NOT_GREEN"),
        ("restart_recovery_evidence_ok", "STEP10D_RESTART_RECOVERY_EVIDENCE_NOT_GREEN"),
        ("zero_production_writes_ok", "STEP10D_ZERO_PRODUCTION_WRITES_NOT_GREEN"),
    ],
)
def test_each_required_evidence_flag_fails_closed(field, failure):
    result = _green(**{field: False})
    assert result["freeze_valid"] is False
    assert failure in result["failures"]


@pytest.mark.parametrize("truthy", [1, "yes", [True], {"ok": True}])
def test_truthy_non_boolean_evidence_is_rejected(truthy):
    result = _green(append_only_evidence_ok=truthy)
    assert result["freeze_valid"] is False
    assert "STEP10D_APPEND_ONLY_EVIDENCE_NOT_GREEN" in result["failures"]


def test_multiple_failures_are_reported_without_short_circuiting():
    result = validate_final_persistence_freeze(
        step10a_manifest=None,
        step10b_manifest=None,
        step10c_manifest=None,
        append_only_evidence_ok=False,
        restart_recovery_evidence_ok=False,
        zero_production_writes_ok=False,
    )
    assert result["freeze_valid"] is False
    assert len(result["failures"]) == 6


def test_validation_does_not_mutate_input_manifests():
    a = persistence_contract_manifest()
    b = adapter_manifest()
    c = recovery_manifest()
    originals = (deepcopy(a), deepcopy(b), deepcopy(c))
    validate_final_persistence_freeze(
        step10a_manifest=a,
        step10b_manifest=b,
        step10c_manifest=c,
        append_only_evidence_ok=True,
        restart_recovery_evidence_ok=True,
        zero_production_writes_ok=True,
    )
    assert (a, b, c) == originals


def test_manifest_nested_lists_are_isolated_across_calls():
    first = final_persistence_freeze_manifest()
    second = final_persistence_freeze_manifest()
    first["step10_stage_chain"].append("BAD")
    first["step10_certification_markers"].append("BAD")
    first["activation_requirements"].append("BAD")
    assert tuple(second["step10_stage_chain"]) == STEP10_STAGE_CHAIN
    assert tuple(second["step10_certification_markers"]) == STEP10_CERTIFICATION_MARKERS
    assert tuple(second["activation_requirements"]) == ACTIVATION_REQUIREMENTS
