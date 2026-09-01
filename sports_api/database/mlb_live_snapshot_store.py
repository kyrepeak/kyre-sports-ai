"""MLB Step 10B — append-only SQLite live snapshot store.

This adapter is the first real database writer behind the frozen Step 10A
persistence contract. It is deliberately not wired into the production API or
Step 9 runtime. Callers must opt in explicitly by constructing valid Step 10A
records and passing the exact JSON payload whose SHA-256 is declared by the
record.

The database itself enforces append-only behavior with UPDATE/DELETE triggers.
Duplicate identical writes are idempotent and never execute an UPDATE/UPSERT.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Mapping

from sports_api.mlb_step10a_live_snapshot_persistence_contract_v1 import (
    DATA_TYPE as STEP10A_DATA_TYPE,
    FINAL_CERTIFICATION_MARKER as STEP10A_FINAL_CERTIFICATION_MARKER,
    validate_live_snapshot_persistence_record,
)

ADAPTER_DATA_TYPE = "mlb_live_snapshot_sqlite_store_v1"
SCHEMA_VERSION = 1
STEP10B_BASE_MAIN_SHA = "cefb91a7b9cfd2c5ebc57182128934384d4f0600"
ADAPTER_STATUS = "STEP10B_APPEND_ONLY_LIVE_SNAPSHOT_STORE_READY"
FINAL_CERTIFICATION_MARKER = "MLB_STEP10B_APPEND_ONLY_LIVE_SNAPSHOT_STORE_GREEN"
TABLE_NAME = "mlb_live_snapshots_v1"


class MLBLiveSnapshotStoreError(RuntimeError):
    """Base Step 10B storage failure."""


class MLBLiveSnapshotIntegrityError(MLBLiveSnapshotStoreError):
    """Stored or candidate data violates the frozen persistence contract."""


class MLBLiveSnapshotNotFoundError(MLBLiveSnapshotStoreError):
    """Requested snapshot does not exist."""


def adapter_manifest() -> dict[str, Any]:
    return {
        "data_type": ADAPTER_DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "step10b_base_main_sha": STEP10B_BASE_MAIN_SHA,
        "adapter_status": ADAPTER_STATUS,
        "final_certification_marker": FINAL_CERTIFICATION_MARKER,
        "step10a_data_type_required": STEP10A_DATA_TYPE,
        "step10a_certification_marker_required": STEP10A_FINAL_CERTIFICATION_MARKER,
        "backend": "sqlite3",
        "append_only": True,
        "insert_allowed": True,
        "idempotent_duplicate_readback_allowed": True,
        "update_allowed": False,
        "upsert_allowed": False,
        "delete_allowed": False,
        "database_level_update_trigger": True,
        "database_level_delete_trigger": True,
        "payload_sha256_verified_before_insert": True,
        "payload_sha256_verified_after_load": True,
        "record_contract_verified_before_insert": True,
        "record_contract_verified_after_load": True,
        "production_runtime_wiring_added_by_step10b": False,
        "automatic_production_writes_enabled": False,
        "persisted_snapshot_as_model_input_allowed": False,
        "persisted_snapshot_as_sportsbook_input_allowed": False,
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _validate_stored_at(value: str) -> str:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise MLBLiveSnapshotIntegrityError("stored_at_utc must be UTC RFC3339 ending in Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise MLBLiveSnapshotIntegrityError("stored_at_utc is invalid") from exc
    if parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise MLBLiveSnapshotIntegrityError("stored_at_utc must be UTC")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _database_path(path: str | Path) -> str:
    if isinstance(path, Path):
        path = str(path)
    if not isinstance(path, str) or not path.strip():
        raise MLBLiveSnapshotStoreError("database path must be a non-empty string or Path")
    if path == ":memory:":
        raise MLBLiveSnapshotStoreError(
            "in-memory SQLite is not supported; use a file-backed path"
        )
    resolved = Path(path).expanduser()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return str(resolved)


def _connect(path: str | Path) -> sqlite3.Connection:
    connection = sqlite3.connect(_database_path(path), timeout=10.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 10000")
    return connection


def initialize_live_snapshot_store(path: str | Path) -> dict[str, Any]:
    """Create the append-only schema. Safe to call repeatedly."""
    connection = _connect(path)
    try:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = FULL")
        connection.executescript(
            f"""
            CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
                record_key TEXT PRIMARY KEY,
                data_type TEXT NOT NULL,
                schema_version INTEGER NOT NULL,
                snapshot_kind TEXT NOT NULL,
                official_game_id INTEGER NOT NULL CHECK (official_game_id > 0),
                observed_at_utc TEXT NOT NULL,
                source_data_type TEXT NOT NULL,
                source_schema_version INTEGER NOT NULL,
                payload_sha256 TEXT NOT NULL,
                source_complete INTEGER NOT NULL CHECK (source_complete IN (0, 1)),
                step9g_handoff_status TEXT NOT NULL,
                step9g_handoff_marker TEXT NOT NULL,
                record_json TEXT NOT NULL,
                source_payload_json TEXT NOT NULL,
                stored_at_utc TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_mlb_live_snapshots_game_kind_time
            ON {TABLE_NAME} (official_game_id, snapshot_kind, observed_at_utc);

            CREATE TRIGGER IF NOT EXISTS trg_mlb_live_snapshots_no_update
            BEFORE UPDATE ON {TABLE_NAME}
            BEGIN
                SELECT RAISE(ABORT, 'MLB_STEP10B_APPEND_ONLY_UPDATE_FORBIDDEN');
            END;

            CREATE TRIGGER IF NOT EXISTS trg_mlb_live_snapshots_no_delete
            BEFORE DELETE ON {TABLE_NAME}
            BEGIN
                SELECT RAISE(ABORT, 'MLB_STEP10B_APPEND_ONLY_DELETE_FORBIDDEN');
            END;
            """
        )
        connection.commit()
        return {
            **adapter_manifest(),
            "schema_ready": True,
            "table_name": TABLE_NAME,
        }
    finally:
        connection.close()


def _validate_payload_json(source_payload_json: str, expected_sha256: str) -> Any:
    if not isinstance(source_payload_json, str):
        raise MLBLiveSnapshotIntegrityError("source_payload_json must be a UTF-8 JSON string")
    try:
        payload = json.loads(source_payload_json)
    except (TypeError, json.JSONDecodeError) as exc:
        raise MLBLiveSnapshotIntegrityError("source_payload_json is not valid JSON") from exc
    actual = hashlib.sha256(source_payload_json.encode("utf-8")).hexdigest()
    if actual != expected_sha256:
        raise MLBLiveSnapshotIntegrityError("source payload SHA-256 does not match Step 10A record")
    return payload


def _canonical_record_json(record: Mapping[str, Any]) -> str:
    return json.dumps(dict(record), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _validated_record(record: Mapping[str, Any] | None) -> dict[str, Any]:
    validation = validate_live_snapshot_persistence_record(record)
    if validation.get("record_valid") is not True:
        failures = validation.get("failures") or ["unknown Step 10A validation failure"]
        raise MLBLiveSnapshotIntegrityError(";".join(str(value) for value in failures))
    assert isinstance(record, Mapping)
    return dict(record)


def append_live_snapshot(
    *,
    path: str | Path,
    record: Mapping[str, Any],
    source_payload_json: str,
    stored_at_utc: str | None = None,
) -> dict[str, Any]:
    """Append one snapshot or return an exact duplicate idempotently.

    This function never executes UPDATE, UPSERT, REPLACE, or DELETE.
    """
    valid_record = _validated_record(record)
    _validate_payload_json(source_payload_json, valid_record["payload_sha256"])
    canonical_record = _canonical_record_json(valid_record)
    stored_at = _validate_stored_at(stored_at_utc or _utc_now())

    initialize_live_snapshot_store(path)
    connection = _connect(path)
    try:
        connection.execute("BEGIN IMMEDIATE")
        existing = connection.execute(
            f"SELECT record_json, source_payload_json FROM {TABLE_NAME} WHERE record_key = ?",
            (valid_record["record_key"],),
        ).fetchone()
        if existing is not None:
            if (
                existing["record_json"] != canonical_record
                or existing["source_payload_json"] != source_payload_json
            ):
                raise MLBLiveSnapshotIntegrityError(
                    "record_key already exists with different immutable content"
                )
            connection.commit()
            return {
                "data_type": ADAPTER_DATA_TYPE,
                "schema_version": SCHEMA_VERSION,
                "record_key": valid_record["record_key"],
                "inserted": False,
                "idempotent_duplicate": True,
            }

        connection.execute(
            f"""
            INSERT INTO {TABLE_NAME} (
                record_key, data_type, schema_version, snapshot_kind,
                official_game_id, observed_at_utc, source_data_type,
                source_schema_version, payload_sha256, source_complete,
                step9g_handoff_status, step9g_handoff_marker, record_json,
                source_payload_json, stored_at_utc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                valid_record["record_key"],
                valid_record["data_type"],
                valid_record["schema_version"],
                valid_record["snapshot_kind"],
                valid_record["official_game_id"],
                valid_record["observed_at_utc"],
                valid_record["source_data_type"],
                valid_record["source_schema_version"],
                valid_record["payload_sha256"],
                1 if valid_record["source_complete"] else 0,
                valid_record["step9g_handoff_status"],
                valid_record["step9g_handoff_marker"],
                canonical_record,
                source_payload_json,
                stored_at,
            ),
        )
        connection.commit()
        return {
            "data_type": ADAPTER_DATA_TYPE,
            "schema_version": SCHEMA_VERSION,
            "record_key": valid_record["record_key"],
            "inserted": True,
            "idempotent_duplicate": False,
            "stored_at_utc": stored_at,
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def _decode_row(row: sqlite3.Row) -> dict[str, Any]:
    try:
        record = json.loads(row["record_json"])
    except json.JSONDecodeError as exc:
        raise MLBLiveSnapshotIntegrityError("stored record_json is corrupt") from exc
    valid_record = _validated_record(record)

    if row["record_key"] != valid_record["record_key"]:
        raise MLBLiveSnapshotIntegrityError("stored record_key disagrees with record_json")
    if row["data_type"] != valid_record["data_type"]:
        raise MLBLiveSnapshotIntegrityError("stored data_type disagrees with record_json")
    if row["schema_version"] != valid_record["schema_version"]:
        raise MLBLiveSnapshotIntegrityError("stored schema_version disagrees with record_json")
    if row["snapshot_kind"] != valid_record["snapshot_kind"]:
        raise MLBLiveSnapshotIntegrityError("stored snapshot_kind disagrees with record_json")
    if row["official_game_id"] != valid_record["official_game_id"]:
        raise MLBLiveSnapshotIntegrityError("stored official_game_id disagrees with record_json")
    if row["observed_at_utc"] != valid_record["observed_at_utc"]:
        raise MLBLiveSnapshotIntegrityError("stored observed_at_utc disagrees with record_json")
    if row["source_data_type"] != valid_record["source_data_type"]:
        raise MLBLiveSnapshotIntegrityError("stored source_data_type disagrees with record_json")
    if row["source_schema_version"] != valid_record["source_schema_version"]:
        raise MLBLiveSnapshotIntegrityError("stored source_schema_version disagrees with record_json")
    if row["payload_sha256"] != valid_record["payload_sha256"]:
        raise MLBLiveSnapshotIntegrityError("stored payload_sha256 disagrees with record_json")
    if bool(row["source_complete"]) is not valid_record["source_complete"]:
        raise MLBLiveSnapshotIntegrityError("stored source_complete disagrees with record_json")
    if row["step9g_handoff_status"] != valid_record["step9g_handoff_status"]:
        raise MLBLiveSnapshotIntegrityError("stored Step 9G status disagrees with record_json")
    if row["step9g_handoff_marker"] != valid_record["step9g_handoff_marker"]:
        raise MLBLiveSnapshotIntegrityError("stored Step 9G marker disagrees with record_json")

    payload = _validate_payload_json(row["source_payload_json"], valid_record["payload_sha256"])
    stored_at = _validate_stored_at(row["stored_at_utc"])
    return {
        "data_type": ADAPTER_DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "record": valid_record,
        "source_payload": payload,
        "source_payload_json": row["source_payload_json"],
        "stored_at_utc": stored_at,
    }


def load_live_snapshot(*, path: str | Path, record_key: str) -> dict[str, Any]:
    if not isinstance(record_key, str) or not record_key:
        raise MLBLiveSnapshotStoreError("record_key must be a non-empty string")
    initialize_live_snapshot_store(path)
    connection = _connect(path)
    try:
        row = connection.execute(
            f"SELECT * FROM {TABLE_NAME} WHERE record_key = ?",
            (record_key,),
        ).fetchone()
        if row is None:
            raise MLBLiveSnapshotNotFoundError(record_key)
        return _decode_row(row)
    finally:
        connection.close()


def list_live_snapshots(
    *,
    path: str | Path,
    official_game_id: int | None = None,
    snapshot_kind: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    if official_game_id is not None and (
        not isinstance(official_game_id, int)
        or isinstance(official_game_id, bool)
        or official_game_id <= 0
    ):
        raise MLBLiveSnapshotStoreError("official_game_id filter must be a positive integer")
    if snapshot_kind is not None and snapshot_kind not in {"live_game_state", "live_market"}:
        raise MLBLiveSnapshotStoreError("unsupported snapshot_kind filter")
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 1000:
        raise MLBLiveSnapshotStoreError("limit must be an integer from 1 through 1000")

    initialize_live_snapshot_store(path)
    clauses: list[str] = []
    params: list[Any] = []
    if official_game_id is not None:
        clauses.append("official_game_id = ?")
        params.append(official_game_id)
    if snapshot_kind is not None:
        clauses.append("snapshot_kind = ?")
        params.append(snapshot_kind)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)

    connection = _connect(path)
    try:
        rows = connection.execute(
            f"SELECT * FROM {TABLE_NAME}{where} "
            "ORDER BY observed_at_utc DESC, record_key DESC LIMIT ?",
            tuple(params),
        ).fetchall()
        return [_decode_row(row) for row in rows]
    finally:
        connection.close()


def count_live_snapshots(*, path: str | Path) -> int:
    initialize_live_snapshot_store(path)
    connection = _connect(path)
    try:
        row = connection.execute(f"SELECT COUNT(*) AS n FROM {TABLE_NAME}").fetchone()
        assert row is not None
        return int(row["n"])
    finally:
        connection.close()


__all__ = [
    "ADAPTER_DATA_TYPE",
    "SCHEMA_VERSION",
    "STEP10B_BASE_MAIN_SHA",
    "ADAPTER_STATUS",
    "FINAL_CERTIFICATION_MARKER",
    "TABLE_NAME",
    "MLBLiveSnapshotStoreError",
    "MLBLiveSnapshotIntegrityError",
    "MLBLiveSnapshotNotFoundError",
    "adapter_manifest",
    "initialize_live_snapshot_store",
    "append_live_snapshot",
    "load_live_snapshot",
    "list_live_snapshots",
    "count_live_snapshots",
]
