"""WNBA Step 5O durable prop-feed collection snapshots and provider health history."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from typing import Any

MODEL_SOURCE = "Kyre Sports API WNBA Step 5O prop-feed store"
MODEL_VERSION = "wnba_step_5o_prop_feed_store_v1"
STORE_SCHEMA_VERSION = "wnba_step_5o_prop_feed_store_sqlite_v1"
STORE_PATH_ENV = "WNBA_PROP_FEED_STORE_PATH"

SUCCESS_OUTCOMES = frozenset({"success", "success_empty_slate"})
MAX_LIST_LIMIT = 1_000
MAX_HEALTH_ATTEMPTS = 100


class WNBAPropFeedStoreError(RuntimeError):
    pass


class WNBAPropFeedStoreConflictError(WNBAPropFeedStoreError):
    pass


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().isoformat()


def _hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _parse_timestamp(value: Any) -> datetime | None:
    text = _clean(value)
    if not text:
        return None
    normalized = text[:-1] + "+00:00" if text.endswith(("Z", "z")) else text
    try:
        result = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if result.tzinfo is None or result.utcoffset() is None:
        return None
    return result.astimezone(timezone.utc)


def resolve_store_path(path: str | Path | None = None, env: Mapping[str, str] | None = None) -> Path:
    if path is not None:
        result = Path(path).expanduser()
    else:
        environment = os.environ if env is None else env
        configured = _clean(environment.get(STORE_PATH_ENV))
        result = Path(configured).expanduser() if configured else Path(__file__).with_name("wnba_prop_feed_store.sqlite3")
    if result.exists() and result.is_dir():
        raise WNBAPropFeedStoreError("WNBA Step 5O prop-feed store path cannot be a directory.")
    return result


def _connect(path: str | Path | None = None, env: Mapping[str, str] | None = None) -> sqlite3.Connection:
    resolved = resolve_store_path(path, env)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    try:
        connection = sqlite3.connect(str(resolved), timeout=10.0)
    except sqlite3.Error as exc:
        raise WNBAPropFeedStoreError(f"WNBA Step 5O could not open prop-feed store: {exc}") from exc
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA busy_timeout = 10000")
    return connection


def initialize_store(path: str | Path | None = None, env: Mapping[str, str] | None = None) -> dict[str, Any]:
    resolved = resolve_store_path(path, env)
    with _connect(resolved) as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS wnba_prop_feed_metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS wnba_prop_feed_snapshots (
                snapshot_id TEXT PRIMARY KEY,
                snapshot_fingerprint_sha256 TEXT NOT NULL UNIQUE,
                provider_id TEXT NOT NULL,
                feed_source TEXT NOT NULL,
                feed_format TEXT NOT NULL,
                odds_format TEXT NOT NULL,
                season INTEGER NOT NULL,
                date TEXT NOT NULL,
                collected_at_utc TEXT NOT NULL,
                stored_at_utc TEXT NOT NULL,
                collection_id TEXT,
                collection_fingerprint_sha256 TEXT,
                source_raw_feed_sha256 TEXT,
                normalized_input_feed_sha256 TEXT NOT NULL,
                collection_json TEXT NOT NULL,
                normalized_input_feed_json TEXT NOT NULL,
                adapter_json TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_wnba_feed_snapshots_provider_collected
                ON wnba_prop_feed_snapshots(provider_id, collected_at_utc DESC);
            CREATE INDEX IF NOT EXISTS idx_wnba_feed_snapshots_date
                ON wnba_prop_feed_snapshots(date, season, collected_at_utc DESC);

            CREATE TABLE IF NOT EXISTS wnba_prop_feed_attempts (
                attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider_id TEXT NOT NULL,
                failover_rank INTEGER NOT NULL,
                started_at_utc TEXT NOT NULL,
                completed_at_utc TEXT NOT NULL,
                outcome TEXT NOT NULL,
                error_type TEXT,
                snapshot_id TEXT,
                normalized_line_count INTEGER,
                playable_game_count INTEGER,
                detail_json TEXT,
                FOREIGN KEY(snapshot_id) REFERENCES wnba_prop_feed_snapshots(snapshot_id)
            );

            CREATE INDEX IF NOT EXISTS idx_wnba_feed_attempts_provider_completed
                ON wnba_prop_feed_attempts(provider_id, completed_at_utc DESC, attempt_id DESC);
            CREATE INDEX IF NOT EXISTS idx_wnba_feed_attempts_outcome
                ON wnba_prop_feed_attempts(outcome, completed_at_utc DESC);

            CREATE TRIGGER IF NOT EXISTS wnba_prop_feed_snapshots_no_update
            BEFORE UPDATE ON wnba_prop_feed_snapshots
            BEGIN
                SELECT RAISE(ABORT, 'WNBA Step 5O feed snapshots are immutable');
            END;

            CREATE TRIGGER IF NOT EXISTS wnba_prop_feed_snapshots_no_delete
            BEFORE DELETE ON wnba_prop_feed_snapshots
            BEGIN
                SELECT RAISE(ABORT, 'WNBA Step 5O feed snapshots are immutable');
            END;

            CREATE TRIGGER IF NOT EXISTS wnba_prop_feed_attempts_no_update
            BEFORE UPDATE ON wnba_prop_feed_attempts
            BEGIN
                SELECT RAISE(ABORT, 'WNBA Step 5O feed attempts are append-only');
            END;

            CREATE TRIGGER IF NOT EXISTS wnba_prop_feed_attempts_no_delete
            BEFORE DELETE ON wnba_prop_feed_attempts
            BEGIN
                SELECT RAISE(ABORT, 'WNBA Step 5O feed attempts are append-only');
            END;
            """
        )
        connection.execute(
            "INSERT OR IGNORE INTO wnba_prop_feed_metadata(key, value) VALUES (?, ?)",
            ("schema_version", STORE_SCHEMA_VERSION),
        )
        existing = connection.execute(
            "SELECT value FROM wnba_prop_feed_metadata WHERE key = 'schema_version'"
        ).fetchone()
        if not existing or existing["value"] != STORE_SCHEMA_VERSION:
            raise WNBAPropFeedStoreConflictError(
                "WNBA Step 5O prop-feed store schema version does not match this code version."
            )
    return {
        "source": MODEL_SOURCE,
        "model_version": MODEL_VERSION,
        "schema_version": STORE_SCHEMA_VERSION,
        "store_path": str(resolved),
    }


def _snapshot_payload(
    *,
    provider_id: str,
    collection: dict[str, Any],
    feed_source: str,
    feed_format: str,
    odds_format: str,
    normalized_input_feed: dict[str, Any],
    adapter: dict[str, Any] | None,
) -> dict[str, Any]:
    provider = _clean(provider_id)
    source = _clean(feed_source)
    format_name = _clean(feed_format)
    odds_name = _clean(odds_format)
    if not all((provider, source, format_name, odds_name)):
        raise WNBAPropFeedStoreError("WNBA Step 5O snapshot identity fields cannot be empty.")
    if not isinstance(collection, dict) or not isinstance(normalized_input_feed, dict):
        raise WNBAPropFeedStoreError("WNBA Step 5O snapshot collection/feed must be objects.")
    season = collection.get("season")
    date = _clean(collection.get("date"))
    collected = _clean(collection.get("collected_at_utc"))
    if not isinstance(season, int) or isinstance(season, bool) or season <= 0 or not date or not _parse_timestamp(collected):
        raise WNBAPropFeedStoreError("WNBA Step 5O snapshot collection identity is incomplete.")
    input_hash = _hash(normalized_input_feed)
    identity = {
        "provider_id": provider,
        "collection_id": collection.get("collection_id"),
        "collection_fingerprint_sha256": collection.get("collection_fingerprint_sha256"),
        "season": season,
        "date": date,
        "collected_at_utc": collected,
        "feed_source": source,
        "feed_format": format_name,
        "odds_format": odds_name,
        "normalized_input_feed_sha256": input_hash,
    }
    fingerprint = _hash(identity)
    return {
        "snapshot_id": f"wnba-5o-feed-{fingerprint[:20]}",
        "snapshot_fingerprint_sha256": fingerprint,
        "provider_id": provider,
        "feed_source": source,
        "feed_format": format_name,
        "odds_format": odds_name,
        "season": season,
        "date": date,
        "collected_at_utc": collected,
        "stored_at_utc": _utc_now_iso(),
        "collection_id": _clean(collection.get("collection_id")),
        "collection_fingerprint_sha256": _clean(collection.get("collection_fingerprint_sha256")),
        "source_raw_feed_sha256": _clean(collection.get("raw_feed_sha256")),
        "normalized_input_feed_sha256": input_hash,
        "collection_json": _json(collection),
        "normalized_input_feed_json": _json(normalized_input_feed),
        "adapter_json": _json(adapter) if adapter is not None else None,
    }


def persist_feed_snapshot(
    *,
    provider_id: str,
    collection: dict[str, Any],
    feed_source: str,
    feed_format: str,
    odds_format: str,
    normalized_input_feed: dict[str, Any],
    adapter: dict[str, Any] | None = None,
    path: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    initialize_store(path, env)
    payload = _snapshot_payload(
        provider_id=provider_id,
        collection=collection,
        feed_source=feed_source,
        feed_format=feed_format,
        odds_format=odds_format,
        normalized_input_feed=normalized_input_feed,
        adapter=adapter,
    )
    resolved = resolve_store_path(path, env)
    inserted = False
    try:
        with _connect(resolved) as connection:
            existing = connection.execute(
                "SELECT * FROM wnba_prop_feed_snapshots WHERE snapshot_id = ?",
                (payload["snapshot_id"],),
            ).fetchone()
            if existing:
                if existing["snapshot_fingerprint_sha256"] != payload["snapshot_fingerprint_sha256"]:
                    raise WNBAPropFeedStoreConflictError(
                        "WNBA Step 5O snapshot id collision detected."
                    )
            else:
                connection.execute(
                    """
                    INSERT INTO wnba_prop_feed_snapshots (
                        snapshot_id, snapshot_fingerprint_sha256, provider_id, feed_source,
                        feed_format, odds_format, season, date, collected_at_utc, stored_at_utc,
                        collection_id, collection_fingerprint_sha256, source_raw_feed_sha256,
                        normalized_input_feed_sha256, collection_json,
                        normalized_input_feed_json, adapter_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        payload["snapshot_id"], payload["snapshot_fingerprint_sha256"],
                        payload["provider_id"], payload["feed_source"], payload["feed_format"],
                        payload["odds_format"], payload["season"], payload["date"],
                        payload["collected_at_utc"], payload["stored_at_utc"],
                        payload["collection_id"], payload["collection_fingerprint_sha256"],
                        payload["source_raw_feed_sha256"], payload["normalized_input_feed_sha256"],
                        payload["collection_json"], payload["normalized_input_feed_json"],
                        payload["adapter_json"],
                    ),
                )
                inserted = True
    except sqlite3.IntegrityError as exc:
        raise WNBAPropFeedStoreConflictError(f"WNBA Step 5O snapshot conflict: {exc}") from exc
    except sqlite3.Error as exc:
        raise WNBAPropFeedStoreError(f"WNBA Step 5O could not persist feed snapshot: {exc}") from exc
    return {
        "snapshot_id": payload["snapshot_id"],
        "snapshot_fingerprint_sha256": payload["snapshot_fingerprint_sha256"],
        "provider_id": payload["provider_id"],
        "collected_at_utc": payload["collected_at_utc"],
        "normalized_input_feed_sha256": payload["normalized_input_feed_sha256"],
        "inserted": inserted,
        "idempotent_replay": not inserted,
        "store_path": str(resolved),
    }


def append_feed_attempt(
    *,
    provider_id: str,
    failover_rank: int,
    started_at_utc: str,
    outcome: str,
    error_type: str | None = None,
    snapshot_id: str | None = None,
    normalized_line_count: int | None = None,
    playable_game_count: int | None = None,
    detail: dict[str, Any] | None = None,
    completed_at_utc: str | None = None,
    path: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    initialize_store(path, env)
    provider = _clean(provider_id)
    outcome_text = _clean(outcome)
    if not provider or not outcome_text:
        raise WNBAPropFeedStoreError("WNBA Step 5O attempt provider/outcome cannot be empty.")
    if not isinstance(failover_rank, int) or isinstance(failover_rank, bool) or failover_rank < 1:
        raise WNBAPropFeedStoreError("WNBA Step 5O failover_rank must be a positive integer.")
    if not _parse_timestamp(started_at_utc):
        raise WNBAPropFeedStoreError("WNBA Step 5O attempt start timestamp is invalid.")
    completed = completed_at_utc or _utc_now_iso()
    if not _parse_timestamp(completed):
        raise WNBAPropFeedStoreError("WNBA Step 5O attempt completion timestamp is invalid.")
    resolved = resolve_store_path(path, env)
    try:
        with _connect(resolved) as connection:
            cursor = connection.execute(
                """
                INSERT INTO wnba_prop_feed_attempts (
                    provider_id, failover_rank, started_at_utc, completed_at_utc,
                    outcome, error_type, snapshot_id, normalized_line_count,
                    playable_game_count, detail_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    provider, failover_rank, started_at_utc, completed, outcome_text,
                    _clean(error_type), _clean(snapshot_id), normalized_line_count,
                    playable_game_count, _json(detail) if detail is not None else None,
                ),
            )
            attempt_id = int(cursor.lastrowid)
    except sqlite3.IntegrityError as exc:
        raise WNBAPropFeedStoreConflictError(f"WNBA Step 5O attempt conflict: {exc}") from exc
    except sqlite3.Error as exc:
        raise WNBAPropFeedStoreError(f"WNBA Step 5O could not append provider attempt: {exc}") from exc
    return {
        "attempt_id": attempt_id,
        "provider_id": provider,
        "failover_rank": failover_rank,
        "outcome": outcome_text,
        "snapshot_id": _clean(snapshot_id),
        "completed_at_utc": completed,
    }


def _snapshot_row(row: sqlite3.Row, *, include_payload: bool) -> dict[str, Any]:
    result = {
        "snapshot_id": row["snapshot_id"],
        "snapshot_fingerprint_sha256": row["snapshot_fingerprint_sha256"],
        "provider_id": row["provider_id"],
        "feed_source": row["feed_source"],
        "feed_format": row["feed_format"],
        "odds_format": row["odds_format"],
        "season": row["season"],
        "date": row["date"],
        "collected_at_utc": row["collected_at_utc"],
        "stored_at_utc": row["stored_at_utc"],
        "collection_id": row["collection_id"],
        "collection_fingerprint_sha256": row["collection_fingerprint_sha256"],
        "source_raw_feed_sha256": row["source_raw_feed_sha256"],
        "normalized_input_feed_sha256": row["normalized_input_feed_sha256"],
    }
    if include_payload:
        result["collection"] = json.loads(row["collection_json"])
        result["normalized_input_feed"] = json.loads(row["normalized_input_feed_json"])
        result["adapter"] = json.loads(row["adapter_json"]) if row["adapter_json"] else None
    return result


def list_feed_snapshots(
    *,
    provider_id: str | None = None,
    date: str | None = None,
    season: int | None = None,
    limit: int = 100,
    include_payload: bool = False,
    path: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_LIST_LIMIT:
        raise ValueError(f"WNBA Step 5O snapshot limit must be 1 through {MAX_LIST_LIMIT}.")
    initialize_store(path, env)
    clauses: list[str] = []
    params: list[Any] = []
    if provider_id:
        clauses.append("provider_id = ?")
        params.append(str(provider_id).strip().casefold())
    if date:
        clauses.append("date = ?")
        params.append(str(date).strip())
    if season is not None:
        clauses.append("season = ?")
        params.append(season)
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    params.append(limit)
    resolved = resolve_store_path(path, env)
    try:
        with _connect(resolved) as connection:
            rows = connection.execute(
                "SELECT * FROM wnba_prop_feed_snapshots"
                + where
                + " ORDER BY collected_at_utc DESC, stored_at_utc DESC LIMIT ?",
                params,
            ).fetchall()
    except sqlite3.Error as exc:
        raise WNBAPropFeedStoreError(f"WNBA Step 5O could not list feed snapshots: {exc}") from exc
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_prop_feed_snapshots",
        "schema_version": STORE_SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _utc_now_iso(),
        "count": len(rows),
        "snapshots": [_snapshot_row(row, include_payload=include_payload) for row in rows],
    }


def _provider_health_from_attempts(provider_id: str, rows: list[sqlite3.Row], now: datetime) -> dict[str, Any]:
    if not rows:
        return {
            "provider_id": provider_id,
            "attempt_count_considered": 0,
            "last_outcome": None,
            "last_attempt_at_utc": None,
            "last_success_at_utc": None,
            "last_snapshot_id": None,
            "last_normalized_line_count": None,
            "consecutive_failures": 0,
            "success_rate": None,
            "seconds_since_last_success": None,
            "healthy": False,
        }
    success_rows = [row for row in rows if row["outcome"] in SUCCESS_OUTCOMES]
    consecutive_failures = 0
    for row in rows:
        if row["outcome"] in SUCCESS_OUTCOMES:
            break
        consecutive_failures += 1
    last_success = success_rows[0] if success_rows else None
    last_success_dt = _parse_timestamp(last_success["completed_at_utc"]) if last_success else None
    seconds_since = max(0.0, (now - last_success_dt).total_seconds()) if last_success_dt else None
    success_rate = round(len(success_rows) / len(rows), 6) if rows else None
    healthy = bool(last_success and consecutive_failures < 3 and seconds_since is not None and seconds_since <= 3600)
    return {
        "provider_id": provider_id,
        "attempt_count_considered": len(rows),
        "last_outcome": rows[0]["outcome"],
        "last_attempt_at_utc": rows[0]["completed_at_utc"],
        "last_success_at_utc": last_success["completed_at_utc"] if last_success else None,
        "last_snapshot_id": last_success["snapshot_id"] if last_success else None,
        "last_normalized_line_count": last_success["normalized_line_count"] if last_success else None,
        "consecutive_failures": consecutive_failures,
        "success_rate": success_rate,
        "seconds_since_last_success": round(seconds_since, 3) if seconds_since is not None else None,
        "healthy": healthy,
    }


def get_provider_health(
    provider_id: str | None = None,
    *,
    attempts_per_provider: int = 20,
    now_utc: datetime | None = None,
    path: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    if not isinstance(attempts_per_provider, int) or isinstance(attempts_per_provider, bool) or not 1 <= attempts_per_provider <= MAX_HEALTH_ATTEMPTS:
        raise ValueError(f"WNBA Step 5O attempts_per_provider must be 1 through {MAX_HEALTH_ATTEMPTS}.")
    current = now_utc or _utc_now()
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("WNBA Step 5O now_utc must be timezone-aware.")
    current = current.astimezone(timezone.utc)
    initialize_store(path, env)
    resolved = resolve_store_path(path, env)
    try:
        with _connect(resolved) as connection:
            if provider_id:
                provider_ids = [str(provider_id).strip().casefold()]
            else:
                provider_ids = [
                    row["provider_id"]
                    for row in connection.execute(
                        "SELECT DISTINCT provider_id FROM wnba_prop_feed_attempts ORDER BY provider_id"
                    ).fetchall()
                ]
            health = []
            for pid in provider_ids:
                rows = connection.execute(
                    """
                    SELECT * FROM wnba_prop_feed_attempts
                    WHERE provider_id = ?
                    ORDER BY completed_at_utc DESC, attempt_id DESC LIMIT ?
                    """,
                    (pid, attempts_per_provider),
                ).fetchall()
                health.append(_provider_health_from_attempts(pid, list(rows), current))
    except sqlite3.Error as exc:
        raise WNBAPropFeedStoreError(f"WNBA Step 5O could not read provider health: {exc}") from exc
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_prop_feed_provider_health",
        "schema_version": STORE_SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _utc_now_iso(),
        "attempts_per_provider": attempts_per_provider,
        "provider_count": len(health),
        "providers": health,
    }


def get_store_status(
    *,
    path: str | Path | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    initialize_store(path, env)
    resolved = resolve_store_path(path, env)
    try:
        with _connect(resolved) as connection:
            snapshot_count = connection.execute("SELECT COUNT(*) AS n FROM wnba_prop_feed_snapshots").fetchone()["n"]
            attempt_count = connection.execute("SELECT COUNT(*) AS n FROM wnba_prop_feed_attempts").fetchone()["n"]
            provider_count = connection.execute("SELECT COUNT(DISTINCT provider_id) AS n FROM wnba_prop_feed_attempts").fetchone()["n"]
            success_count = connection.execute(
                "SELECT COUNT(*) AS n FROM wnba_prop_feed_attempts WHERE outcome IN ('success', 'success_empty_slate')"
            ).fetchone()["n"]
    except sqlite3.Error as exc:
        raise WNBAPropFeedStoreError(f"WNBA Step 5O could not read store status: {exc}") from exc
    explicit_path_configured = bool(_clean((os.environ if env is None else env).get(STORE_PATH_ENV)))
    return {
        "source": MODEL_SOURCE,
        "data_type": "wnba_prop_feed_store_status",
        "schema_version": STORE_SCHEMA_VERSION,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _utc_now_iso(),
        "store_path": str(resolved),
        "explicit_persistent_path_configured": explicit_path_configured,
        "snapshot_count": snapshot_count,
        "attempt_count": attempt_count,
        "provider_count": provider_count,
        "successful_attempt_count": success_count,
        "immutability": {
            "snapshots_update_rejected": True,
            "snapshots_delete_rejected": True,
            "attempts_update_rejected": True,
            "attempts_delete_rejected": True,
        },
    }
