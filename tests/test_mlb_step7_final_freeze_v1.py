import copy

from sports_api.mlb_step7_final_freeze_v1 import (
    DATA_TYPE,
    FINAL_CERTIFICATION_MARKER,
    FINAL_FREEZE_STATUS,
    PROTECTED_INVARIANTS,
    SCHEMA_VERSION,
    STEP7_CERTIFICATION_MARKERS,
    STEP7_MERGED_PULL_REQUESTS,
    STEP7_STAGE_CHAIN,
    STEP7F_BASE_MAIN_SHA,
    final_freeze_manifest,
    validate_final_step7_certification,
)


def test_final_freeze_manifest_records_exact_step7_checkpoint():
    manifest = final_freeze_manifest()
    assert manifest["data_type"] == DATA_TYPE
    assert manifest["schema_version"] == SCHEMA_VERSION == 1
    assert manifest["step7f_base_main_sha"] == STEP7F_BASE_MAIN_SHA
    assert manifest["step7f_base_main_sha"] == "918a0ea3abf6c79d15ff6eac1654e7e5a1e773cc"
    assert manifest["final_freeze_status"] == FINAL_FREEZE_STATUS
    assert manifest["final_certification_marker"] == FINAL_CERTIFICATION_MARKER


def test_manifest_freezes_exact_step7_stage_chain_and_prs():
    manifest = final_freeze_manifest()
    assert manifest["stage_chain"] == list(STEP7_STAGE_CHAIN)
    assert manifest["certification_markers"] == list(STEP7_CERTIFICATION_MARKERS)
    assert manifest["merged_pull_requests"] == list(STEP7_MERGED_PULL_REQUESTS)
    assert len(manifest["stage_chain"]) == 5
    assert len(manifest["certification_markers"]) == 5
    assert manifest["merged_pull_requests"] == [24, 25, 26, 27, 28]


def test_final_freeze_is_read_only_exact_id_fail_closed_contract():
    manifest = final_freeze_manifest()
    assert manifest["read_only_freeze"] is True
    assert manifest["automatic_runtime_mutation"] is False
    assert manifest["runtime_files_changed_by_step7f"] is False
    assert manifest["exact_official_game_id_required"] is True
    assert manifest["fuzzy_matching_allowed"] is False
    assert manifest["stale_market_context_allowed"] is False
    assert manifest["missing_market_price_fabrication_allowed"] is False
    assert manifest["step6_frozen_state_required"] is True


def test_protected_invariants_are_all_false():
    manifest = final_freeze_manifest()
    for key, expected in PROTECTED_INVARIANTS.items():
        assert expected is False
        assert manifest[key] is False


def test_exact_certification_evidence_is_freeze_eligible():
    result = validate_final_step7_certification(
        STEP7_CERTIFICATION_MARKERS,
        runtime_base_sha=STEP7F_BASE_MAIN_SHA,
    )
    assert result["freeze_eligible"] is True
    assert result["freeze_status"] == FINAL_FREEZE_STATUS
    assert result["failures"] == []
    assert result["missing_certification_markers"] == []
    assert result["unexpected_certification_markers"] == []
    assert result["duplicate_certification_markers"] == []


def test_marker_order_does_not_change_certification_identity():
    observed = list(reversed(STEP7_CERTIFICATION_MARKERS))
    result = validate_final_step7_certification(
        observed,
        runtime_base_sha=STEP7F_BASE_MAIN_SHA,
    )
    assert result["freeze_eligible"] is True
    assert result["observed_certification_markers"] == observed


def test_missing_marker_rejects_freeze():
    observed = list(STEP7_CERTIFICATION_MARKERS[:-1])
    result = validate_final_step7_certification(
        observed,
        runtime_base_sha=STEP7F_BASE_MAIN_SHA,
    )
    assert result["freeze_eligible"] is False
    assert result["freeze_status"] == "STEP7_FREEZE_REJECTED"
    assert "STEP7_CERTIFICATION_MARKERS_MISSING" in result["failures"]
    assert "STEP7_CERTIFICATION_MARKER_COUNT_MISMATCH" in result["failures"]
    assert result["missing_certification_markers"] == [STEP7_CERTIFICATION_MARKERS[-1]]


def test_duplicate_marker_rejects_freeze_even_when_all_expected_markers_exist():
    observed = list(STEP7_CERTIFICATION_MARKERS) + [STEP7_CERTIFICATION_MARKERS[0]]
    result = validate_final_step7_certification(
        observed,
        runtime_base_sha=STEP7F_BASE_MAIN_SHA,
    )
    assert result["freeze_eligible"] is False
    assert "STEP7_DUPLICATE_CERTIFICATION_MARKERS" in result["failures"]
    assert "STEP7_CERTIFICATION_MARKER_COUNT_MISMATCH" in result["failures"]
    assert result["duplicate_certification_markers"] == [STEP7_CERTIFICATION_MARKERS[0]]


def test_unexpected_marker_rejects_freeze():
    observed = list(STEP7_CERTIFICATION_MARKERS)
    observed[-1] = "NOT_A_CERTIFIED_STEP7_MARKER"
    result = validate_final_step7_certification(
        observed,
        runtime_base_sha=STEP7F_BASE_MAIN_SHA,
    )
    assert result["freeze_eligible"] is False
    assert "STEP7_CERTIFICATION_MARKERS_MISSING" in result["failures"]
    assert "STEP7_UNEXPECTED_CERTIFICATION_MARKERS" in result["failures"]


def test_wrong_runtime_base_sha_rejects_freeze():
    result = validate_final_step7_certification(
        STEP7_CERTIFICATION_MARKERS,
        runtime_base_sha="deadbeef",
    )
    assert result["freeze_eligible"] is False
    assert result["failures"] == ["STEP7F_RUNTIME_BASE_SHA_MISMATCH"]


def test_validation_does_not_mutate_observed_marker_input():
    observed = list(STEP7_CERTIFICATION_MARKERS)
    before = copy.deepcopy(observed)
    validate_final_step7_certification(observed, runtime_base_sha=STEP7F_BASE_MAIN_SHA)
    assert observed == before
