from __future__ import annotations

from copy import deepcopy

import pytest

from sports_api.mlb_step9_final_freeze_v1 import PROTECTED_INVARIANTS
from sports_api.mlb_step11_final_provider_expansion_freeze_v1 import (
    FINAL_CERTIFICATION_MARKER as STEP11_MARKER,
    FINAL_FREEZE_STATUS as STEP11_STATUS,
    final_provider_expansion_freeze_manifest,
)
from sports_api.mlb_step12a_shadow_runtime_runner_v1 import (
    FINAL_CERTIFICATION_MARKER as STEP12A_MARKER,
    RUNTIME_MODE as STEP12A_MODE,
    RUNTIME_STATUS as STEP12A_STATUS,
    shadow_runtime_manifest,
)
from sports_api.mlb_step12b_live_runtime_assembly_v1 import (
    ASSEMBLY_STATUS as STEP12B_STATUS,
    FINAL_CERTIFICATION_MARKER as STEP12B_MARKER,
    RUNTIME_MODE as STEP12B_MODE,
    live_runtime_assembly_manifest,
)
from sports_api.mlb_step12c_live_board_runtime_v1 import (
    BOARD_STATUS as STEP12C_STATUS,
    FINAL_CERTIFICATION_MARKER as STEP12C_MARKER,
    RUNTIME_MODE as STEP12C_MODE,
    live_board_runtime_manifest,
)
from sports_api.mlb_step12_final_runtime_freeze_v1 import (
    DATA_TYPE,
    FINAL_CERTIFICATION_MARKER,
    FINAL_FREEZE_STATUS,
    FUTURE_RUNTIME_ACTIVATION_REQUIREMENTS,
    RUNTIME_MODE,
    SCHEMA_VERSION,
    STEP12_CERTIFICATION_MARKERS,
    STEP12_STAGE_CHAIN,
    STEP12D_BASE_MAIN_SHA,
    final_runtime_freeze_manifest,
    validate_final_runtime_freeze,
)

BASE_SHA = "fc3eacbda9162cf1bd0abd6ec30c6368a9df767b"


def _valid_kwargs():
    return {
        "step11_manifest": final_provider_expansion_freeze_manifest(),
        "step12a_manifest": shadow_runtime_manifest(),
        "step12b_manifest": live_runtime_assembly_manifest(),
        "step12c_manifest": live_board_runtime_manifest(),
        "shadow_runtime_evidence_ok": True,
        "exact_game_assembly_evidence_ok": True,
        "live_board_evidence_ok": True,
        "zero_actionable_rows_ok": True,
        "zero_live_secondary_provider_calls_ok": True,
        "zero_price_fabrication_ok": True,
        "zero_production_consensus_failover_ok": True,
        "zero_production_runtime_changes_ok": True,
        "zero_production_database_writes_ok": True,
    }


def test_constants_are_exact():
    assert DATA_TYPE == "mlb_step12_final_runtime_freeze_v1"
    assert SCHEMA_VERSION == 1
    assert STEP12D_BASE_MAIN_SHA == BASE_SHA
    assert FINAL_FREEZE_STATUS == "STEP12_FROZEN_SHADOW_RUNTIME_COMPLETE"
    assert RUNTIME_MODE == "SHADOW_ONLY"
    assert FINAL_CERTIFICATION_MARKER == "MLB_STEP12D_FINAL_RUNTIME_FREEZE_GREEN"


def test_stage_chain_is_exact_and_complete():
    assert STEP12_STAGE_CHAIN == (
        "12A_DETERMINISTIC_SHADOW_RUNTIME_RUNNER",
        "12B_EXACT_GAME_LIVE_RUNTIME_ASSEMBLY",
        "12C_DETERMINISTIC_LIVE_BOARD_RUNTIME",
    )


def test_certification_markers_are_exact():
    assert STEP12_CERTIFICATION_MARKERS == (
        STEP12A_MARKER,
        STEP12B_MARKER,
        STEP12C_MARKER,
    )


def test_manifest_pins_upstream_statuses_and_markers():
    manifest = final_runtime_freeze_manifest()
    assert manifest["step11_final_freeze_status_required"] == STEP11_STATUS
    assert manifest["step11_final_certification_marker_required"] == STEP11_MARKER
    assert manifest["step12a_runtime_status_required"] == STEP12A_STATUS
    assert manifest["step12a_runtime_mode_required"] == STEP12A_MODE
    assert manifest["step12b_assembly_status_required"] == STEP12B_STATUS
    assert manifest["step12b_runtime_mode_required"] == STEP12B_MODE
    assert manifest["step12c_board_status_required"] == STEP12C_STATUS
    assert manifest["step12c_runtime_mode_required"] == STEP12C_MODE


@pytest.mark.parametrize(
    "key",
    [
        "runtime_block_frozen",
        "step12a_shadow_runtime_frozen",
        "step12b_exact_game_assembly_frozen",
        "step12c_live_board_runtime_frozen",
        "deterministic_runtime_required",
        "exact_official_game_id_required",
        "freshness_gate_required",
        "source_complete_gate_required",
        "same_line_required_for_run_line_total_consensus",
        "observational_only",
        "explicit_future_activation_step_required",
    ],
)
def test_manifest_required_guards_are_true(key):
    assert final_runtime_freeze_manifest()[key] is True


@pytest.mark.parametrize(
    "key",
    [
        "actionable_output_enabled",
        "live_secondary_provider_network_calls_enabled",
        "production_provider_consensus_enabled",
        "production_provider_failover_enabled",
        "best_price_selection_enabled",
        "provider_weighting_enabled",
        "network_io_added_by_step12d",
        "production_api_wiring_added_by_step12d",
        "production_runtime_wiring_added_by_step12d",
        "production_database_writes_enabled",
        "persistence_schema_changed_by_step12d",
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
        "production_activation_allowed_by_step12d",
    ],
)
def test_manifest_forbidden_behaviors_are_false(key):
    assert final_runtime_freeze_manifest()[key] is False


def test_all_protected_invariants_remain_false():
    manifest = final_runtime_freeze_manifest()
    assert PROTECTED_INVARIANTS
    for key, value in PROTECTED_INVARIANTS.items():
        assert value is False
        assert manifest[key] is False


def test_future_activation_requirements_are_exact_and_unique():
    assert FUTURE_RUNTIME_ACTIVATION_REQUIREMENTS == (
        "explicit_future_activation_step_required",
        "bounded_scheduler_or_supervisor_required_before_always_on_runtime",
        "verified_live_secondary_provider_endpoint_required_before_secondary_network_calls",
        "exact_secondary_provider_event_to_official_gamepk_map_required",
        "exact_official_game_id_join_required",
        "freshness_gate_required",
        "source_complete_gate_required",
        "same_line_required_for_run_line_total_consensus",
        "no_price_fabrication_required",
        "bounded_failure_isolation_required",
        "provider_disable_or_rollback_switch_required",
        "shadow_evidence_window_required",
        "production_smoke_certification_required",
    )
    assert len(set(FUTURE_RUNTIME_ACTIVATION_REQUIREMENTS)) == len(
        FUTURE_RUNTIME_ACTIVATION_REQUIREMENTS
    )


def test_manifest_returns_lists_not_shared_tuples():
    manifest = final_runtime_freeze_manifest()
    assert manifest["step12_stage_chain"] == list(STEP12_STAGE_CHAIN)
    assert manifest["step12_certification_markers"] == list(STEP12_CERTIFICATION_MARKERS)
    assert manifest["future_runtime_activation_requirements"] == list(
        FUTURE_RUNTIME_ACTIVATION_REQUIREMENTS
    )


def test_exact_upstream_manifests_and_green_evidence_pass():
    result = validate_final_runtime_freeze(**_valid_kwargs())
    assert result["freeze_valid"] is True
    assert result["failures"] == []
    assert result["final_certification_marker"] == FINAL_CERTIFICATION_MARKER


@pytest.mark.parametrize(
    ("manifest_field", "expected_failure"),
    [
        ("step11_manifest", "STEP12D_STEP11_FINAL_FREEZE_MANIFEST_MISMATCH"),
        ("step12a_manifest", "STEP12D_STEP12A_MANIFEST_MISMATCH"),
        ("step12b_manifest", "STEP12D_STEP12B_MANIFEST_MISMATCH"),
        ("step12c_manifest", "STEP12D_STEP12C_MANIFEST_MISMATCH"),
    ],
)
def test_tampered_upstream_manifest_fails_closed(manifest_field, expected_failure):
    kwargs = _valid_kwargs()
    tampered = deepcopy(kwargs[manifest_field])
    tampered["tampered"] = True
    kwargs[manifest_field] = tampered
    result = validate_final_runtime_freeze(**kwargs)
    assert result["freeze_valid"] is False
    assert expected_failure in result["failures"]


@pytest.mark.parametrize(
    "manifest_field",
    ["step11_manifest", "step12a_manifest", "step12b_manifest", "step12c_manifest"],
)
def test_missing_upstream_manifest_fails_closed(manifest_field):
    kwargs = _valid_kwargs()
    kwargs[manifest_field] = None
    assert validate_final_runtime_freeze(**kwargs)["freeze_valid"] is False


EVIDENCE_FIELDS = (
    "shadow_runtime_evidence_ok",
    "exact_game_assembly_evidence_ok",
    "live_board_evidence_ok",
    "zero_actionable_rows_ok",
    "zero_live_secondary_provider_calls_ok",
    "zero_price_fabrication_ok",
    "zero_production_consensus_failover_ok",
    "zero_production_runtime_changes_ok",
    "zero_production_database_writes_ok",
)


@pytest.mark.parametrize("field", EVIDENCE_FIELDS)
def test_false_evidence_fails_closed(field):
    kwargs = _valid_kwargs()
    kwargs[field] = False
    result = validate_final_runtime_freeze(**kwargs)
    assert result["freeze_valid"] is False
    assert f"STEP12D_{field.upper()}_NOT_GREEN" in result["failures"]
    assert result[field] is False


@pytest.mark.parametrize("field", EVIDENCE_FIELDS)
@pytest.mark.parametrize("truthy_non_bool", [1, "yes", [True], {"ok": True}])
def test_truthy_non_boolean_evidence_is_rejected(field, truthy_non_bool):
    kwargs = _valid_kwargs()
    kwargs[field] = truthy_non_bool
    result = validate_final_runtime_freeze(**kwargs)
    assert result["freeze_valid"] is False
    assert f"STEP12D_{field.upper()}_NOT_GREEN" in result["failures"]
    assert result[field] is False


def test_multiple_failures_are_accumulated():
    kwargs = _valid_kwargs()
    kwargs["step12b_manifest"] = None
    kwargs["zero_actionable_rows_ok"] = False
    kwargs["zero_production_database_writes_ok"] = False
    result = validate_final_runtime_freeze(**kwargs)
    assert result["freeze_valid"] is False
    assert result["failures"] == [
        "STEP12D_STEP12B_MANIFEST_MISMATCH",
        "STEP12D_ZERO_ACTIONABLE_ROWS_OK_NOT_GREEN",
        "STEP12D_ZERO_PRODUCTION_DATABASE_WRITES_OK_NOT_GREEN",
    ]


def test_validation_does_not_mutate_input_manifests():
    kwargs = _valid_kwargs()
    originals = {
        key: deepcopy(kwargs[key])
        for key in ("step11_manifest", "step12a_manifest", "step12b_manifest", "step12c_manifest")
    }
    validate_final_runtime_freeze(**kwargs)
    for key, original in originals.items():
        assert kwargs[key] == original


def test_manifest_calls_are_isolated_from_nested_list_mutation():
    first = final_runtime_freeze_manifest()
    first["step12_stage_chain"].append("BAD")
    first["step12_certification_markers"].clear()
    first["future_runtime_activation_requirements"].append("BAD")
    second = final_runtime_freeze_manifest()
    assert second["step12_stage_chain"] == list(STEP12_STAGE_CHAIN)
    assert second["step12_certification_markers"] == list(STEP12_CERTIFICATION_MARKERS)
    assert second["future_runtime_activation_requirements"] == list(
        FUTURE_RUNTIME_ACTIVATION_REQUIREMENTS
    )
