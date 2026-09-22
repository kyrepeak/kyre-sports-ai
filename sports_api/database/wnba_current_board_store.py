"""WNBA Step 5P durable publication and scheduler-run store.

This store is intentionally separate from the frozen Step-5O raw market-feed
store and frozen Step-5J audit archive store.  Step 5P records what board was
published and why/when the scheduler ran.  Publications and run records are
append-only; the current board is derived by selecting the newest unexpired
publication rather than mutating a singleton row.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from typing import Any

MODEL_SOURCE = "Kyre Sports API WNBA Step 5P current board publication store"
MODEL_VERSION = "wnba_step_5p_current_board_store_v1"
STORE_SCHEMA_VERSION = "wnba_step_5p_current_board_sqlite_v1"
STORE_PATH_ENV = "WNBA_CURRENT_BOARD_STORE_PATH"
DEFAULT_STORE_PATH = Path(__file__).resolve().with_name("wnba_current_board_store.sqlite3")
MAX_PUBLICATION_LIMIT = 2_000
MAX_RUN_LIMIT = 5_000


class WNBACurrentBoardStoreError(RuntimeError):
    pass


class WNBACurrentBoardStoreConflictError(WNBACurrentBoardStoreError):
    pass


class WNBACurrentBoardStoreNotReadyError(WNBACurrentBoardStoreError):
    pass


def _environment(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if env is None else env


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None = None) -> str:
    value = value or _now()
    if value.tzinfo is None or value.utcoffset() is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _dt(value: Any, label: str) -> datetime:
    text = str(value or "").strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        result = datetime.fromisoformat(text)
    except ValueError as exc:
        raise WNBACurrentBoardStoreError(
            f"WNBA Step 5P {label} must be timezone-aware ISO-8601."
        ) from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise WNBACurrentBoardStoreError(
            f"WNBA Step 5P {label} must include a timezone offset or Z."
        )
    return result.astimezone(timezone.utc)


def _json(value: Any) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def _hash(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def _sha(value: Any) -> bool:
    text = str(value or "").strip()
    return bool(
        len(text) == 64
        and all(char in "0123456789abcdefABCDEF" for char in text)
    )


def resolve_store_path(
    path: str | os.PathLike[str] | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> Path:
    environment = _environment(env)
    raw = path if path is not None else environment.get(STORE_PATH_ENV)
    resolved = Path(raw).expanduser() if raw else DEFAULT_STORE_PATH
    if resolved.exists() and resolved.is_dir():
        raise WNBACurrentBoardStoreError(
            f"{STORE_PATH_ENV} must point to a SQLite file, not a directory."
        )
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved


def _connect(
    path: str | os.PathLike[str] | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> sqlite3.Connection:
    conn = sqlite3.connect(
        str(resolve_store_path(path, env=env)),
        timeout=30.0,
        isolation_level=None,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    try:
        conn.execute("PRAGMA journal_mode = WAL")
    except sqlite3.DatabaseError:
        pass
    return conn


_SCHEMA = """
CREATE TABLE IF NOT EXISTS wnba_current_board_metadata (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS wnba_board_publications (
  publication_id TEXT PRIMARY KEY,
  content_sha256 TEXT NOT NULL UNIQUE,
  logical_publication_key TEXT NOT NULL UNIQUE,
  publication_json TEXT NOT NULL,
  stored_at_utc TEXT NOT NULL,
  published_at_utc TEXT NOT NULL,
  valid_until_utc TEXT NOT NULL,
  date TEXT NOT NULL,
  season INTEGER NOT NULL,
  season_type TEXT,
  serving_state TEXT NOT NULL,
  selected_provider_id TEXT,
  source_feed_fingerprint_sha256 TEXT,
  step_5l_daily_board_fingerprint_sha256 TEXT,
  probability_board_count INTEGER NOT NULL,
  value_board_count INTEGER NOT NULL,
  archived_prediction_count INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_wnba_board_publications_current
  ON wnba_board_publications(date, season, published_at_utc DESC);
CREATE INDEX IF NOT EXISTS idx_wnba_board_publications_validity
  ON wnba_board_publications(valid_until_utc);

CREATE TABLE IF NOT EXISTS wnba_board_scheduler_runs (
  run_id TEXT PRIMARY KEY,
  run_json TEXT NOT NULL,
  stored_at_utc TEXT NOT NULL,
  started_at_utc TEXT NOT NULL,
  completed_at_utc TEXT NOT NULL,
  date TEXT NOT NULL,
  season INTEGER NOT NULL,
  outcome TEXT NOT NULL,
  provider_collection_attempted INTEGER NOT NULL CHECK(provider_collection_attempted IN (0,1)),
  board_rebuild_attempted INTEGER NOT NULL CHECK(board_rebuild_attempted IN (0,1)),
  publication_id TEXT,
  selected_provider_id TEXT,
  source_feed_fingerprint_sha256 TEXT,
  next_due_at_utc TEXT,
  FOREIGN KEY(publication_id) REFERENCES wnba_board_publications(publication_id)
);
CREATE INDEX IF NOT EXISTS idx_wnba_board_scheduler_runs_latest
  ON wnba_board_scheduler_runs(date, season, completed_at_utc DESC);

CREATE TRIGGER IF NOT EXISTS wnba_board_publications_no_update
BEFORE UPDATE ON wnba_board_publications
BEGIN SELECT RAISE(ABORT,'wnba_board_publications is immutable'); END;
CREATE TRIGGER IF NOT EXISTS wnba_board_publications_no_delete
BEFORE DELETE ON wnba_board_publications
BEGIN SELECT RAISE(ABORT,'wnba_board_publications is immutable'); END;
CREATE TRIGGER IF NOT EXISTS wnba_board_scheduler_runs_no_update
BEFORE UPDATE ON wnba_board_scheduler_runs
BEGIN SELECT RAISE(ABORT,'wnba_board_scheduler_runs is append-only'); END;
CREATE TRIGGER IF NOT EXISTS wnba_board_scheduler_runs_no_delete
BEFORE DELETE ON wnba_board_scheduler_runs
BEGIN SELECT RAISE(ABORT,'wnba_board_scheduler_runs is append-only'); END;
"""


def initialize_store(
    path: str | os.PathLike[str] | None = None,
    *,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    resolved = resolve_store_path(path, env=env)
    conn = _connect(resolved, env=env)
    try:
        conn.executescript(_SCHEMA)
        conn.execute(
            "INSERT OR IGNORE INTO wnba_current_board_metadata(key,value) VALUES('schema_version',?)",
            (STORE_SCHEMA_VERSION,),
        )
        row = conn.execute(
            "SELECT value FROM wnba_current_board_metadata WHERE key='schema_version'"
        ).fetchone()
        if row is None or row["value"] != STORE_SCHEMA_VERSION:
            raise WNBACurrentBoardStoreError(
                "Unexpected WNBA Step 5P current-board store schema version."
            )
    finally:
        conn.close()
    environment = _environment(env)
    return {
        "source": MODEL_SOURCE,
        "model_version": MODEL_VERSION,
        "schema_version": STORE_SCHEMA_VERSION,
        "store_path": str(resolved),
        "persistent_path_explicitly_configured": (
            path is not None or bool(environment.get(STORE_PATH_ENV))
        ),
    }


def _publication_row(publication: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(publication, dict):
        raise WNBACurrentBoardStoreError("WNBA Step 5P publication must be an object.")
    content = publication.get("content")
    digest = publication.get("content_sha256")
    publication_id = str(publication.get("publication_id") or "").strip()
    if not isinstance(content, dict) or not publication_id:
        raise WNBACurrentBoardStoreError(
            "WNBA Step 5P publication content/id is missing."
        )
    if not _sha(digest) or _hash(content) != digest:
        raise WNBACurrentBoardStoreError(
            "WNBA Step 5P publication content hash mismatch."
        )
    published = _dt(content.get("published_at_utc"), "publication timestamp")
    valid_until = _dt(content.get("valid_until_utc"), "publication valid-until timestamp")
    if valid_until <= published:
        raise WNBACurrentBoardStoreError(
            "WNBA Step 5P publication valid_until_utc must be after published_at_utc."
        )
    board = content.get("board")
    source = content.get("source_reference")
    archive_summary = content.get("archive_summary")
    if not isinstance(board, dict) or not isinstance(source, dict) or not isinstance(archive_summary, dict):
        raise WNBACurrentBoardStoreError(
            "WNBA Step 5P publication board/source/archive summary is malformed."
        )
    try:
        date = str(content["date"])
        season = int(content["season"])
        serving_state = str(content["serving_state"])
        probability_count = int(board.get("probability_board_count") or 0)
        value_count = int(board.get("value_board_count") or 0)
        archive_count = int(archive_summary.get("stored_or_existing_count") or 0)
    except (KeyError, TypeError, ValueError) as exc:
        raise WNBACurrentBoardStoreError(
            "WNBA Step 5P publication identity/count fields are malformed."
        ) from exc
    if season <= 0 or probability_count < 0 or value_count < 0 or archive_count < 0:
        raise WNBACurrentBoardStoreError(
            "WNBA Step 5P publication contains invalid season/count fields."
        )
    source_feed_fingerprint = source.get("line_board_fingerprint_sha256")
    daily_fingerprint = board.get("daily_board_fingerprint_sha256")
    if source_feed_fingerprint is not None and not _sha(source_feed_fingerprint):
        raise WNBACurrentBoardStoreError(
            "WNBA Step 5P source line-board fingerprint is invalid."
        )
    if daily_fingerprint is not None and not _sha(daily_fingerprint):
        raise WNBACurrentBoardStoreError(
            "WNBA Step 5P Step-5L daily-board fingerprint is invalid."
        )
    logical = _hash(
        {
            "date": date,
            "season": season,
            "serving_state": serving_state,
            "source_feed_fingerprint_sha256": source_feed_fingerprint,
            "step_5l_daily_board_fingerprint_sha256": daily_fingerprint,
        }
    )
    return {
        "publication_id": publication_id,
        "content_sha256": str(digest),
        "logical_publication_key": logical,
        "publication_json": _json(publication),
        "published_at_utc": published.isoformat(),
        "valid_until_utc": valid_until.isoformat(),
        "date": date,
        "season": season,
        "season_type": content.get("season_type"),
        "serving_state": serving_state,
        "selected_provider_id": source.get("selected_provider_id"),
        "source_feed_fingerprint_sha256": source_feed_fingerprint,
        "step_5l_daily_board_fingerprint_sha256": daily_fingerprint,
        "probability_board_count": probability_count,
        "value_board_count": value_count,
        "archived_prediction_count": archive_count,
    }


def persist_publication(
    publication: dict[str, Any],
    *,
    path: str | os.PathLike[str] | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    initialize_store(path, env=env)
    row = _publication_row(publication)
    conn = _connect(path, env=env)
    try:
        conn.execute("BEGIN IMMEDIATE")
        existing_id = conn.execute(
            "SELECT publication_id,content_sha256,publication_json FROM wnba_board_publications WHERE publication_id=?",
            (row["publication_id"],),
        ).fetchone()
        if existing_id is not None:
            if (
                existing_id["content_sha256"] != row["content_sha256"]
                or existing_id["publication_json"] != row["publication_json"]
            ):
                raise WNBACurrentBoardStoreConflictError(
                    "Immutable Step 5P publication_id already exists with different content."
                )
            conn.execute("COMMIT")
            return {
                "stored": False,
                "idempotent_replay": True,
                "logical_idempotent_replay": False,
                "publication_id": existing_id["publication_id"],
                "content_sha256": existing_id["content_sha256"],
            }
        logical = conn.execute(
            "SELECT publication_id,content_sha256 FROM wnba_board_publications WHERE logical_publication_key=?",
            (row["logical_publication_key"],),
        ).fetchone()
        if logical is not None:
            conn.execute("COMMIT")
            return {
                "stored": False,
                "idempotent_replay": True,
                "logical_idempotent_replay": True,
                "publication_id": logical["publication_id"],
                "content_sha256": logical["content_sha256"],
            }
        collision = conn.execute(
            "SELECT publication_id FROM wnba_board_publications WHERE content_sha256=?",
            (row["content_sha256"],),
        ).fetchone()
        if collision is not None:
            raise WNBACurrentBoardStoreConflictError(
                "Step 5P publication content hash exists under another publication_id."
            )
        conn.execute(
            """INSERT INTO wnba_board_publications(
            publication_id,content_sha256,logical_publication_key,publication_json,stored_at_utc,
            published_at_utc,valid_until_utc,date,season,season_type,serving_state,
            selected_provider_id,source_feed_fingerprint_sha256,
            step_5l_daily_board_fingerprint_sha256,probability_board_count,
            value_board_count,archived_prediction_count)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                row["publication_id"], row["content_sha256"], row["logical_publication_key"],
                row["publication_json"], _iso(), row["published_at_utc"], row["valid_until_utc"],
                row["date"], row["season"], row["season_type"], row["serving_state"],
                row["selected_provider_id"], row["source_feed_fingerprint_sha256"],
                row["step_5l_daily_board_fingerprint_sha256"], row["probability_board_count"],
                row["value_board_count"], row["archived_prediction_count"],
            ),
        )
        conn.execute("COMMIT")
    except Exception:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
    return {
        "stored": True,
        "idempotent_replay": False,
        "logical_idempotent_replay": False,
        "publication_id": row["publication_id"],
        "content_sha256": row["content_sha256"],
    }


def _publication_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return json.loads(row["publication_json"])


def get_latest_publication(
    *,
    date: str | None = None,
    season: int | None = None,
    now_utc: datetime | None = None,
    require_current: bool = False,
    path: str | os.PathLike[str] | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any] | None:
    initialize_store(path, env=env)
    clauses: list[str] = []
    params: list[Any] = []
    if date is not None:
        clauses.append("date=?")
        params.append(str(date))
    if season is not None:
        clauses.append("season=?")
        params.append(int(season))
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    conn = _connect(path, env=env)
    try:
        row = conn.execute(
            "SELECT publication_json,valid_until_utc FROM wnba_board_publications"
            + where
            + " ORDER BY published_at_utc DESC,publication_id DESC LIMIT 1",
            tuple(params),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return None
    publication = _publication_from_row(row)
    now = now_utc or _now()
    if now.tzinfo is None or now.utcoffset() is None:
        now = now.replace(tzinfo=timezone.utc)
    else:
        now = now.astimezone(timezone.utc)
    valid_until = _dt(row["valid_until_utc"], "stored valid-until timestamp")
    is_current = now < valid_until
    publication["serving"] = {
        "is_current": is_current,
        "evaluated_at_utc": now.isoformat(),
        "seconds_until_expiry": max(0.0, round((valid_until - now).total_seconds(), 3)),
    }
    if require_current and not is_current:
        raise WNBACurrentBoardStoreNotReadyError(
            "WNBA Step 5P latest published board is expired."
        )
    return publication


def list_publications(
    *,
    date: str | None = None,
    season: int | None = None,
    limit: int = 100,
    path: str | os.PathLike[str] | None = None,
    env: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_PUBLICATION_LIMIT:
        raise ValueError(
            f"WNBA Step 5P publication limit must be 1 through {MAX_PUBLICATION_LIMIT}."
        )
    initialize_store(path, env=env)
    clauses: list[str] = []
    params: list[Any] = []
    if date is not None:
        clauses.append("date=?")
        params.append(str(date))
    if season is not None:
        clauses.append("season=?")
        params.append(int(season))
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    params.append(limit)
    conn = _connect(path, env=env)
    try:
        rows = conn.execute(
            "SELECT publication_json FROM wnba_board_publications"
            + where
            + " ORDER BY published_at_utc DESC,publication_id DESC LIMIT ?",
            tuple(params),
        ).fetchall()
    finally:
        conn.close()
    return [json.loads(row["publication_json"]) for row in rows]


def append_scheduler_run(
    run: dict[str, Any],
    *,
    path: str | os.PathLike[str] | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    if not isinstance(run, dict):
        raise WNBACurrentBoardStoreError("WNBA Step 5P scheduler run must be an object.")
    try:
        run_id = str(run["run_id"])
        started = _dt(run["started_at_utc"], "scheduler started_at_utc")
        completed = _dt(run["completed_at_utc"], "scheduler completed_at_utc")
        date = str(run["date"])
        season = int(run["season"])
        outcome = str(run["outcome"])
        provider_attempted = bool(run["provider_collection_attempted"])
        rebuild_attempted = bool(run["board_rebuild_attempted"])
    except (KeyError, TypeError, ValueError) as exc:
        raise WNBACurrentBoardStoreError(
            "WNBA Step 5P scheduler run identity is malformed."
        ) from exc
    if not run_id or completed < started or season <= 0 or not outcome:
        raise WNBACurrentBoardStoreError(
            "WNBA Step 5P scheduler run contains invalid timing/identity fields."
        )
    next_due = run.get("next_due_at_utc")
    if next_due is not None:
        next_due = _dt(next_due, "scheduler next_due_at_utc").isoformat()
    initialize_store(path, env=env)
    conn = _connect(path, env=env)
    try:
        conn.execute(
            """INSERT INTO wnba_board_scheduler_runs(
            run_id,run_json,stored_at_utc,started_at_utc,completed_at_utc,date,season,outcome,
            provider_collection_attempted,board_rebuild_attempted,publication_id,
            selected_provider_id,source_feed_fingerprint_sha256,next_due_at_utc)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                run_id, _json(run), _iso(), started.isoformat(), completed.isoformat(), date, season,
                outcome, 1 if provider_attempted else 0, 1 if rebuild_attempted else 0,
                run.get("publication_id"), run.get("selected_provider_id"),
                run.get("source_feed_fingerprint_sha256"), next_due,
            ),
        )
    except sqlite3.IntegrityError as exc:
        raise WNBACurrentBoardStoreConflictError(
            "WNBA Step 5P scheduler run_id already exists or references an invalid publication."
        ) from exc
    finally:
        conn.close()
    return {"stored": True, "run_id": run_id}


def get_latest_scheduler_run(
    *,
    date: str | None = None,
    season: int | None = None,
    path: str | os.PathLike[str] | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any] | None:
    initialize_store(path, env=env)
    clauses: list[str] = []
    params: list[Any] = []
    if date is not None:
        clauses.append("date=?")
        params.append(str(date))
    if season is not None:
        clauses.append("season=?")
        params.append(int(season))
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    conn = _connect(path, env=env)
    try:
        row = conn.execute(
            "SELECT run_json FROM wnba_board_scheduler_runs"
            + where
            + " ORDER BY completed_at_utc DESC,run_id DESC LIMIT 1",
            tuple(params),
        ).fetchone()
    finally:
        conn.close()
    return json.loads(row["run_json"]) if row is not None else None


def list_scheduler_runs(
    *,
    date: str | None = None,
    season: int | None = None,
    limit: int = 100,
    path: str | os.PathLike[str] | None = None,
    env: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_RUN_LIMIT:
        raise ValueError(f"WNBA Step 5P scheduler run limit must be 1 through {MAX_RUN_LIMIT}.")
    initialize_store(path, env=env)
    clauses: list[str] = []
    params: list[Any] = []
    if date is not None:
        clauses.append("date=?")
        params.append(str(date))
    if season is not None:
        clauses.append("season=?")
        params.append(int(season))
    where = " WHERE " + " AND ".join(clauses) if clauses else ""
    params.append(limit)
    conn = _connect(path, env=env)
    try:
        rows = conn.execute(
            "SELECT run_json FROM wnba_board_scheduler_runs"
            + where
            + " ORDER BY completed_at_utc DESC,run_id DESC LIMIT ?",
            tuple(params),
        ).fetchall()
    finally:
        conn.close()
    return [json.loads(row["run_json"]) for row in rows]


def get_store_status(
    *,
    path: str | os.PathLike[str] | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    metadata = initialize_store(path, env=env)
    conn = _connect(path, env=env)
    try:
        publication_count = int(
            conn.execute("SELECT COUNT(*) AS n FROM wnba_board_publications").fetchone()["n"]
        )
        run_count = int(
            conn.execute("SELECT COUNT(*) AS n FROM wnba_board_scheduler_runs").fetchone()["n"]
        )
        latest_publication = conn.execute(
            "SELECT publication_id,published_at_utc,valid_until_utc,date,season,serving_state,selected_provider_id,probability_board_count,value_board_count,archived_prediction_count FROM wnba_board_publications ORDER BY published_at_utc DESC,publication_id DESC LIMIT 1"
        ).fetchone()
        latest_run = conn.execute(
            "SELECT run_id,completed_at_utc,date,season,outcome,next_due_at_utc FROM wnba_board_scheduler_runs ORDER BY completed_at_utc DESC,run_id DESC LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    return {
        **metadata,
        "publication_count": publication_count,
        "scheduler_run_count": run_count,
        "latest_publication": dict(latest_publication) if latest_publication is not None else None,
        "latest_scheduler_run": dict(latest_run) if latest_run is not None else None,
        "append_only_publications": True,
        "append_only_scheduler_runs": True,
    }
