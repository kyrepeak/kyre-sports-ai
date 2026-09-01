from sports_api.mlb_step9_final_freeze_v1 import (
    FINAL_CERTIFICATION_MARKER as STEP9F_FINAL_CERTIFICATION_MARKER,
    FINAL_FREEZE_STATUS as STEP9F_FINAL_FREEZE_STATUS,
    PROTECTED_INVARIANTS,
    STEP9_STAGE_CHAIN,
    final_freeze_manifest,
)
from sports_api.mlb_step9g_postfreeze_handoff_v1 import (
    DATA_TYPE,
    FINAL_CERTIFICATION_MARKER,
    HANDOFF_STATUS,
    SCHEMA_VERSION,
    STEP9G_BASE_MAIN_SHA,
    handoff_manifest,
    validate_postfreeze_handoff,
)


def _valid_result(**overrides):
    kwargs = {
        "step9f_manifest": final_freeze_manifest(),
        "runtime_base_sha": STEP9G_BASE_MAIN_SHA,
        "live_state_contract_ok": True,
        "live_market_contract_ok": True,
        "no_price_fabrication_ok": True,
    }
    kwargs.update(overrides)
    return validate_postfreeze_handoff(**kwargs)


def test_handoff_manifest_is_non_behavioral_and_anchors_exact_step9f_merge():
    manifest = handoff_manifest()
    assert manifest["data_type"] == DATA_TYPE == "mlb_step9g_postfreeze_handoff_v1"
    assert manifest["schema_version"] == SCHEMA_VERSION == 1
    assert manifest["step9g_base_main_sha"] == STEP9G_BASE_MAIN_SHA
    assert manifest["handoff_status"] == HANDOFF_STATUS
    assert manifest["final_certification_marker"] == FINAL_CERTIFICATION_MARKER
    assert manifest["step9f_final_freeze_status"] == STEP9F_FINAL_FREEZE_STATUS
    assert manifest["step9f_final_certification_marker"] == STEP9F_FINAL_CERTIFICATION_MARKER
    assert manifest["stage_chain"] == list(STEP9_STAGE_CHAIN)
    assert manifest["read_only_handoff"] is True
    assert manifest["step9f_frozen_prerequisite_required"] is True
    assert manifest["automatic_runtime_mutation"] is False
    assert manifest["runtime_files_changed_by_step9g"] is False
    assert manifest["network_io_in_module"] is False


def test_handoff_manifest_preserves_exact_identity_and_all_protected_invariants():
    manifest = handoff_manifest()
    assert manifest["exact_official_game_id_required"] is True
    assert manifest["team_name_matching_allowed"] is False
    assert manifest["player_name_matching_allowed"] is False
    assert manifest["fuzzy_matching_allowed"] is False
    assert manifest["synthetic_game_id_allowed"] is False
    assert manifest["stale_live_state_context_allowed"] is False
    assert manifest["stale_live_market_context_allowed"] is False
    assert manifest["missing_live_market_price_fabrication_allowed"] is False
    assert manifest["live_game_state_api_first"] is True
    assert manifest["live_market_api_first"] is True
    for key, value in PROTECTED_INVARIANTS.items():
        assert value is False
        assert manifest[key] is False


def test_exact_step9f_freeze_and_production_evidence_is_handoff_eligible():
    result = _valid_result()
    assert result["handoff_eligible"] is True
    assert result["handoff_status"] == HANDOFF_STATUS
    assert result["step9f_freeze_intact"] is True
    assert result["live_state_contract_ok"] is True
    assert result["live_market_contract_ok"] is True
    assert result["no_price_fabrication_ok"] is True
    assert result["failures"] == []


def test_wrong_postfreeze_base_sha_rejects_handoff():
    result = _valid_result(runtime_base_sha="0" * 40)
    assert result["handoff_eligible"] is False
    assert result["handoff_status"] == "STEP9_POSTFREEZE_HANDOFF_REJECTED"
    assert "STEP9G_RUNTIME_BASE_SHA_MISMATCH" in result["failures"]


def test_missing_or_tampered_step9f_manifest_rejects_handoff():
    missing = _valid_result(step9f_manifest=None)
    assert missing["handoff_eligible"] is False
    assert "STEP9F_FREEZE_MANIFEST_MISSING" in missing["failures"]

    tampered_manifest = final_freeze_manifest()
    tampered_manifest["final_certification_marker"] = "TAMPERED"
    tampered = _valid_result(step9f_manifest=tampered_manifest)
    assert tampered["handoff_eligible"] is False
    assert tampered["step9f_freeze_intact"] is False
    assert "STEP9F_FREEZE_MANIFEST_MISMATCH" in tampered["failures"]


def test_unproven_live_state_contract_rejects_handoff():
    result = _valid_result(live_state_contract_ok=False)
    assert result["handoff_eligible"] is False
    assert "STEP9G_LIVE_STATE_CONTRACT_NOT_PROVEN" in result["failures"]


def test_unproven_live_market_contract_rejects_handoff():
    result = _valid_result(live_market_contract_ok=False)
    assert result["handoff_eligible"] is False
    assert "STEP9G_LIVE_MARKET_CONTRACT_NOT_PROVEN" in result["failures"]


def test_unproven_no_price_fabrication_rejects_handoff():
    result = _valid_result(no_price_fabrication_ok=False)
    assert result["handoff_eligible"] is False
    assert "STEP9G_NO_PRICE_FABRICATION_NOT_PROVEN" in result["failures"]


def test_truthy_non_boolean_evidence_fails_closed():
    result = _valid_result(
        live_state_contract_ok=1,
        live_market_contract_ok="yes",
        no_price_fabrication_ok=[True],
    )
    assert result["handoff_eligible"] is False
    assert result["live_state_contract_ok"] is False
    assert result["live_market_contract_ok"] is False
    assert result["no_price_fabrication_ok"] is False
    assert "STEP9G_LIVE_STATE_CONTRACT_NOT_PROVEN" in result["failures"]
    assert "STEP9G_LIVE_MARKET_CONTRACT_NOT_PROVEN" in result["failures"]
    assert "STEP9G_NO_PRICE_FABRICATION_NOT_PROVEN" in result["failures"]


def test_handoff_manifest_calls_return_isolated_stage_chain_lists():
    first = handoff_manifest()
    second = handoff_manifest()
    first["stage_chain"].append("MUTATED")
    assert second["stage_chain"] == list(STEP9_STAGE_CHAIN)
