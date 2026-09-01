"""MLB Step 10C — durable restart recovery and persisted snapshot verification.

This module verifies a Step 10B SQLite snapshot store from a fresh process or
connection without mutating it. Recovery is deliberately downstream-only: it
may validate and return persisted snapshots, but it does not wire them into the
frozen MLB runtime, model, simulation, ranking, or sportsbook inputs.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
from typing import Any, Mapping
from urllib.parse import quote

from sports_api.mlb_step10a_live_snapshot_persistence_contract_v1 import (
    FINAL_CERTIFICATION_MARKER as STEP10A_FINAL_CERTIFICATION_MARKER,
    validate_live_snapshot_persistence_record,
)
from sports_api.database.mlb_live_snapshot_store import (
    ADAPTER_DATA_TYPE as STEP10B_ADAPTER_DATA_TYPE,
    FINAL_CERTIFICATION_MARKER as STEP10B_FINAL_CERTIFICATION_MARKER,
    TABLE_NAME,
)

RECOVERY_DATA_TYPE = "mlb_live_snapshot_restart_recovery_v1"
SCHEMA_VERSION = 1
STEP10C_BASE_MAIN_SHA = "97efc7da1fef517b7dc1f6d17a04375d505622f3"
RECOVERY_STATUS = "STEP10C_DURABLE_RESTART_RECOVERY_READY"
FINAL_CERTIFICATION_MARKER = "MLB_STEP10C_DURABLE_RESTART_RECOVERY_GREEN"
UPDATE_TRIGGER_NAME = "trg_mlb_live_snapshots_no_update"
DELETE_TRIGGER_NAME = "trg_mlb_live_snapshots_no_delete"
UPDATE_TRIGGER_MARKER = "MLB_STEP10B_APPEND_ONLY_UPDATE_FORBIDDEN"
DELETE_TRIGGER_MARKER = "MLB_STEP10B_APPEND_ONLY_DELETE_FORBIDDEN"


class MLBLiveSnapshotRecoveryError(RuntimeError):
    """Base Step 10C recovery failure."""


class MLBLiveSnapshotRecoveryIntegrityError(MLBLiveSnapshotRecoveryError):
    """Persisted store contents or schema failed closed verification."""


def recovery_manifest() -> dict[str, Any]:
    return {
        "data_type": RECOVERY_DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "step10c_base_main_sha": STEP10C_BASE_MAIN_SHA,
        "recovery_status": RECOVERY_STATUS,
        "final_certification_marker": FINAL_CERTIFICATION_MARKER,
        "step10a_certification_marker_required": STEP10A_FINAL_CERTIFICATION_MARKER,
        "step10b_adapter_data_type_required": STEP10B_ADAPTER_DATA_TYPE,
        "step10b_certification_marker_required": STEP10B_FINAL_CERTIFICATION_MARKER,
        "existing_file_backed_store_required": True,
        "read_only_database_open": True,
        "sqlite_integrity_check_required": True,
        "append_only_triggers_verified": True,
        "record_contract_reverified": True,
        "payload_sha256_reverified": True,
        "stored_column_consistency_reverified": True,
        "fresh_process_restart_supported": True,
        "recovery_mutates_database": False,
        "production_runtime_wiring_added_by_step10c": False,
        "automatic_production_writes_enabled": False,
        "persisted_snapshot_as_model_input_allowed": False,
        "persisted_snapshot_as_sportsbook_input_allowed": False,
    }


def _existing_database_path(path: str | Path) -> Path:
    if isinstance(path, Path):
        value = path
    elif isinstance(path, str) and path.strip():
        if path == ":memory:":
            raise MLBLiveSnapshotRecoveryError(
                "restart recovery requires an existing file-backed database"
            )
        value = Path(path).expanduser()
    else:
        raise MLBLiveSnapshotRecoveryError(
            "database path must be a non-empty string or Path"
        )

    resolved = value.resolve()
    if not resolved.exists():
        raise MLBLiveSnapshotRecoveryError("persisted database does not exist")
    if not resolved.is_file():
        raise MLBLiveSnapshotRecoveryError("persisted database path must be a file")
    return resolved


def _connect_read_only(path: Path) -> sqlite3.Connection:
    uri_path = quote(path.as_posix(), safe="/")
    connection = sqlite3.connect(
        f"file:{uri_path}?mode=ro",
        uri=True,
        timeout=10.0,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    connection.execute("PRAGMA busy_timeout = 10000")
    return connection


def _validate_utc_z(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise MLBLiveSnapshotRecoveryIntegrityError(
            f"{field_name} must be UTC RFC3339 ending in Z"
        )
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise MLBLiveSnapshotRecoveryIntegrityError(
            f"{field_name} is invalid"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise MLBLiveSnapshotRecoveryIntegrityError(f"{field_name} must be UTC")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical_record_json(record: Mapping[str, Any]) -> str:
    return json.dumps(dict(record), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _validate_schema(connection: sqlite3.Connection) -> None:
    integrity = connection.execute("PRAGMA integrity_check").fetchall()
    integrity_values = [str(row[0]) for row in integrity]
    if integrity_values != ["ok"]:
        raise MLBLiveSnapshotRecoveryIntegrityError(
            "sqlite integrity_check failed: " + ";".join(integrity_values)
        )

    table = connection.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name=?",
        (TABLE_NAME,),
    ).fetchone()
    if table is None or not table["sql"]:
        raise MLBLiveSnapshotRecoveryIntegrityError("Step 10B snapshot table is missing")

    trigger_rows = connection.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='trigger' AND tbl_name=?",
        (TABLE_NAME,),
    ).fetchall()
    triggers = {row["name"]: row["sql"] or "" for row in trigger_rows}
    required = {
        UPDATE_TRIGGER_NAME: UPDATE_TRIGGER_MARKER,
        DELETE_TRIGGER_NAME: DELETE_TRIGGER_MARKER,
    }
    for trigger_name, marker in required.items():
        sql = triggers.get(trigger_name)
        if sql is None:
            raise MLBLiveSnapshotRecoveryIntegrityError(
                f"required append-only trigger missing: {trigger_name}"
            )
        if marker not in sql:
            raise MLBLiveSnapshotRecoveryIntegrityError(
                f"append-only trigger marker mismatch: {trigger_name}"
            )


def _decode_verified_row(row: sqlite3.Row) -> dict[str, Any]:
    try:
        record = json.loads(row["record_json"])
    except (TypeError, json.JSONDecodeError) as exc:
        raise MLBLiveSnapshotRecoveryIntegrityError(
            "stored record_json is corrupt"
        ) from exc
    if not isinstance(record, dict):
        raise MLBLiveSnapshotRecoveryIntegrityError("stored record_json must decode to an object")

    validation = validate_live_snapshot_persistence_record(record)
    if validation.get("record_valid") is not True:
        failures = validation.get("failures") or ["unknown Step 10A validation failure"]
        raise MLBLiveSnapshotRecoveryIntegrityError(
            "stored Step 10A record invalid: " + ";".join(str(value) for value in failures)
        )

    canonical_record = _canonical_record_json(record)
    if row["record_json"] != canonical_record:
        raise MLBLiveSnapshotRecoveryIntegrityError(
            "stored record_json is not the canonical immutable Step 10B representation"
        )

    expected_columns = {
        "record_key": record["record_key"],
        "data_type": record["data_type"],
        "schema_version": record["schema_version"],
        "snapshot_kind": record["snapshot_kind"],
        "official_game_id": record["official_game_id"],
        "observed_at_utc": record["observed_at_utc"],
        "source_data_type": record["source_data_type"],
        "source_schema_version": record["source_schema_version"],
        "payload_sha256": record["payload_sha256"],
        "step9g_handoff_status": record["step9g_handoff_status"],
        "step9g_handoff_marker": record["step9g_handoff_marker"],
    }
    for column, expected in expected_columns.items():
        if row[column] != expected:
            raise MLBLiveSnapshotRecoveryIntegrityError(
                f"stored {column} disagrees with record_json"
            )

    if row["source_complete"] not in (0, 1):
        raise MLBLiveSnapshotRecoveryIntegrityError("stored source_complete is not boolean")
    if bool(row["source_complete"]) is not record["source_complete"]:
        raise MLBLiveSnapshotRecoveryIntegrityError(
            "stored source_complete disagrees with record_json"
        )

    source_payload_json = row["source_payload_json"]
    if not isinstance(source_payload_json, str):
        raise MLBLiveSnapshotRecoveryIntegrityError("stored source_payload_json must be text")
    try:
        source_payload = json.loads(source_payload_json)
    except (TypeError, json.JSONDecodeError) as exc:
        raise MLBLiveSnapshotRecoveryIntegrityError(
            "stored source_payload_json is corrupt"
        ) from exc
    actual_sha256 = hashlib.sha256(source_payload_json.encode("utf-8")).hexdigest()
    if actual_sha256 != record["payload_sha256"]:
        raise MLBLiveSnapshotRecoveryIntegrityError(
            "stored source payload SHA-256 does not match Step 10A record"
        )

    stored_at = _validate_utc_z(row["stored_at_utc"], "stored_at_utc")
    observed_at = _validate_utc_z(record["observed_at_utc"], "observed_at_utc")
    return {
        "record": record,
        "source_payload": source_payload,
        "source_payload_json": source_payload_json,
        "stored_at_utc": stored_at,
        "observed_at_utc": observed_at,
    }


def verify_persisted_live_snapshot_store(
    *,
    path: str | Path,
    expected_min_rows: int = 1,
    max_rows: int = 100000,
) -> dict[str, Any]:
    """Open an existing Step 10B database read-only and fail closed on corruption."""
    if (
        not isinstance(expected_min_rows, int)
        or isinstance(expected_min_rows, bool)
        or expected_min_rows < 0
    ):
        raise MLBLiveSnapshotRecoveryError("expected_min_rows must be a non-negative integer")
    if (
        not isinstance(max_rows, int)
        or isinstance(max_rows, bool)
        or max_rows < 1
        or expected_min_rows > max_rows
    ):
        raise MLBLiveSnapshotRecoveryError(
            "max_rows must be a positive integer not smaller than expected_min_rows"
        )

    database_path = _existing_database_path(path)
    connection = _connect_read_only(database_path)
    try:
        _validate_schema(connection)
        count_row = connection.execute(
            f"SELECT COUNT(*) AS n FROM {TABLE_NAME}"
        ).fetchone()
        assert count_row is not None
        row_count = int(count_row["n"])
        if row_count < expected_min_rows:
            raise MLBLiveSnapshotRecoveryIntegrityError(
                f"persisted snapshot row count {row_count} is below expected minimum {expected_min_rows}"
            )
        if row_count > max_rows:
            raise MLBLiveSnapshotRecoveryIntegrityError(
                f"persisted snapshot row count {row_count} exceeds recovery bound {max_rows}"
            )

        rows = connection.execute(
            f"SELECT * FROM {TABLE_NAME} ORDER BY observed_at_utc DESC, record_key DESC"
        ).fetchall()
        if len(rows) != row_count:
            raise MLBLiveSnapshotRecoveryIntegrityError(
                "snapshot count changed during read-only recovery scan"
            )

        snapshots = [_decode_verified_row(row) for row in rows]
        record_keys = [snapshot["record"]["record_key"] for snapshot in snapshots]
        if len(set(record_keys)) != len(record_keys):
            raise MLBLiveSnapshotRecoveryIntegrityError(
                "duplicate record_key detected during recovery"
            )

        by_kind: dict[str, int] = {}
        by_game: dict[str, int] = {}
        fingerprint = hashlib.sha256()
        for snapshot in snapshots:
            record = snapshot["record"]
            kind = record["snapshot_kind"]
            game_key = str(record["official_game_id"])
            by_kind[kind] = by_kind.get(kind, 0) + 1
            by_game[game_key] = by_game.get(game_key, 0) + 1
            fingerprint.update(record["record_key"].encode("utf-8"))
            fingerprint.update(b"\0")
            fingerprint.update(record["payload_sha256"].encode("ascii"))
            fingerprint.update(b"\0")
            fingerprint.update(snapshot["stored_at_utc"].encode("ascii"))
            fingerprint.update(b"\n")

        return {
            **recovery_manifest(),
            "database_path": str(database_path),
            "database_opened_read_only": True,
            "sqlite_integrity_check": "ok",
            "append_only_triggers_verified": True,
            "row_count": row_count,
            "record_keys": record_keys,
            "rows_by_snapshot_kind": by_kind,
            "rows_by_official_game_id": by_game,
            "verified_content_fingerprint_sha256": fingerprint.hexdigest(),
            "snapshots": snapshots,
            "recovery_verified": True,
        }
    except sqlite3.DatabaseError as exc:
        raise MLBLiveSnapshotRecoveryIntegrityError(
            f"sqlite recovery verification failed: {exc}"
        ) from exc
    finally:
        connection.close()


__all__ = [
    "RECOVERY_DATA_TYPE",
    "SCHEMA_VERSION",
    "STEP10C_BASE_MAIN_SHA",
    "RECOVERY_STATUS",
    "FINAL_CERTIFICATION_MARKER",
    "UPDATE_TRIGGER_NAME",
    "DELETE_TRIGGER_NAME",
    "MLBLiveSnapshotRecoveryError",
    "MLBLiveSnapshotRecoveryIntegrityError",
    "recovery_manifest",
    "verify_persisted_live_snapshot_store",
]
