from copy import deepcopy

import pytest

from sports_api.mlb_step9_final_freeze_v1 import PROTECTED_INVARIANTS
from sports_api.mlb_step10_final_persistence_freeze_v1 import final_persistence_freeze_manifest
from sports_api.mlb_step11a_provider_contract_v1 import provider_contract_manifest
from sports_api.collectors.mlb_draftkings_provider import adapter_manifest as draftkings_adapter_manifest
from sports_api.mlb_step11c_multi_provider_shadow_board_v1 import shadow_board_manifest
from sports_api.mlb_step11d_provider_consensus_failover_shadow_policy_v1 import policy_manifest
from sports_api.mlb_step11_final_provider_expansion_freeze_v1 import (
    DATA_TYPE,
    FINAL_CERTIFICATION_MARKER,
    FINAL_FREEZE_STATUS,
    FUTURE_ACTIVATION_REQUIREMENTS,
    SCHEMA_VERSION,
    STEP11E_BASE_MAIN_SHA,
    STEP11_CERTIFICATION_MARKERS,
    STEP11_STAGE_CHAIN,
    final_provider_expansion_freeze_manifest,
    validate_final_provider_expansion_freeze,
)


def _kwargs():
    return {
        "step10_manifest": final_persistence_freeze_manifest(),
        "step11a_manifest": provider_contract_manifest(),
        "step11b_manifest": draftkings_adapter_manifest(),
        "step11c_manifest": shadow_board_manifest(),
        "step11d_manifest": policy_manifest(),
        "provider_contract_evidence_ok": True,
        "draftkings_adapter_evidence_ok": True,
        "shadow_board_evidence_ok": True,
        "consensus_failover_shadow_evidence_ok": True,
        "zero_live_secondary_provider_calls_ok": True,
        "zero_price_fabrication_ok": True,
        "zero_production_consensus_failover_ok": True,
        "zero_production_runtime_changes_ok": True,
        "zero_production_database_writes_ok": True,
    }


def test_constants_are_exact():
    assert DATA_TYPE == "mlb_step11_final_provider_expansion_freeze_v1"
    assert SCHEMA_VERSION == 1
    assert STEP11E_BASE_MAIN_SHA == "9559b6d98ff1193051ea064060db21d13d5428e6"
    assert FINAL_FREEZE_STATUS == "STEP11_FROZEN_MULTI_PROVIDER_EXPANSION_COMPLETE"
    assert FINAL_CERTIFICATION_MARKER == "MLB_STEP11E_FINAL_PROVIDER_EXPANSION_FREEZE_GREEN"


def test_stage_chain_is_exact():
    assert STEP11_STAGE_CHAIN == (
        "11A_PROVIDER_NEUTRAL_CORE_MARKET_CONTRACT",
        "11B_DRAFTKINGS_SHADOW_PROVIDER_ADAPTER",
        "11C_MULTI_PROVIDER_SHADOW_BOARD",
        "11D_PROVIDER_CONSENSUS_FAILOVER_SHADOW_POLICY",
    )
    assert len(STEP11_CERTIFICATION_MARKERS) == 4
    assert len(set(STEP11_CERTIFICATION_MARKERS)) == 4


def test_future_activation_requirements_are_explicit_and_unique():
    assert len(FUTURE_ACTIVATION_REQUIREMENTS) >= 10
    assert len(set(FUTURE_ACTIVATION_REQUIREMENTS)) == len(FUTURE_ACTIVATION_REQUIREMENTS)
    assert "verified_live_secondary_provider_endpoint_required" in FUTURE_ACTIVATION_REQUIREMENTS
    assert "exact_secondary_provider_event_to_official_gamepk_map_required" in FUTURE_ACTIVATION_REQUIREMENTS
    assert "provider_disable_or_rollback_switch_required" in FUTURE_ACTIVATION_REQUIREMENTS
    assert "production_smoke_certification_required" in FUTURE_ACTIVATION_REQUIREMENTS


def test_manifest_freezes_all_step11_layers():
    m = final_provider_expansion_freeze_manifest()
    for key in (
        "provider_expansion_block_frozen",
        "step11a_provider_contract_frozen",
        "step11b_draftkings_adapter_frozen",
        "step11c_shadow_board_frozen",
        "step11d_consensus_failover_policy_frozen",
        "exact_official_game_id_required",
        "exact_secondary_provider_event_map_required",
        "freshness_required",
        "source_complete_required",
        "same_line_required_for_run_line_total_consensus",
        "explicit_future_activation_step_required",
    ):
        assert m[key] is True, key


def test_manifest_keeps_production_activation_off():
    m = final_provider_expansion_freeze_manifest()
    for key in (
        "price_fabrication_allowed",
        "fallback_price_fabrication_allowed",
        "team_name_join_allowed",
        "player_name_join_allowed",
        "fuzzy_matching_allowed",
        "synthetic_game_id_allowed",
        "best_price_selection_enabled",
        "provider_weighting_enabled",
        "production_provider_consensus_enabled",
        "production_provider_failover_enabled",
        "live_secondary_provider_network_calls_enabled",
        "network_io_added_by_step11e",
        "production_api_wiring_added_by_step11e",
        "production_runtime_wiring_added_by_step11e",
        "persistence_schema_changed_by_step11e",
        "production_database_writes_enabled",
        "consensus_as_model_input_allowed",
        "shadow_route_as_model_input_allowed",
        "shadow_route_as_sportsbook_input_allowed",
        "production_activation_allowed_by_step11e",
        "persisted_snapshot_as_model_input_allowed",
        "persisted_snapshot_as_sportsbook_input_allowed",
    ):
        assert m[key] is False, key


def test_manifest_preserves_all_protected_invariants():
    m = final_provider_expansion_freeze_manifest()
    for key, value in PROTECTED_INVARIANTS.items():
        assert value is False
        assert m[key] is False


def test_manifest_supports_exactly_fanduel_and_draftkings():
    m = final_provider_expansion_freeze_manifest()
    assert m["supported_providers"] == ["fanduel", "draftkings"]
    assert m["primary_provider"] == "fanduel"
    assert m["fallback_provider"] == "draftkings"


def test_manifest_isolation():
    first = final_provider_expansion_freeze_manifest()
    first["supported_providers"].append("other")
    first["future_activation_requirements"].append("bad")
    second = final_provider_expansion_freeze_manifest()
    assert second["supported_providers"] == ["fanduel", "draftkings"]
    assert "other" not in second["supported_providers"]
    assert "bad" not in second["future_activation_requirements"]


def test_valid_freeze_is_green():
    result = validate_final_provider_expansion_freeze(**_kwargs())
    assert result["freeze_valid"] is True
    assert result["failures"] == []
    assert result["final_certification_marker"] == FINAL_CERTIFICATION_MARKER


@pytest.mark.parametrize(
    ("manifest_field", "failure"),
    [
        ("step10_manifest", "STEP11E_STEP10_FINAL_FREEZE_MANIFEST_MISMATCH"),
        ("step11a_manifest", "STEP11E_STEP11A_MANIFEST_MISMATCH"),
        ("step11b_manifest", "STEP11E_STEP11B_MANIFEST_MISMATCH"),
        ("step11c_manifest", "STEP11E_STEP11C_MANIFEST_MISMATCH"),
        ("step11d_manifest", "STEP11E_STEP11D_MANIFEST_MISMATCH"),
    ],
)
def test_each_prerequisite_manifest_fails_closed(manifest_field, failure):
    kwargs = _kwargs()
    kwargs[manifest_field] = {"tampered": True}
    result = validate_final_provider_expansion_freeze(**kwargs)
    assert result["freeze_valid"] is False
    assert failure in result["failures"]


@pytest.mark.parametrize(
    "field",
    [
        "provider_contract_evidence_ok",
        "draftkings_adapter_evidence_ok",
        "shadow_board_evidence_ok",
        "consensus_failover_shadow_evidence_ok",
        "zero_live_secondary_provider_calls_ok",
        "zero_price_fabrication_ok",
        "zero_production_consensus_failover_ok",
        "zero_production_runtime_changes_ok",
        "zero_production_database_writes_ok",
    ],
)
def test_each_false_evidence_flag_fails_closed(field):
    kwargs = _kwargs()
    kwargs[field] = False
    result = validate_final_provider_expansion_freeze(**kwargs)
    assert result["freeze_valid"] is False
    assert f"STEP11E_{field.upper()}_NOT_GREEN" in result["failures"]
    assert result[field] is False


@pytest.mark.parametrize(
    "field",
    [
        "provider_contract_evidence_ok",
        "draftkings_adapter_evidence_ok",
        "shadow_board_evidence_ok",
        "consensus_failover_shadow_evidence_ok",
        "zero_live_secondary_provider_calls_ok",
        "zero_price_fabrication_ok",
        "zero_production_consensus_failover_ok",
        "zero_production_runtime_changes_ok",
        "zero_production_database_writes_ok",
    ],
)
def test_truthy_non_boolean_evidence_fails_closed(field):
    kwargs = _kwargs()
    kwargs[field] = 1
    result = validate_final_provider_expansion_freeze(**kwargs)
    assert result["freeze_valid"] is False
    assert f"STEP11E_{field.upper()}_NOT_GREEN" in result["failures"]
    assert result[field] is False


def test_multiple_failures_are_all_reported():
    kwargs = _kwargs()
    kwargs["step11c_manifest"] = None
    kwargs["zero_price_fabrication_ok"] = False
    kwargs["zero_production_database_writes_ok"] = False
    result = validate_final_provider_expansion_freeze(**kwargs)
    assert result["freeze_valid"] is False
    assert "STEP11E_STEP11C_MANIFEST_MISMATCH" in result["failures"]
    assert "STEP11E_ZERO_PRICE_FABRICATION_OK_NOT_GREEN" in result["failures"]
    assert "STEP11E_ZERO_PRODUCTION_DATABASE_WRITES_OK_NOT_GREEN" in result["failures"]


def test_validation_does_not_mutate_input_manifests():
    kwargs = _kwargs()
    originals = {
        key: deepcopy(value)
        for key, value in kwargs.items()
        if key.endswith("_manifest")
    }
    validate_final_provider_expansion_freeze(**kwargs)
    for key, original in originals.items():
        assert kwargs[key] == original


def test_validator_result_repeats_immutable_freeze_boundary():
    result = validate_final_provider_expansion_freeze(**_kwargs())
    manifest = final_provider_expansion_freeze_manifest()
    for key, value in manifest.items():
        assert result[key] == value


def test_step11_markers_match_exact_prerequisite_manifests():
    markers = [
        provider_contract_manifest()["final_certification_marker"],
        draftkings_adapter_manifest()["final_certification_marker"],
        shadow_board_manifest()["final_certification_marker"],
        policy_manifest()["final_certification_marker"],
    ]
    assert list(STEP11_CERTIFICATION_MARKERS) == markers


def test_step10_final_freeze_is_explicit_prerequisite():
    m = final_provider_expansion_freeze_manifest()
    step10 = final_persistence_freeze_manifest()
    assert m["step10_final_freeze_status_required"] == step10["final_freeze_status"]
    assert m["step10_final_certification_marker_required"] == step10["final_certification_marker"]


def test_step11_statuses_are_explicit_prerequisites():
    m = final_provider_expansion_freeze_manifest()
    assert m["step11a_contract_status_required"] == provider_contract_manifest()["contract_status"]
    assert m["step11b_adapter_status_required"] == draftkings_adapter_manifest()["adapter_status"]
    assert m["step11c_board_status_required"] == shadow_board_manifest()["board_status"]
    assert m["step11d_policy_status_required"] == policy_manifest()["policy_status"]
