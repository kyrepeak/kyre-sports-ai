from sports_api.mlb_step9_final_freeze_v1 import (
    DATA_TYPE,
    FINAL_CERTIFICATION_MARKER,
    FINAL_FREEZE_STATUS,
    PROTECTED_INVARIANTS,
    SCHEMA_VERSION,
    STEP9_CERTIFICATION_MARKERS,
    STEP9_MERGED_PULL_REQUESTS,
    STEP9_STAGE_CHAIN,
    STEP9F_BASE_MAIN_SHA,
    final_freeze_manifest,
    validate_final_step9_certification,
)


def test_manifest_records_complete_step9_chain_and_certification_evidence():
    manifest = final_freeze_manifest()
    assert manifest["data_type"] == DATA_TYPE == "mlb_step9_final_freeze_v1"
    assert manifest["schema_version"] == SCHEMA_VERSION == 1
    assert manifest["step9f_base_main_sha"] == STEP9F_BASE_MAIN_SHA
    assert manifest["final_freeze_status"] == FINAL_FREEZE_STATUS
    assert manifest["final_certification_marker"] == FINAL_CERTIFICATION_MARKER
    assert manifest["stage_chain"] == list(STEP9_STAGE_CHAIN)
    assert manifest["certification_markers"] == list(STEP9_CERTIFICATION_MARKERS)
    assert manifest["merged_pull_requests"] == list(STEP9_MERGED_PULL_REQUESTS)
    assert len(manifest["stage_chain"]) == 5
    assert len(manifest["certification_markers"]) == 5
    assert manifest["merged_pull_requests"] == [37, 38, 39, 40, 41]


def test_manifest_is_read_only_exact_identity_api_first_and_fallback_safe():
    manifest = final_freeze_manifest()
    assert manifest["read_only_freeze"] is True
    assert manifest["automatic_runtime_mutation"] is False
    assert manifest["runtime_files_changed_by_step9f"] is False
    assert manifest["exact_official_game_id_required"] is True
    assert manifest["team_name_matching_allowed"] is False
    assert manifest["player_name_matching_allowed"] is False
    assert manifest["fuzzy_matching_allowed"] is False
    assert manifest["synthetic_game_id_allowed"] is False
    assert manifest["stale_live_state_context_allowed"] is False
    assert manifest["stale_live_market_context_allowed"] is False
    assert manifest["missing_live_market_price_fabrication_allowed"] is False
    assert manifest["provider_contract_unavailable_may_fall_back"] is True
    assert manifest["legacy_direct_live_state_fallback_preserved"] is True
    assert manifest["legacy_odds_api_io_fallback_preserved"] is True
    assert manifest["live_game_state_api_first"] is True
    assert manifest["live_market_api_first"] is True
    assert manifest["v1922_market_sync_function_preserved"] is True
    assert manifest["step8_final_freeze_required"] is True
    for key, value in PROTECTED_INVARIANTS.items():
        assert value is False
        assert manifest[key] is False


def test_exact_certification_evidence_is_freeze_eligible():
    result = validate_final_step9_certification(
        STEP9_CERTIFICATION_MARKERS,
        runtime_base_sha=STEP9F_BASE_MAIN_SHA,
    )
    assert result["freeze_eligible"] is True
    assert result["freeze_status"] == FINAL_FREEZE_STATUS
    assert result["failures"] == []
    assert result["missing_certification_markers"] == []
    assert result["unexpected_certification_markers"] == []
    assert result["duplicate_certification_markers"] == []


def test_wrong_runtime_base_sha_rejects_freeze():
    result = validate_final_step9_certification(
        STEP9_CERTIFICATION_MARKERS,
        runtime_base_sha="0" * 40,
    )
    assert result["freeze_eligible"] is False
    assert result["freeze_status"] == "STEP9_FREEZE_REJECTED"
    assert "STEP9F_RUNTIME_BASE_SHA_MISMATCH" in result["failures"]


def test_missing_marker_rejects_freeze():
    result = validate_final_step9_certification(
        STEP9_CERTIFICATION_MARKERS[:-1],
        runtime_base_sha=STEP9F_BASE_MAIN_SHA,
    )
    assert result["freeze_eligible"] is False
    assert result["missing_certification_markers"] == [STEP9_CERTIFICATION_MARKERS[-1]]
    assert "STEP9_CERTIFICATION_MARKERS_MISSING" in result["failures"]
    assert "STEP9_CERTIFICATION_MARKER_COUNT_MISMATCH" in result["failures"]


def test_duplicate_marker_rejects_freeze():
    markers = list(STEP9_CERTIFICATION_MARKERS)
    markers[-1] = markers[0]
    result = validate_final_step9_certification(markers, runtime_base_sha=STEP9F_BASE_MAIN_SHA)
    assert result["freeze_eligible"] is False
    assert result["duplicate_certification_markers"] == [STEP9_CERTIFICATION_MARKERS[0]]
    assert "STEP9_DUPLICATE_CERTIFICATION_MARKERS" in result["failures"]
    assert "STEP9_CERTIFICATION_MARKERS_MISSING" in result["failures"]


def test_unexpected_marker_rejects_freeze():
    markers = list(STEP9_CERTIFICATION_MARKERS) + ["UNEXPECTED"]
    result = validate_final_step9_certification(markers, runtime_base_sha=STEP9F_BASE_MAIN_SHA)
    assert result["freeze_eligible"] is False
    assert result["unexpected_certification_markers"] == ["UNEXPECTED"]
    assert "STEP9_UNEXPECTED_CERTIFICATION_MARKERS" in result["failures"]
    assert "STEP9_CERTIFICATION_MARKER_COUNT_MISMATCH" in result["failures"]


def test_none_or_non_iterable_evidence_fails_closed_without_exception():
    none_result = validate_final_step9_certification(None, runtime_base_sha=STEP9F_BASE_MAIN_SHA)
    scalar_result = validate_final_step9_certification(123, runtime_base_sha=STEP9F_BASE_MAIN_SHA)
    for result in (none_result, scalar_result):
        assert result["freeze_eligible"] is False
        assert "STEP9_CERTIFICATION_MARKERS_MISSING" in result["failures"]
        assert "STEP9_CERTIFICATION_MARKER_COUNT_MISMATCH" in result["failures"]


def test_manifest_calls_return_isolated_mutable_lists():
    first = final_freeze_manifest()
    second = final_freeze_manifest()
    first["stage_chain"].append("MUTATED")
    first["certification_markers"].clear()
    first["merged_pull_requests"].append(999)
    assert second["stage_chain"] == list(STEP9_STAGE_CHAIN)
    assert second["certification_markers"] == list(STEP9_CERTIFICATION_MARKERS)
    assert second["merged_pull_requests"] == list(STEP9_MERGED_PULL_REQUESTS)
