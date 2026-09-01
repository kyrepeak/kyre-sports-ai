from copy import deepcopy

import pytest

from sports_api.mlb_step9_final_freeze_v1 import PROTECTED_INVARIANTS
from sports_api.mlb_step9g_postfreeze_handoff_v1 import (
    FINAL_CERTIFICATION_MARKER as STEP9G_FINAL_CERTIFICATION_MARKER,
    HANDOFF_STATUS as STEP9G_HANDOFF_STATUS,
)
from sports_api.mlb_step10a_live_snapshot_persistence_contract_v1 import (
    CONTRACT_STATUS,
    DATA_TYPE,
    FINAL_CERTIFICATION_MARKER,
    SCHEMA_VERSION,
    SNAPSHOT_SOURCE_CONTRACTS,
    STEP10A_BASE_MAIN_SHA,
    build_live_snapshot_persistence_record,
    persistence_contract_manifest,
    validate_live_snapshot_persistence_record,
)


GAME_ID = 824472
OBSERVED = "2026-09-01T16:42:00.123000Z"
SHA = "a" * 64


def _valid_record(**overrides):
    kwargs = {
        "snapshot_kind": "live_game_state",
        "official_game_id": GAME_ID,
        "observed_at_utc": OBSERVED,
        "source_data_type": "mlb_live_game_state_api_response_v1",
        "source_schema_version": 1,
        "payload_sha256": SHA,
        "source_complete": True,
        "step9g_handoff_status": STEP9G_HANDOFF_STATUS,
        "step9g_handoff_marker": STEP9G_FINAL_CERTIFICATION_MARKER,
    }
    kwargs.update(overrides)
    return build_live_snapshot_persistence_record(**kwargs)


def test_manifest_starts_step10a_without_enabling_database_writes():
    m = persistence_contract_manifest()
    assert m["data_type"] == DATA_TYPE == "mlb_live_snapshot_persistence_record_v1"
    assert m["schema_version"] == SCHEMA_VERSION == 1
    assert m["step10a_base_main_sha"] == STEP10A_BASE_MAIN_SHA
    assert m["contract_status"] == CONTRACT_STATUS
    assert m["final_certification_marker"] == FINAL_CERTIFICATION_MARKER
    assert m["database_writes_enabled_by_step10a"] is False
    assert m["database_adapter_added_by_step10a"] is False
    assert m["runtime_files_changed_by_step10a"] is False


def test_manifest_requires_append_only_no_fabrication_downstream_storage():
    m = persistence_contract_manifest()
    assert m["append_only_required"] is True
    assert m["overwrite_allowed"] is False
    assert m["upsert_allowed"] is False
    assert m["delete_allowed"] is False
    assert m["backfill_fabrication_allowed"] is False
    assert m["source_payload_hash_required"] is True
    assert m["utc_observation_timestamp_required"] is True
    assert m["exact_official_game_id_required"] is True


def test_manifest_preserves_step9g_and_all_model_runtime_invariants():
    m = persistence_contract_manifest()
    assert m["step9g_handoff_status_required"] == STEP9G_HANDOFF_STATUS
    assert m["step9g_handoff_marker_required"] == STEP9G_FINAL_CERTIFICATION_MARKER
    assert m["persisted_snapshot_as_model_input_allowed"] is False
    assert m["persisted_snapshot_as_sportsbook_input_allowed"] is False
    for key, value in PROTECTED_INVARIANTS.items():
        assert value is False
        assert m[key] is False


def test_manifest_declares_only_frozen_step9_live_state_and_live_market_sources():
    assert SNAPSHOT_SOURCE_CONTRACTS == {
        "live_game_state": {
            "source_data_type": "mlb_live_game_state_api_response_v1",
            "source_schema_version": 1,
        },
        "live_market": {
            "source_data_type": "mlb_inplay_odds_api_response_v1",
            "source_schema_version": 1,
        },
    }


def test_build_live_game_state_record_is_deterministic_and_valid():
    first = _valid_record()
    second = _valid_record()
    assert first == second
    assert first["official_game_id"] == GAME_ID
    assert first["observed_at_utc"] == OBSERVED
    assert first["record_key"] == f"mlb:{GAME_ID}:live_game_state:{OBSERVED}:{SHA}"
    assert validate_live_snapshot_persistence_record(first)["record_valid"] is True


def test_build_live_market_record_uses_exact_market_source_contract():
    record = _valid_record(
        snapshot_kind="live_market",
        source_data_type="mlb_inplay_odds_api_response_v1",
        payload_sha256="b" * 64,
        source_complete=False,
    )
    assert record["snapshot_kind"] == "live_market"
    assert record["source_complete"] is False
    assert validate_live_snapshot_persistence_record(record)["record_valid"] is True


def test_invalid_snapshot_kind_rejected():
    with pytest.raises(ValueError, match="unsupported snapshot_kind"):
        _valid_record(snapshot_kind="pregame_odds")


@pytest.mark.parametrize("bad_id", [True, False, 0, -1, 824472.0, "824472", "８２４４７２"])
def test_official_game_id_must_be_exact_positive_integer(bad_id):
    with pytest.raises(ValueError, match="positive integer"):
        _valid_record(official_game_id=bad_id)


def test_source_data_type_must_match_snapshot_kind():
    with pytest.raises(ValueError, match="source_data_type"):
        _valid_record(source_data_type="mlb_inplay_odds_api_response_v1")


@pytest.mark.parametrize("bad_version", [True, 0, 2, 1.0, "1"])
def test_source_schema_version_must_be_exact_contract_version(bad_version):
    with pytest.raises(ValueError, match="source_schema_version"):
        _valid_record(source_schema_version=bad_version)


@pytest.mark.parametrize(
    "bad_timestamp",
    [
        "2026-09-01T16:42:00",
        "2026-09-01T16:42:00+00:00",
        "2026-09-01T09:42:00-07:00",
        "not-a-time",
        123,
        None,
    ],
)
def test_observation_timestamp_must_be_utc_rfc3339_z(bad_timestamp):
    with pytest.raises(ValueError, match="UTC RFC3339"):
        _valid_record(observed_at_utc=bad_timestamp)


@pytest.mark.parametrize(
    "bad_hash",
    [
        "a" * 63,
        "a" * 65,
        "A" * 64,
        "g" * 64,
        123,
        None,
    ],
)
def test_payload_hash_must_be_exact_lowercase_sha256(bad_hash):
    with pytest.raises(ValueError, match="64 lowercase hex"):
        _valid_record(payload_sha256=bad_hash)


@pytest.mark.parametrize("bad_complete", [1, 0, "true", None, []])
def test_source_complete_must_be_exact_boolean(bad_complete):
    with pytest.raises(ValueError, match="exact boolean"):
        _valid_record(source_complete=bad_complete)


def test_wrong_step9g_status_or_marker_rejected():
    with pytest.raises(ValueError, match="handoff status"):
        _valid_record(step9g_handoff_status="NOT_GREEN")
    with pytest.raises(ValueError, match="certification marker"):
        _valid_record(step9g_handoff_marker="NOT_GREEN")


def test_validator_rejects_missing_or_non_mapping_record():
    for candidate in (None, 123, "record"):
        result = validate_live_snapshot_persistence_record(candidate)
        assert result["record_valid"] is False
        assert result["failures"] == ["STEP10A_RECORD_MISSING_OR_NOT_MAPPING"]


def test_validator_rejects_tampered_record_key():
    record = _valid_record()
    record["record_key"] = "tampered"
    result = validate_live_snapshot_persistence_record(record)
    assert result["record_valid"] is False
    assert "STEP10A_RECORD_KEY_MISMATCH" in result["failures"]


def test_validator_rejects_any_attempt_to_relax_append_only_invariants():
    fields = [
        "append_only_required",
        "overwrite_allowed",
        "upsert_allowed",
        "delete_allowed",
        "backfill_fabrication_allowed",
        "persisted_snapshot_as_model_input_allowed",
        "persisted_snapshot_as_sportsbook_input_allowed",
    ]
    for field in fields:
        record = _valid_record()
        record[field] = not record[field]
        result = validate_live_snapshot_persistence_record(record)
        assert result["record_valid"] is False
        assert f"STEP10A_INVARIANT_MISMATCH:{field}" in result["failures"]


def test_validator_does_not_mutate_candidate_record():
    record = _valid_record()
    original = deepcopy(record)
    validate_live_snapshot_persistence_record(record)
    assert record == original


def test_manifest_calls_return_isolated_nested_source_contracts():
    first = persistence_contract_manifest()
    second = persistence_contract_manifest()
    first["snapshot_source_contracts"]["live_game_state"]["source_schema_version"] = 999
    first["snapshot_source_contracts"]["new"] = {"bad": True}
    assert second["snapshot_source_contracts"] == SNAPSHOT_SOURCE_CONTRACTS
