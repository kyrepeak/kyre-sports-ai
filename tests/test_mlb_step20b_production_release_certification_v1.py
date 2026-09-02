from __future__ import annotations

from copy import deepcopy

import pytest

from sports_api import mlb_step17a_production_host_contract_v1 as step17a
from sports_api import mlb_step20a_end_to_end_certification_v1 as step20a
from sports_api.mlb_step20b_production_release_certification_v1 import (
    CERTIFICATION_STATUS,
    CERTIFIED_ROLLBACK_REVISION,
    DATA_TYPE,
    FINAL_CERTIFICATION_MARKER,
    MLBStep20BProductionReleaseCertificationError,
    RELEASE_MODE,
    SCHEMA_VERSION,
    STEP20B_BASE_MAIN_SHA,
    certification_manifest,
    certify_step20b_production_release_candidate,
)


CANDIDATE_SHA = "1" * 40


def _step20a_result() -> dict:
    return {
        "data_type": step20a.DATA_TYPE,
        "schema_version": step20a.SCHEMA_VERSION,
        "certification_status": "certified",
        "final_certification_marker": step20a.FINAL_CERTIFICATION_MARKER,
        "checkpoint_version": 4,
        "checkpoint_id": "checkpoint-4",
        "checkpoint_envelope_sha256": "a" * 64,
        "consumer_api_path": step20a.EXISTING_CONSUMER_PATH,
        "consumer_api_data_type": step20a.EXISTING_API_DATA_TYPE,
        "consumer_game_count": 2,
        "consumer_card_count": 2,
        "consumer_official_game_ids": [777001, 777002],
        "provider_network_calls_added_by_step20a": 0,
        "database_reads_added_by_step20a": 0,
        "database_writes_added_by_step20a": 0,
        "production_runtime_wiring": False,
        "production_scheduler_mutation": False,
        "model_probability_mutation": False,
        "projection_mutation": False,
        "actionable_output": False,
        "wagering": False,
        "fuzzy_matching_used": False,
        "synthetic_game_id_used": False,
        "synthetic_player_id_used": False,
        "price_fabrication_used": False,
    }


def _safe_env() -> dict[str, str]:
    return {
        "MLB_PRODUCTION_RUNTIME_ENABLED": "false",
        "MLB_PRODUCTION_SCHEDULER_ENABLED": "false",
        "MLB_ACTIONABLE_OUTPUT_ENABLED": "false",
        "MLB_WAGERING_ENABLED": "false",
        "MLB_SUPABASE_REST_WRITE_ENABLED": "false",
        "MLB_STEP16C_LIVE_POSTGRESQL_CANARY_ENABLED": "false",
        "MLB_STEP16D_CONTROLLED_PRODUCTION_ACTIVATION_ENABLED": "false",
        "MLB_STEP16E_FINAL_PRODUCTION_FREEZE_ENABLED": "false",
    }


def test_manifest_is_non_deploying_and_manual_only():
    manifest = certification_manifest()
    assert manifest["data_type"] == DATA_TYPE
    assert manifest["schema_version"] == SCHEMA_VERSION
    assert manifest["step20b_base_main_sha"] == STEP20B_BASE_MAIN_SHA
    assert manifest["certification_status"] == CERTIFICATION_STATUS
    assert manifest["final_certification_marker"] == FINAL_CERTIFICATION_MARKER
    assert manifest["release_mode"] == RELEASE_MODE
    assert manifest["pull_request_deploy_allowed"] is False
    assert manifest["pull_request_activation_allowed"] is False
    assert manifest["render_mutation_allowed"] is False
    assert manifest["automatic_rollback_allowed"] is False
    assert manifest["manual_merge_required"] is True
    assert manifest["manual_post_merge_activation_required"] is True
    assert manifest["wagering_enabled"] is False


def test_green_step20a_result_becomes_release_candidate_only():
    source = _step20a_result()
    result = certify_step20b_production_release_candidate(
        source,
        candidate_sha=CANDIDATE_SHA,
        env=_safe_env(),
    )
    assert result["certification_status"] == "certified"
    assert result["final_certification_marker"] == FINAL_CERTIFICATION_MARKER
    assert result["candidate_sha"] == CANDIDATE_SHA
    assert result["consumer_api_path"] == "/api/v1/mlb/odds"
    assert result["consumer_game_count"] == 2
    assert result["consumer_official_game_ids"] == [777001, 777002]
    assert result["host_release_boundary_verified"] is True
    assert result["ready_for_merge_decision"] is True
    assert result["deployment_performed"] is False
    assert result["activation_performed"] is False
    assert result["render_mutation_performed"] is False
    assert result["production_database_write_performed"] is False
    assert result["automatic_rollback_performed"] is False
    assert result["rollback_revision"] == CERTIFIED_ROLLBACK_REVISION
    assert result["manual_merge_required"] is True
    assert result["manual_post_merge_activation_required"] is True
    assert result["actionable_output"] is False
    assert result["wagering"] is False


def test_result_is_copy_isolated_from_source():
    source = _step20a_result()
    result = certify_step20b_production_release_candidate(
        source,
        candidate_sha=CANDIDATE_SHA,
        env=_safe_env(),
    )
    result["consumer_official_game_ids"][0] = 999999
    assert source["consumer_official_game_ids"] == [777001, 777002]


@pytest.mark.parametrize(
    "field,value,match",
    [
        ("data_type", "wrong", "not a Step 20A"),
        ("schema_version", 99, "schema version"),
        ("certification_status", "failed", "not green"),
        ("final_certification_marker", "wrong", "marker"),
        ("consumer_api_path", "/wrong", "API path"),
        ("consumer_api_data_type", "wrong", "data type"),
    ],
)
def test_step20a_contract_drift_fails_closed(field, value, match):
    source = _step20a_result()
    source[field] = value
    with pytest.raises(MLBStep20BProductionReleaseCertificationError, match=match):
        certify_step20b_production_release_candidate(
            source,
            candidate_sha=CANDIDATE_SHA,
            env=_safe_env(),
        )


@pytest.mark.parametrize(
    "field",
    [
        "production_runtime_wiring",
        "production_scheduler_mutation",
        "model_probability_mutation",
        "projection_mutation",
        "actionable_output",
        "wagering",
        "fuzzy_matching_used",
        "synthetic_game_id_used",
        "synthetic_player_id_used",
        "price_fabrication_used",
    ],
)
def test_step20a_unsafe_flag_fails_closed(field):
    source = _step20a_result()
    source[field] = True
    with pytest.raises(MLBStep20BProductionReleaseCertificationError, match=field):
        certify_step20b_production_release_candidate(
            source,
            candidate_sha=CANDIDATE_SHA,
            env=_safe_env(),
        )


@pytest.mark.parametrize(
    "field",
    [
        "provider_network_calls_added_by_step20a",
        "database_reads_added_by_step20a",
        "database_writes_added_by_step20a",
    ],
)
def test_step20a_nonzero_safety_counter_fails_closed(field):
    source = _step20a_result()
    source[field] = 1
    with pytest.raises(MLBStep20BProductionReleaseCertificationError, match=field):
        certify_step20b_production_release_candidate(
            source,
            candidate_sha=CANDIDATE_SHA,
            env=_safe_env(),
        )


def test_mismatched_consumer_counts_fail_closed():
    source = _step20a_result()
    source["consumer_card_count"] = 1
    with pytest.raises(
        MLBStep20BProductionReleaseCertificationError,
        match="cards",
    ):
        certify_step20b_production_release_candidate(
            source,
            candidate_sha=CANDIDATE_SHA,
            env=_safe_env(),
        )


def test_duplicate_official_game_ids_fail_closed():
    source = _step20a_result()
    source["consumer_official_game_ids"] = [777001, 777001]
    with pytest.raises(
        MLBStep20BProductionReleaseCertificationError,
        match="unique",
    ):
        certify_step20b_production_release_candidate(
            source,
            candidate_sha=CANDIDATE_SHA,
            env=_safe_env(),
        )


@pytest.mark.parametrize("key", list(_safe_env()))
def test_release_certification_refuses_activation_or_mutation_gates(key):
    env = _safe_env()
    env[key] = "true"
    with pytest.raises(
        MLBStep20BProductionReleaseCertificationError,
        match="refuses activation/mutation gates",
    ):
        certify_step20b_production_release_candidate(
            _step20a_result(),
            candidate_sha=CANDIDATE_SHA,
            env=env,
        )


def test_invalid_candidate_sha_fails_closed():
    with pytest.raises(
        MLBStep20BProductionReleaseCertificationError,
        match="40-character",
    ):
        certify_step20b_production_release_candidate(
            _step20a_result(),
            candidate_sha="short",
            env=_safe_env(),
        )


def test_host_auto_deploy_boundary_drift_fails_closed(monkeypatch):
    monkeypatch.setattr(step17a, "EXPECTED_RENDER_AUTO_DEPLOY", "yes")
    with pytest.raises(
        MLBStep20BProductionReleaseCertificationError,
        match="host release boundary drift",
    ):
        certify_step20b_production_release_candidate(
            _step20a_result(),
            candidate_sha=CANDIDATE_SHA,
            env=_safe_env(),
        )


def test_host_render_deploy_boundary_drift_fails_closed(monkeypatch):
    monkeypatch.setattr(step17a, "RENDER_DEPLOY_ALLOWED", True)
    with pytest.raises(
        MLBStep20BProductionReleaseCertificationError,
        match="host release boundary drift",
    ):
        certify_step20b_production_release_candidate(
            _step20a_result(),
            candidate_sha=CANDIDATE_SHA,
            env=_safe_env(),
        )
