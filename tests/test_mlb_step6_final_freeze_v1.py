from __future__ import annotations

import copy

import pytest

from sports_api.mlb_step6_final_freeze_v1 import (
    DATA_TYPE,
    FINAL_CERTIFICATION_MARKER,
    FINAL_FREEZE_STATUS,
    FINAL_GRADUATION_STATUS,
    FINAL_PRODUCTION_PERCENT,
    MAX_PRODUCTION_PERCENT,
    MLBStep6FinalFreezeError,
    PROTECTED_INVARIANTS,
    SCHEMA_VERSION,
    STEP6H_BASE_MAIN_SHA,
    STEP6_CERTIFICATION_MARKERS,
    STEP6_STAGE_CHAIN,
    final_freeze_manifest,
    validate_final_step6_runtime,
)
from sports_api.mlb_step6d_production_expansion_v1 import (
    CERTIFIED_STEP6C_PERMISSION,
    KILL_SWITCH_ENV_KEY,
    resolve_step6d_production_expansion,
)
from sports_api.mlb_step6g_controlled_graduation_v1 import (
    CERTIFIED_STEP6F_DECISION,
    resolve_step6g_controlled_graduation,
)


def green_runtime():
    rollout = resolve_step6d_production_expansion({}, permission=CERTIFIED_STEP6C_PERMISSION)
    graduation = resolve_step6g_controlled_graduation(rollout, permission=CERTIFIED_STEP6F_DECISION)
    return rollout, graduation


def test_manifest_identity_and_final_status():
    manifest = final_freeze_manifest()
    assert manifest["data_type"] == DATA_TYPE
    assert manifest["schema_version"] == SCHEMA_VERSION == 1
    assert manifest["step6h_base_main_sha"] == STEP6H_BASE_MAIN_SHA
    assert manifest["final_production_percent"] == FINAL_PRODUCTION_PERCENT == 25.0
    assert manifest["max_production_percent"] == MAX_PRODUCTION_PERCENT == 25.0
    assert manifest["final_graduation_status"] == FINAL_GRADUATION_STATUS == "GRADUATED_PRODUCTION_ACTIVE"
    assert manifest["final_freeze_status"] == FINAL_FREEZE_STATUS
    assert manifest["final_certification_marker"] == FINAL_CERTIFICATION_MARKER


def test_stage_chain_is_exact_6a_through_6g():
    assert STEP6_STAGE_CHAIN == (
        "6A_PRODUCTION_CANARY_ACTIVATION",
        "6B_PRODUCTION_CANARY_MONITORING",
        "6C_EVIDENCE_GATED_EXPANSION",
        "6D_CONTROLLED_25_PERCENT_ACTIVATION",
        "6E_25_PERCENT_STABILITY_WINDOW",
        "6F_PRODUCTION_GRADUATION_GATE",
        "6G_CONTROLLED_PRODUCTION_GRADUATION",
    )
    assert len(STEP6_STAGE_CHAIN) == 7
    assert len(set(STEP6_STAGE_CHAIN)) == 7


def test_certification_marker_chain_is_complete_and_unique():
    assert len(STEP6_CERTIFICATION_MARKERS) == 7
    assert len(set(STEP6_CERTIFICATION_MARKERS)) == 7
    for label in ("STEP6A", "STEP6B", "STEP6C", "STEP6D", "STEP6E", "STEP6F", "STEP6G"):
        assert sum(label in marker for marker in STEP6_CERTIFICATION_MARKERS) == 1


def test_manifest_is_read_only_and_does_not_expand_exposure():
    manifest = final_freeze_manifest()
    assert manifest["read_only_freeze"] is True
    assert manifest["automatic_runtime_mutation"] is False
    assert manifest["production_exposure_changed"] is False
    assert manifest["exact_rollback_required"] is True
    assert manifest["final_production_percent"] <= manifest["max_production_percent"] == 25.0


def test_manifest_returns_fresh_lists():
    first = final_freeze_manifest()
    second = final_freeze_manifest()
    first["stage_chain"].append("BAD")
    first["certification_markers"].append("BAD")
    assert second["stage_chain"] == list(STEP6_STAGE_CHAIN)
    assert second["certification_markers"] == list(STEP6_CERTIFICATION_MARKERS)


@pytest.mark.parametrize("field", list(PROTECTED_INVARIANTS))
def test_all_protected_manifest_flags_are_false(field):
    assert PROTECTED_INVARIANTS[field] is False
    assert final_freeze_manifest()[field] is False


def test_certified_runtime_is_freeze_eligible():
    rollout, graduation = green_runtime()
    result = validate_final_step6_runtime(rollout, graduation)
    assert result["freeze_eligible"] is True
    assert result["freeze_status"] == FINAL_FREEZE_STATUS
    assert result["failures"] == []
    assert result["final_production_percent"] == 25.0
    assert result["production_exposure_changed"] is False


def test_validator_does_not_mutate_inputs():
    rollout, graduation = green_runtime()
    before_rollout = copy.deepcopy(rollout)
    before_graduation = copy.deepcopy(graduation)
    validate_final_step6_runtime(rollout, graduation)
    assert rollout == before_rollout
    assert graduation == before_graduation


@pytest.mark.parametrize("bad", [None, 1, 1.2, "x", [], (), object()])
def test_bad_step6d_input_is_rejected(bad):
    _, graduation = green_runtime()
    with pytest.raises(MLBStep6FinalFreezeError):
        validate_final_step6_runtime(bad, graduation)


@pytest.mark.parametrize("bad", [None, 1, 1.2, "x", [], (), object()])
def test_bad_step6g_input_is_rejected(bad):
    rollout, _ = green_runtime()
    with pytest.raises(MLBStep6FinalFreezeError):
        validate_final_step6_runtime(rollout, bad)


@pytest.mark.parametrize(
    "field,value,expected",
    [
        ("data_type", "wrong", "STEP6D_DATA_TYPE_MISMATCH"),
        ("schema_version", 2, "STEP6D_SCHEMA_VERSION_MISMATCH"),
        ("enabled", False, "STEP6D_NOT_ENABLED"),
        ("config_valid", False, "STEP6D_CONFIG_NOT_VALID"),
        ("exact_rollback", False, "STEP6D_EXACT_ROLLBACK_NOT_PRESERVED"),
        ("step6c_permission_valid", False, "STEP6C_PERMISSION_NOT_VALID"),
        ("effective_percent", 10.0, "STEP6D_PERCENT_NOT_25"),
        ("effective_percent", 26.0, "STEP6D_PERCENT_EXCEEDS_FINAL_CAP"),
        ("effective_percent", "bad", "STEP6D_PERCENT_INVALID"),
    ],
)
def test_step6d_runtime_drift_rejects_freeze(field, value, expected):
    rollout, graduation = green_runtime()
    rollout[field] = value
    result = validate_final_step6_runtime(rollout, graduation)
    assert result["freeze_eligible"] is False
    assert result["freeze_status"] == "STEP6_FREEZE_REJECTED"
    assert expected in result["failures"]


@pytest.mark.parametrize(
    "field,value,expected",
    [
        ("data_type", "wrong", "STEP6G_DATA_TYPE_MISMATCH"),
        ("schema_version", 2, "STEP6G_SCHEMA_VERSION_MISMATCH"),
        ("graduation_status", "CANARY_HOLD_AT_25_PERCENT", "STEP6G_NOT_GRADUATED_ACTIVE"),
        ("graduated_production_active", False, "STEP6G_GRADUATED_FLAG_NOT_ACTIVE"),
        ("canary_status_retired", False, "STEP6G_CANARY_STATUS_NOT_RETIRED"),
        ("step6f_permission_valid", False, "STEP6F_PERMISSION_NOT_VALID"),
        ("step6d_rollout_reused", False, "STEP6D_ROLLOUT_NOT_REUSED"),
        ("exact_rollback_preserved", False, "STEP6G_EXACT_ROLLBACK_NOT_PRESERVED"),
        ("production_exposure_changed", True, "STEP6G_EXPOSURE_CHANGED"),
        ("exposure_increase_authorized", True, "STEP6G_EXPOSURE_INCREASE_AUTHORIZED"),
        ("graduated_production_percent", 24.0, "STEP6G_PERCENT_NOT_25"),
        ("exposure_change_percent", 1.0, "STEP6G_EXPOSURE_CHANGE_NOT_ZERO"),
        ("graduated_production_percent", "bad", "STEP6G_PERCENT_FIELDS_INVALID"),
    ],
)
def test_step6g_runtime_drift_rejects_freeze(field, value, expected):
    rollout, graduation = green_runtime()
    graduation[field] = value
    result = validate_final_step6_runtime(rollout, graduation)
    assert result["freeze_eligible"] is False
    assert expected in result["failures"]


def test_step6g_failures_reject_freeze():
    rollout, graduation = green_runtime()
    graduation["failures"] = ["FORCED"]
    result = validate_final_step6_runtime(rollout, graduation)
    assert "STEP6G_FAILURES_PRESENT" in result["failures"]


def test_global_kill_switch_remains_exact_rollback_and_not_frozen_active():
    rollout = resolve_step6d_production_expansion(
        {KILL_SWITCH_ENV_KEY: "1"}, permission=CERTIFIED_STEP6C_PERMISSION
    )
    graduation = resolve_step6g_controlled_graduation(rollout, permission=CERTIFIED_STEP6F_DECISION)
    assert rollout["effective_percent"] == 0.0
    assert rollout["exact_rollback"] is True
    assert graduation["graduation_status"] == "GRADUATED_PRODUCTION_ROLLBACK"
    assert graduation["exact_rollback_preserved"] is True
    assert validate_final_step6_runtime(rollout, graduation)["freeze_eligible"] is False


def test_session_rollback_remains_exact_and_not_frozen_active():
    rollout = resolve_step6d_production_expansion(
        {}, rollback_requested=True, permission=CERTIFIED_STEP6C_PERMISSION
    )
    graduation = resolve_step6g_controlled_graduation(rollout, permission=CERTIFIED_STEP6F_DECISION)
    assert rollout["effective_percent"] == 0.0
    assert rollout["control_source"] == "STREAMLIT_SESSION_ROLLBACK"
    assert graduation["graduation_status"] == "GRADUATED_PRODUCTION_ROLLBACK"
    assert validate_final_step6_runtime(rollout, graduation)["freeze_eligible"] is False


def test_degraded_graduation_permission_holds_at_25_without_exposure_change():
    rollout, _ = green_runtime()
    permission = dict(CERTIFIED_STEP6F_DECISION)
    permission["decision"] = "HOLD_AT_25_PERCENT"
    graduation = resolve_step6g_controlled_graduation(rollout, permission=permission)
    assert graduation["graduation_status"] == "CANARY_HOLD_AT_25_PERCENT"
    assert graduation["graduated_production_active"] is False
    assert graduation["step6d_effective_percent"] == 25.0
    assert graduation["production_exposure_changed"] is False
    assert validate_final_step6_runtime(rollout, graduation)["freeze_eligible"] is False
