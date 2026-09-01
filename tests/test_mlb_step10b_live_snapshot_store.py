import hashlib
import json
import sqlite3

import pytest

from sports_api.mlb_step9g_postfreeze_handoff_v1 import (
    FINAL_CERTIFICATION_MARKER as STEP9G_MARKER,
    HANDOFF_STATUS as STEP9G_STATUS,
)
from sports_api.mlb_step10a_live_snapshot_persistence_contract_v1 import (
    FINAL_CERTIFICATION_MARKER as STEP10A_MARKER,
    build_live_snapshot_persistence_record,
)
from sports_api.database.mlb_live_snapshot_store import (
    ADAPTER_DATA_TYPE,
    ADAPTER_STATUS,
    FINAL_CERTIFICATION_MARKER,
    MLBLiveSnapshotIntegrityError,
    MLBLiveSnapshotNotFoundError,
    MLBLiveSnapshotStoreError,
    SCHEMA_VERSION,
    STEP10B_BASE_MAIN_SHA,
    TABLE_NAME,
    adapter_manifest,
    append_live_snapshot,
    count_live_snapshots,
    initialize_live_snapshot_store,
    list_live_snapshots,
    load_live_snapshot,
)


GAME_ID = 824472
OBSERVED = "2026-09-01T16:50:00Z"
STORED = "2026-09-01T16:50:01Z"


def _payload_json(**overrides):
    payload = {
        "official_game_id": GAME_ID,
        "inning": 4,
        "inning_half": "top",
        "home_score": 2,
        "away_score": 1,
    }
    payload.update(overrides)
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


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


def _market_record(payload_json, observed=OBSERVED):
    return _record(
        payload_json,
        snapshot_kind="live_market",
        observed_at_utc=observed,
        source_data_type="mlb_inplay_odds_api_response_v1",
    )


def test_manifest_enables_only_explicit_adapter_io():
    m = adapter_manifest()
    assert m["data_type"] == ADAPTER_DATA_TYPE == "mlb_live_snapshot_sqlite_store_v1"
    assert m["schema_version"] == SCHEMA_VERSION == 1
    assert m["step10b_base_main_sha"] == STEP10B_BASE_MAIN_SHA
    assert m["adapter_status"] == ADAPTER_STATUS
    assert m["final_certification_marker"] == FINAL_CERTIFICATION_MARKER
    assert m["step10a_certification_marker_required"] == STEP10A_MARKER
    assert m["insert_allowed"] is True
    assert m["production_runtime_wiring_added_by_step10b"] is False
    assert m["automatic_production_writes_enabled"] is False


def test_manifest_preserves_append_only_and_downstream_only_boundary():
    m = adapter_manifest()
    assert m["append_only"] is True
    assert m["idempotent_duplicate_readback_allowed"] is True
    assert m["update_allowed"] is False
    assert m["upsert_allowed"] is False
    assert m["delete_allowed"] is False
    assert m["database_level_update_trigger"] is True
    assert m["database_level_delete_trigger"] is True
    assert m["persisted_snapshot_as_model_input_allowed"] is False
    assert m["persisted_snapshot_as_sportsbook_input_allowed"] is False


def test_initialize_creates_schema_and_is_repeatable(tmp_path):
    path = tmp_path / "snapshots.sqlite3"
    first = initialize_live_snapshot_store(path)
    second = initialize_live_snapshot_store(path)
    assert first["schema_ready"] is True
    assert second["schema_ready"] is True
    assert first["table_name"] == TABLE_NAME
    with sqlite3.connect(path) as conn:
        table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (TABLE_NAME,)
        ).fetchone()
        assert table == (TABLE_NAME,)


def test_append_load_and_count_round_trip(tmp_path):
    path = tmp_path / "snapshots.sqlite3"
    payload = _payload_json()
    record = _record(payload)
    result = append_live_snapshot(
        path=path,
        record=record,
        source_payload_json=payload,
        stored_at_utc=STORED,
    )
    assert result["inserted"] is True
    assert result["idempotent_duplicate"] is False
    assert result["stored_at_utc"] == STORED
    assert count_live_snapshots(path=path) == 1

    loaded = load_live_snapshot(path=path, record_key=record["record_key"])
    assert loaded["record"] == record
    assert loaded["source_payload"] == json.loads(payload)
    assert loaded["source_payload_json"] == payload
    assert loaded["stored_at_utc"] == STORED


def test_exact_duplicate_is_idempotent_and_does_not_create_second_row(tmp_path):
    path = tmp_path / "snapshots.sqlite3"
    payload = _payload_json()
    record = _record(payload)
    first = append_live_snapshot(path=path, record=record, source_payload_json=payload)
    second = append_live_snapshot(path=path, record=record, source_payload_json=payload)
    assert first["inserted"] is True
    assert second["inserted"] is False
    assert second["idempotent_duplicate"] is True
    assert count_live_snapshots(path=path) == 1


def test_database_trigger_blocks_direct_update(tmp_path):
    path = tmp_path / "snapshots.sqlite3"
    payload = _payload_json()
    record = _record(payload)
    append_live_snapshot(path=path, record=record, source_payload_json=payload)
    with sqlite3.connect(path) as conn:
        with pytest.raises(sqlite3.IntegrityError, match="APPEND_ONLY_UPDATE_FORBIDDEN"):
            conn.execute(
                f"UPDATE {TABLE_NAME} SET source_complete=0 WHERE record_key=?",
                (record["record_key"],),
            )


def test_database_trigger_blocks_direct_delete(tmp_path):
    path = tmp_path / "snapshots.sqlite3"
    payload = _payload_json()
    record = _record(payload)
    append_live_snapshot(path=path, record=record, source_payload_json=payload)
    with sqlite3.connect(path) as conn:
        with pytest.raises(sqlite3.IntegrityError, match="APPEND_ONLY_DELETE_FORBIDDEN"):
            conn.execute(f"DELETE FROM {TABLE_NAME} WHERE record_key=?", (record["record_key"],))
    assert count_live_snapshots(path=path) == 1


def test_payload_hash_mismatch_fails_before_insert(tmp_path):
    path = tmp_path / "snapshots.sqlite3"
    payload = _payload_json()
    record = _record(payload)
    with pytest.raises(MLBLiveSnapshotIntegrityError, match="SHA-256"):
        append_live_snapshot(
            path=path,
            record=record,
            source_payload_json=_payload_json(home_score=99),
        )
    assert count_live_snapshots(path=path) == 0


def test_invalid_json_payload_fails_closed(tmp_path):
    path = tmp_path / "snapshots.sqlite3"
    payload = _payload_json()
    record = _record(payload)
    with pytest.raises(MLBLiveSnapshotIntegrityError, match="valid JSON"):
        append_live_snapshot(path=path, record=record, source_payload_json="{broken")


def test_invalid_step10a_record_fails_closed(tmp_path):
    path = tmp_path / "snapshots.sqlite3"
    payload = _payload_json()
    record = _record(payload)
    record["overwrite_allowed"] = True
    with pytest.raises(MLBLiveSnapshotIntegrityError, match="overwrite_allowed"):
        append_live_snapshot(path=path, record=record, source_payload_json=payload)


@pytest.mark.parametrize("bad", [None, "", " "])
def test_invalid_database_path_rejected(bad):
    with pytest.raises(MLBLiveSnapshotStoreError, match="database path"):
        initialize_live_snapshot_store(bad)


@pytest.mark.parametrize(
    "bad",
    ["2026-09-01T16:50:01", "2026-09-01T09:50:01-07:00", "bad-time"],
)
def test_stored_at_must_be_utc_z(tmp_path, bad):
    path = tmp_path / "snapshots.sqlite3"
    payload = _payload_json()
    record = _record(payload)
    with pytest.raises(MLBLiveSnapshotIntegrityError, match="stored_at_utc"):
        append_live_snapshot(
            path=path,
            record=record,
            source_payload_json=payload,
            stored_at_utc=bad,
        )


def test_load_missing_record_raises_not_found(tmp_path):
    path = tmp_path / "snapshots.sqlite3"
    with pytest.raises(MLBLiveSnapshotNotFoundError):
        load_live_snapshot(path=path, record_key="missing")


@pytest.mark.parametrize("bad", [None, ""])
def test_load_requires_nonempty_record_key(tmp_path, bad):
    with pytest.raises(MLBLiveSnapshotStoreError, match="record_key"):
        load_live_snapshot(path=tmp_path / "x.sqlite3", record_key=bad)


def test_list_orders_newest_first_and_filters_by_game_and_kind(tmp_path):
    path = tmp_path / "snapshots.sqlite3"

    state1_payload = _payload_json(inning=1)
    state1 = _record(state1_payload, observed_at_utc="2026-09-01T16:40:00Z")
    append_live_snapshot(path=path, record=state1, source_payload_json=state1_payload)

    state2_payload = _payload_json(inning=2)
    state2 = _record(state2_payload, observed_at_utc="2026-09-01T16:45:00Z")
    append_live_snapshot(path=path, record=state2, source_payload_json=state2_payload)

    market_payload = _payload_json(market="moneyline")
    market = _market_record(market_payload, observed="2026-09-01T16:47:00Z")
    append_live_snapshot(path=path, record=market, source_payload_json=market_payload)

    other_payload = _payload_json(official_game_id=999999)
    other = _record(other_payload, official_game_id=999999, observed_at_utc="2026-09-01T16:49:00Z")
    append_live_snapshot(path=path, record=other, source_payload_json=other_payload)

    all_rows = list_live_snapshots(path=path)
    assert [row["record"]["record_key"] for row in all_rows] == [
        other["record_key"], market["record_key"], state2["record_key"], state1["record_key"]
    ]

    state_rows = list_live_snapshots(
        path=path,
        official_game_id=GAME_ID,
        snapshot_kind="live_game_state",
    )
    assert [row["record"]["record_key"] for row in state_rows] == [
        state2["record_key"], state1["record_key"]
    ]


def test_list_limit_is_enforced(tmp_path):
    path = tmp_path / "snapshots.sqlite3"
    for index in range(3):
        payload = _payload_json(inning=index)
        record = _record(payload, observed_at_utc=f"2026-09-01T16:4{index}:00Z")
        append_live_snapshot(path=path, record=record, source_payload_json=payload)
    assert len(list_live_snapshots(path=path, limit=2)) == 2


@pytest.mark.parametrize("bad", [True, 0, -1, "824472"])
def test_list_game_filter_must_be_positive_integer(tmp_path, bad):
    with pytest.raises(MLBLiveSnapshotStoreError, match="positive integer"):
        list_live_snapshots(path=tmp_path / "x.sqlite3", official_game_id=bad)


@pytest.mark.parametrize("bad", ["pregame", "", 3])
def test_list_snapshot_kind_filter_must_be_supported(tmp_path, bad):
    with pytest.raises(MLBLiveSnapshotStoreError, match="snapshot_kind"):
        list_live_snapshots(path=tmp_path / "x.sqlite3", snapshot_kind=bad)


@pytest.mark.parametrize("bad", [True, 0, 1001, 1.0, "10"])
def test_list_limit_must_be_bounded_integer(tmp_path, bad):
    with pytest.raises(MLBLiveSnapshotStoreError, match="limit"):
        list_live_snapshots(path=tmp_path / "x.sqlite3", limit=bad)


def test_unicode_payload_round_trip_uses_exact_input_bytes(tmp_path):
    path = tmp_path / "snapshots.sqlite3"
    payload = json.dumps(
        {"official_game_id": GAME_ID, "note": "Curaçao ⚾"},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    record = _record(payload)
    append_live_snapshot(path=path, record=record, source_payload_json=payload)
    loaded = load_live_snapshot(path=path, record_key=record["record_key"])
    assert loaded["source_payload_json"] == payload
    assert loaded["source_payload"]["note"] == "Curaçao ⚾"


def test_load_detects_stored_payload_corruption_even_if_trigger_removed(tmp_path):
    path = tmp_path / "snapshots.sqlite3"
    payload = _payload_json()
    record = _record(payload)
    append_live_snapshot(path=path, record=record, source_payload_json=payload)
    with sqlite3.connect(path) as conn:
        conn.execute("DROP TRIGGER trg_mlb_live_snapshots_no_update")
        conn.execute(
            f"UPDATE {TABLE_NAME} SET source_payload_json=? WHERE record_key=?",
            (_payload_json(home_score=88), record["record_key"]),
        )
        conn.commit()
    with pytest.raises(MLBLiveSnapshotIntegrityError, match="SHA-256"):
        load_live_snapshot(path=path, record_key=record["record_key"])


def test_load_detects_stored_record_json_corruption_even_if_trigger_removed(tmp_path):
    path = tmp_path / "snapshots.sqlite3"
    payload = _payload_json()
    record = _record(payload)
    append_live_snapshot(path=path, record=record, source_payload_json=payload)
    with sqlite3.connect(path) as conn:
        conn.execute("DROP TRIGGER trg_mlb_live_snapshots_no_update")
        conn.execute(
            f"UPDATE {TABLE_NAME} SET record_json=? WHERE record_key=?",
            ("{broken", record["record_key"]),
        )
        conn.commit()
    with pytest.raises(MLBLiveSnapshotIntegrityError, match="record_json is corrupt"):
        load_live_snapshot(path=path, record_key=record["record_key"])


def test_file_backed_store_survives_fresh_connection(tmp_path):
    path = tmp_path / "snapshots.sqlite3"
    payload = _payload_json()
    record = _record(payload)
    append_live_snapshot(path=path, record=record, source_payload_json=payload)

    # Every public operation opens a fresh sqlite3 connection. A successful
    # load here proves the adapter is file-backed rather than process-memory state.
    loaded = load_live_snapshot(path=path, record_key=record["record_key"])
    assert loaded["record"]["record_key"] == record["record_key"]
    assert count_live_snapshots(path=path) == 1
