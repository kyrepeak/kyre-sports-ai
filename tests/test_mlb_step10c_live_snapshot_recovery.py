import hashlib
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest

from sports_api.mlb_step9g_postfreeze_handoff_v1 import (
    FINAL_CERTIFICATION_MARKER as STEP9G_MARKER,
    HANDOFF_STATUS as STEP9G_STATUS,
)
from sports_api.mlb_step10a_live_snapshot_persistence_contract_v1 import (
    build_live_snapshot_persistence_record,
)
from sports_api.database.mlb_live_snapshot_store import (
    TABLE_NAME,
    append_live_snapshot,
    initialize_live_snapshot_store,
)
from sports_api.database.mlb_live_snapshot_recovery import (
    DELETE_TRIGGER_NAME,
    FINAL_CERTIFICATION_MARKER,
    MLBLiveSnapshotRecoveryError,
    MLBLiveSnapshotRecoveryIntegrityError,
    RECOVERY_DATA_TYPE,
    RECOVERY_STATUS,
    SCHEMA_VERSION,
    STEP10C_BASE_MAIN_SHA,
    UPDATE_TRIGGER_NAME,
    recovery_manifest,
    verify_persisted_live_snapshot_store,
)


GAME_ID = 824472
OBSERVED = "2026-09-01T17:05:00Z"
STORED = "2026-09-01T17:05:01Z"


def _payload_json(**overrides):
    payload = {
        "official_game_id": GAME_ID,
        "inning": 5,
        "inning_half": "bottom",
        "home_score": 3,
        "away_score": 2,
    }
    payload.update(overrides)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _record(payload_json=None, **overrides):
    payload_json = payload_json or _payload_json()
    kwargs = {
        "snapshot_kind": "live_game_state",
        "official_game_id": GAME_ID,
        "observed_at_utc": OBSERVED,
        "source_data_type": "mlb_live_game_state_api_response_v1",
        "source_schema_version": 1,
        "payload_sha256": hashlib.sha256(payload_json.encode("utf-8")).hexdigest(),
        "source_complete": True,
        "step9g_handoff_status": STEP9G_STATUS,
        "step9g_handoff_marker": STEP9G_MARKER,
    }
    kwargs.update(overrides)
    return build_live_snapshot_persistence_record(**kwargs)


def _market_record(payload_json, observed="2026-09-01T17:06:00Z"):
    return _record(
        payload_json,
        snapshot_kind="live_market",
        observed_at_utc=observed,
        source_data_type="mlb_inplay_odds_api_response_v1",
    )


def _write_one(path: Path):
    payload = _payload_json()
    record = _record(payload)
    append_live_snapshot(
        path=path,
        record=record,
        source_payload_json=payload,
        stored_at_utc=STORED,
    )
    return payload, record


def _drop_update_trigger(conn):
    conn.execute(f"DROP TRIGGER {UPDATE_TRIGGER_NAME}")


def _restore_update_trigger(conn):
    conn.execute(
        f"""
        CREATE TRIGGER {UPDATE_TRIGGER_NAME}
        BEFORE UPDATE ON {TABLE_NAME}
        BEGIN
            SELECT RAISE(ABORT, 'MLB_STEP10B_APPEND_ONLY_UPDATE_FORBIDDEN');
        END;
        """
    )


def test_manifest_is_strict_read_only_restart_boundary():
    m = recovery_manifest()
    assert m["data_type"] == RECOVERY_DATA_TYPE == "mlb_live_snapshot_restart_recovery_v1"
    assert m["schema_version"] == SCHEMA_VERSION == 1
    assert m["step10c_base_main_sha"] == STEP10C_BASE_MAIN_SHA
    assert m["recovery_status"] == RECOVERY_STATUS
    assert m["final_certification_marker"] == FINAL_CERTIFICATION_MARKER
    assert m["existing_file_backed_store_required"] is True
    assert m["read_only_database_open"] is True
    assert m["sqlite_integrity_check_required"] is True
    assert m["append_only_triggers_verified"] is True
    assert m["record_contract_reverified"] is True
    assert m["payload_sha256_reverified"] is True
    assert m["fresh_process_restart_supported"] is True
    assert m["recovery_mutates_database"] is False
    assert m["production_runtime_wiring_added_by_step10c"] is False
    assert m["automatic_production_writes_enabled"] is False
    assert m["persisted_snapshot_as_model_input_allowed"] is False
    assert m["persisted_snapshot_as_sportsbook_input_allowed"] is False


def test_verify_valid_store_round_trip(tmp_path):
    path = tmp_path / "snapshots.sqlite3"
    payload, record = _write_one(path)
    result = verify_persisted_live_snapshot_store(path=path)
    assert result["recovery_verified"] is True
    assert result["database_opened_read_only"] is True
    assert result["sqlite_integrity_check"] == "ok"
    assert result["append_only_triggers_verified"] is True
    assert result["row_count"] == 1
    assert result["record_keys"] == [record["record_key"]]
    assert result["rows_by_snapshot_kind"] == {"live_game_state": 1}
    assert result["rows_by_official_game_id"] == {str(GAME_ID): 1}
    assert result["snapshots"][0]["record"] == record
    assert result["snapshots"][0]["source_payload"] == json.loads(payload)
    assert result["snapshots"][0]["source_payload_json"] == payload
    assert result["snapshots"][0]["stored_at_utc"] == STORED
    assert len(result["verified_content_fingerprint_sha256"]) == 64


def test_verification_does_not_mutate_database_file(tmp_path):
    path = tmp_path / "snapshots.sqlite3"
    _write_one(path)
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    verify_persisted_live_snapshot_store(path=path)
    after = hashlib.sha256(path.read_bytes()).hexdigest()
    assert before == after


def test_fresh_python_process_recovers_same_persisted_row(tmp_path):
    path = tmp_path / "snapshots.sqlite3"
    _, record = _write_one(path)
    script = """
import json
import sys
from sports_api.database.mlb_live_snapshot_recovery import verify_persisted_live_snapshot_store
result = verify_persisted_live_snapshot_store(path=sys.argv[1])
print(json.dumps({
    'row_count': result['row_count'],
    'record_keys': result['record_keys'],
    'fingerprint': result['verified_content_fingerprint_sha256'],
    'verified': result['recovery_verified'],
}, sort_keys=True))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script, str(path)],
        check=True,
        capture_output=True,
        text=True,
    )
    child = json.loads(completed.stdout)
    parent = verify_persisted_live_snapshot_store(path=path)
    assert child["verified"] is True
    assert child["row_count"] == 1
    assert child["record_keys"] == [record["record_key"]]
    assert child["fingerprint"] == parent["verified_content_fingerprint_sha256"]


def test_fresh_process_recovery_keeps_database_file_byte_identical(tmp_path):
    path = tmp_path / "snapshots.sqlite3"
    _write_one(path)
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    script = """
import sys
from sports_api.database.mlb_live_snapshot_recovery import verify_persisted_live_snapshot_store
verify_persisted_live_snapshot_store(path=sys.argv[1])
"""
    subprocess.run([sys.executable, "-c", script, str(path)], check=True)
    after = hashlib.sha256(path.read_bytes()).hexdigest()
    assert before == after


@pytest.mark.parametrize("bad", [None, "", " ", ":memory:"])
def test_recovery_rejects_non_file_backed_paths(bad):
    with pytest.raises(MLBLiveSnapshotRecoveryError, match="database|file-backed"):
        verify_persisted_live_snapshot_store(path=bad)


def test_recovery_rejects_missing_database(tmp_path):
    with pytest.raises(MLBLiveSnapshotRecoveryError, match="does not exist"):
        verify_persisted_live_snapshot_store(path=tmp_path / "missing.sqlite3")


def test_recovery_rejects_directory_path(tmp_path):
    with pytest.raises(MLBLiveSnapshotRecoveryError, match="must be a file"):
        verify_persisted_live_snapshot_store(path=tmp_path)


def test_empty_existing_store_fails_default_minimum(tmp_path):
    path = tmp_path / "empty.sqlite3"
    initialize_live_snapshot_store(path)
    with pytest.raises(MLBLiveSnapshotRecoveryIntegrityError, match="below expected minimum"):
        verify_persisted_live_snapshot_store(path=path)


def test_empty_existing_store_can_be_verified_when_explicitly_allowed(tmp_path):
    path = tmp_path / "empty.sqlite3"
    initialize_live_snapshot_store(path)
    result = verify_persisted_live_snapshot_store(path=path, expected_min_rows=0)
    assert result["row_count"] == 0
    assert result["record_keys"] == []
    assert result["recovery_verified"] is True


@pytest.mark.parametrize("bad", [True, -1, 1.0, "1"])
def test_expected_min_rows_must_be_nonnegative_integer(tmp_path, bad):
    with pytest.raises(MLBLiveSnapshotRecoveryError, match="expected_min_rows"):
        verify_persisted_live_snapshot_store(path=tmp_path / "x.sqlite3", expected_min_rows=bad)


@pytest.mark.parametrize("bad", [True, 0, -1, 1.0, "10"])
def test_max_rows_must_be_positive_integer(tmp_path, bad):
    with pytest.raises(MLBLiveSnapshotRecoveryError, match="max_rows"):
        verify_persisted_live_snapshot_store(path=tmp_path / "x.sqlite3", expected_min_rows=0, max_rows=bad)


def test_expected_min_rows_cannot_exceed_max_rows(tmp_path):
    with pytest.raises(MLBLiveSnapshotRecoveryError, match="max_rows"):
        verify_persisted_live_snapshot_store(
            path=tmp_path / "x.sqlite3", expected_min_rows=2, max_rows=1
        )


def test_recovery_bound_fails_closed_when_store_is_larger(tmp_path):
    path = tmp_path / "snapshots.sqlite3"
    for index in range(2):
        payload = _payload_json(inning=index)
        record = _record(payload, observed_at_utc=f"2026-09-01T17:0{index}:00Z")
        append_live_snapshot(path=path, record=record, source_payload_json=payload)
    with pytest.raises(MLBLiveSnapshotRecoveryIntegrityError, match="exceeds recovery bound"):
        verify_persisted_live_snapshot_store(path=path, max_rows=1)


def test_multiple_snapshot_kinds_and_games_recover_deterministically(tmp_path):
    path = tmp_path / "snapshots.sqlite3"

    state1_payload = _payload_json(inning=1)
    state1 = _record(state1_payload, observed_at_utc="2026-09-01T17:01:00Z")
    append_live_snapshot(path=path, record=state1, source_payload_json=state1_payload)

    state2_payload = _payload_json(inning=2)
    state2 = _record(state2_payload, observed_at_utc="2026-09-01T17:02:00Z")
    append_live_snapshot(path=path, record=state2, source_payload_json=state2_payload)

    market_payload = _payload_json(market="moneyline")
    market = _market_record(market_payload, observed="2026-09-01T17:03:00Z")
    append_live_snapshot(path=path, record=market, source_payload_json=market_payload)

    other_payload = _payload_json(official_game_id=999999)
    other = _record(
        other_payload,
        official_game_id=999999,
        observed_at_utc="2026-09-01T17:04:00Z",
    )
    append_live_snapshot(path=path, record=other, source_payload_json=other_payload)

    result = verify_persisted_live_snapshot_store(path=path)
    assert result["record_keys"] == [
        other["record_key"],
        market["record_key"],
        state2["record_key"],
        state1["record_key"],
    ]
    assert result["rows_by_snapshot_kind"] == {
        "live_game_state": 3,
        "live_market": 1,
    }
    assert result["rows_by_official_game_id"] == {
        str(GAME_ID): 3,
        "999999": 1,
    }


def test_missing_update_trigger_fails_closed(tmp_path):
    path = tmp_path / "snapshots.sqlite3"
    _write_one(path)
    with sqlite3.connect(path) as conn:
        conn.execute(f"DROP TRIGGER {UPDATE_TRIGGER_NAME}")
        conn.commit()
    with pytest.raises(MLBLiveSnapshotRecoveryIntegrityError, match="trigger missing"):
        verify_persisted_live_snapshot_store(path=path)


def test_missing_delete_trigger_fails_closed(tmp_path):
    path = tmp_path / "snapshots.sqlite3"
    _write_one(path)
    with sqlite3.connect(path) as conn:
        conn.execute(f"DROP TRIGGER {DELETE_TRIGGER_NAME}")
        conn.commit()
    with pytest.raises(MLBLiveSnapshotRecoveryIntegrityError, match="trigger missing"):
        verify_persisted_live_snapshot_store(path=path)


def test_payload_corruption_fails_closed_after_restart(tmp_path):
    path = tmp_path / "snapshots.sqlite3"
    _, record = _write_one(path)
    with sqlite3.connect(path) as conn:
        _drop_update_trigger(conn)
        conn.execute(
            f"UPDATE {TABLE_NAME} SET source_payload_json=? WHERE record_key=?",
            (_payload_json(home_score=99), record["record_key"]),
        )
        _restore_update_trigger(conn)
        conn.commit()
    with pytest.raises(MLBLiveSnapshotRecoveryIntegrityError, match="SHA-256"):
        verify_persisted_live_snapshot_store(path=path)


def test_noncanonical_record_json_fails_closed(tmp_path):
    path = tmp_path / "snapshots.sqlite3"
    _, record = _write_one(path)
    noncanonical = json.dumps(record, indent=2, ensure_ascii=False)
    with sqlite3.connect(path) as conn:
        _drop_update_trigger(conn)
        conn.execute(
            f"UPDATE {TABLE_NAME} SET record_json=? WHERE record_key=?",
            (noncanonical, record["record_key"]),
        )
        _restore_update_trigger(conn)
        conn.commit()
    with pytest.raises(MLBLiveSnapshotRecoveryIntegrityError, match="canonical immutable"):
        verify_persisted_live_snapshot_store(path=path)


def test_corrupt_record_json_fails_closed(tmp_path):
    path = tmp_path / "snapshots.sqlite3"
    _, record = _write_one(path)
    with sqlite3.connect(path) as conn:
        _drop_update_trigger(conn)
        conn.execute(
            f"UPDATE {TABLE_NAME} SET record_json=? WHERE record_key=?",
            ("{broken", record["record_key"]),
        )
        _restore_update_trigger(conn)
        conn.commit()
    with pytest.raises(MLBLiveSnapshotRecoveryIntegrityError, match="record_json is corrupt"):
        verify_persisted_live_snapshot_store(path=path)


def test_stored_column_disagreement_fails_closed(tmp_path):
    path = tmp_path / "snapshots.sqlite3"
    _, record = _write_one(path)
    with sqlite3.connect(path) as conn:
        _drop_update_trigger(conn)
        conn.execute(
            f"UPDATE {TABLE_NAME} SET observed_at_utc=? WHERE record_key=?",
            ("2026-09-01T17:59:00Z", record["record_key"]),
        )
        _restore_update_trigger(conn)
        conn.commit()
    with pytest.raises(MLBLiveSnapshotRecoveryIntegrityError, match="observed_at_utc disagrees"):
        verify_persisted_live_snapshot_store(path=path)


def test_stored_source_complete_disagreement_fails_closed(tmp_path):
    path = tmp_path / "snapshots.sqlite3"
    _, record = _write_one(path)
    with sqlite3.connect(path) as conn:
        _drop_update_trigger(conn)
        conn.execute(
            f"UPDATE {TABLE_NAME} SET source_complete=0 WHERE record_key=?",
            (record["record_key"],),
        )
        _restore_update_trigger(conn)
        conn.commit()
    with pytest.raises(MLBLiveSnapshotRecoveryIntegrityError, match="source_complete disagrees"):
        verify_persisted_live_snapshot_store(path=path)


def test_invalid_stored_at_timestamp_fails_closed(tmp_path):
    path = tmp_path / "snapshots.sqlite3"
    _, record = _write_one(path)
    with sqlite3.connect(path) as conn:
        _drop_update_trigger(conn)
        conn.execute(
            f"UPDATE {TABLE_NAME} SET stored_at_utc=? WHERE record_key=?",
            ("2026-09-01T17:05:01", record["record_key"]),
        )
        _restore_update_trigger(conn)
        conn.commit()
    with pytest.raises(MLBLiveSnapshotRecoveryIntegrityError, match="stored_at_utc"):
        verify_persisted_live_snapshot_store(path=path)


def test_unicode_payload_survives_restart_verification(tmp_path):
    path = tmp_path / "snapshots.sqlite3"
    payload = _payload_json(note="Curaçao ⚾ restart")
    record = _record(payload)
    append_live_snapshot(path=path, record=record, source_payload_json=payload)
    result = verify_persisted_live_snapshot_store(path=path)
    assert result["snapshots"][0]["source_payload"]["note"] == "Curaçao ⚾ restart"
    assert result["snapshots"][0]["source_payload_json"] == payload
