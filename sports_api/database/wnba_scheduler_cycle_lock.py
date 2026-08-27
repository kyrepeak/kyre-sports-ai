"""WNBA Step 5Q cross-process scheduler-cycle mutex.

Step 5P already prevents overlapping work inside one Python process. Step 5Q
adds the production guard needed when FastAPI runs with multiple worker
processes. The mutex lives in a dedicated SQLite file beside the persistent
Step-5P board store and is held by an open ``BEGIN IMMEDIATE`` transaction for
the entire scheduler cycle.

Because the live lock is the SQLite transaction itself, a crashed process does
not leave a stale TTL lease behind: closing the process closes the connection
and the operating system releases the lock automatically.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sqlite3
import threading
from typing import Any
from uuid import uuid4

from sports_api.database.wnba_current_board_store import (
    resolve_store_path as resolve_board_store_path,
)

MODEL_SOURCE = "Kyre Sports API WNBA Step 5Q cross-process scheduler lock"
MODEL_VERSION = "wnba_step_5q_cross_process_scheduler_lock_v1"
STORE_SCHEMA_VERSION = "wnba_step_5q_scheduler_lock_sqlite_v1"
LOCK_PATH_ENV = "WNBA_BOARD_SCHEDULER_LOCK_PATH"
LOCK_NAME = "wnba-pregame-player-prop-board-cycle"
DEFAULT_ACQUIRE_TIMEOUT_SECONDS = 0.05
MAX_ACQUIRE_TIMEOUT_SECONDS = 5.0
MAX_HISTORY_LIMIT = 2_000


class WNBASchedulerCycleLockError(RuntimeError):
    pass


class WNBASchedulerCycleLockConfigurationError(WNBASchedulerCycleLockError):
    pass


class WNBASchedulerCycleLockHandle:
    def __init__(
        self,
        *,
        connection: sqlite3.Connection,
        owner_id: str,
        acquired_at_utc: datetime,
        lock_path: Path,
    ) -> None:
        self.connection = connection
        self.owner_id = owner_id
        self.acquired_at_utc = acquired_at_utc
        self.lock_path = lock_path
        self.released = False


_initialized_paths: set[str] = set()
_initialized_paths_lock = threading.Lock()


def _environment(env: Mapping[str, str] | None) -> Mapping[str, str]:
    return os.environ if env is None else env


def _aware(value: datetime | None = None) -> datetime:
    result = value or datetime.now(timezone.utc)
    if result.tzinfo is None or result.utcoffset() is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


def _iso(value: datetime | None = None) -> str:
    return _aware(value).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _is_locked(exc: BaseException) -> bool:
    text = str(exc).casefold()
    return "locked" in text or "busy" in text


def _owner(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        raise WNBASchedulerCycleLockConfigurationError(
            "WNBA Step 5Q scheduler lock owner_id must not be empty."
        )
    if len(text) > 240:
        raise WNBASchedulerCycleLockConfigurationError(
            "WNBA Step 5Q scheduler lock owner_id must be 240 characters or fewer."
        )
    return text


def _timeout(value: Any) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise WNBASchedulerCycleLockConfigurationError(
            "WNBA Step 5Q lock timeout must be numeric."
        ) from exc
    if result < 0:
        raise WNBASchedulerCycleLockConfigurationError(
            "WNBA Step 5Q lock timeout cannot be negative."
        )
    return min(result, MAX_ACQUIRE_TIMEOUT_SECONDS)


def resolve_lock_path(
    path: str | os.PathLike[str] | None = None,
    *,
    board_store_path: str | os.PathLike[str] | None = None,
    env: Mapping[str, str] | None = None,
) -> Path:
    environment = _environment(env)
    board_path = resolve_board_store_path(board_store_path, env=environment)
    raw = path if path is not None else environment.get(LOCK_PATH_ENV)
    if raw:
        resolved = Path(raw).expanduser()
    else:
        suffix = board_path.suffix or ".sqlite3"
        resolved = board_path.with_name(f"{board_path.stem}.scheduler_lock{suffix}")
    if resolved.exists() and resolved.is_dir():
        raise WNBASchedulerCycleLockConfigurationError(
            f"{LOCK_PATH_ENV} must point to a SQLite file, not a directory."
        )
    try:
        same = resolved.resolve() == board_path.resolve()
    except OSError:
        same = os.path.abspath(str(resolved)) == os.path.abspath(str(board_path))
    if same:
        raise WNBASchedulerCycleLockConfigurationError(
            "WNBA Step 5Q lock database must be separate from the Step-5P current-board database."
        )
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved


def _connect(path: Path, timeout_seconds: float) -> sqlite3.Connection:
    conn = sqlite3.connect(str(path), timeout=timeout_seconds, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute(f"PRAGMA busy_timeout = {max(0, int(timeout_seconds * 1000))}")
    return conn


_SCHEMA = """
CREATE TABLE IF NOT EXISTS wnba_scheduler_lock_metadata (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS wnba_scheduler_lock_history (
  event_id TEXT PRIMARY KEY,
  owner_id TEXT NOT NULL,
  acquired_at_utc TEXT NOT NULL,
  released_at_utc TEXT NOT NULL,
  outcome TEXT NOT NULL,
  detail_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_wnba_scheduler_lock_history_released
  ON wnba_scheduler_lock_history(released_at_utc DESC);
CREATE TRIGGER IF NOT EXISTS wnba_scheduler_lock_history_no_update
BEFORE UPDATE ON wnba_scheduler_lock_history
BEGIN SELECT RAISE(ABORT,'wnba_scheduler_lock_history is append-only'); END;
CREATE TRIGGER IF NOT EXISTS wnba_scheduler_lock_history_no_delete
BEFORE DELETE ON wnba_scheduler_lock_history
BEGIN SELECT RAISE(ABORT,'wnba_scheduler_lock_history is append-only'); END;
"""


def _schema_ready(resolved: Path) -> bool:
    if not resolved.exists():
        return False
    conn = _connect(resolved, 0.0)
    try:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='wnba_scheduler_lock_metadata'"
        ).fetchone()
        if row is None:
            return False
        version = conn.execute(
            "SELECT value FROM wnba_scheduler_lock_metadata WHERE key='schema_version'"
        ).fetchone()
        return version is not None and version["value"] == STORE_SCHEMA_VERSION
    except sqlite3.DatabaseError:
        return False
    finally:
        conn.close()


def initialize_lock_store(
    path: str | os.PathLike[str] | None = None,
    *,
    board_store_path: str | os.PathLike[str] | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    resolved = resolve_lock_path(path, board_store_path=board_store_path, env=env)
    cache_key = str(resolved.absolute())
    with _initialized_paths_lock:
        cached = cache_key in _initialized_paths
    if not cached and not _schema_ready(resolved):
        conn = _connect(resolved, 5.0)
        try:
            try:
                conn.execute("PRAGMA journal_mode = WAL")
            except sqlite3.DatabaseError:
                pass
            conn.executescript(_SCHEMA)
            conn.execute(
                "INSERT OR IGNORE INTO wnba_scheduler_lock_metadata(key,value) VALUES('schema_version',?)",
                (STORE_SCHEMA_VERSION,),
            )
            version = conn.execute(
                "SELECT value FROM wnba_scheduler_lock_metadata WHERE key='schema_version'"
            ).fetchone()
            if version is None or version["value"] != STORE_SCHEMA_VERSION:
                raise WNBASchedulerCycleLockError(
                    "Unexpected WNBA Step 5Q scheduler-lock schema version."
                )
        except sqlite3.DatabaseError as exc:
            raise WNBASchedulerCycleLockError(
                f"WNBA Step 5Q could not initialize scheduler-lock store: {exc}"
            ) from exc
        finally:
            conn.close()
    with _initialized_paths_lock:
        _initialized_paths.add(cache_key)
    return {
        "source": MODEL_SOURCE,
        "model_version": MODEL_VERSION,
        "schema_version": STORE_SCHEMA_VERSION,
        "lock_name": LOCK_NAME,
        "lock_path": str(resolved),
        "board_store_path": str(resolve_board_store_path(board_store_path, env=env)),
        "separate_from_board_store": True,
        "crash_releases_os_lock_automatically": True,
    }


def try_acquire_cycle_lock(
    owner_id: str,
    *,
    path: str | os.PathLike[str] | None = None,
    board_store_path: str | os.PathLike[str] | None = None,
    env: Mapping[str, str] | None = None,
    timeout_seconds: float = DEFAULT_ACQUIRE_TIMEOUT_SECONDS,
    now_utc: datetime | None = None,
) -> WNBASchedulerCycleLockHandle | None:
    owner = _owner(owner_id)
    timeout = _timeout(timeout_seconds)
    resolved = resolve_lock_path(path, board_store_path=board_store_path, env=env)
    try:
        initialize_lock_store(resolved, board_store_path=board_store_path, env=env)
    except WNBASchedulerCycleLockError as exc:
        if _is_locked(exc):
            return None
        raise
    conn = _connect(resolved, timeout)
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute(
            "UPDATE wnba_scheduler_lock_metadata SET value=value WHERE key='schema_version'"
        )
    except sqlite3.OperationalError as exc:
        conn.close()
        if _is_locked(exc):
            return None
        raise WNBASchedulerCycleLockError(
            f"WNBA Step 5Q could not acquire scheduler lock: {exc}"
        ) from exc
    except Exception:
        conn.close()
        raise
    return WNBASchedulerCycleLockHandle(
        connection=conn,
        owner_id=owner,
        acquired_at_utc=_aware(now_utc),
        lock_path=resolved,
    )


def release_cycle_lock(
    handle: WNBASchedulerCycleLockHandle,
    *,
    outcome: str = "completed",
    detail: Mapping[str, Any] | None = None,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    if not isinstance(handle, WNBASchedulerCycleLockHandle):
        raise WNBASchedulerCycleLockError("WNBA Step 5Q release requires a valid lock handle.")
    if handle.released:
        raise WNBASchedulerCycleLockError("WNBA Step 5Q lock handle has already been released.")
    released = _aware(now_utc)
    event_id = f"wnba-5q-lock-{uuid4().hex}"
    outcome_text = str(outcome or "completed").strip() or "completed"
    try:
        handle.connection.execute(
            "INSERT INTO wnba_scheduler_lock_history(event_id,owner_id,acquired_at_utc,released_at_utc,outcome,detail_json) VALUES(?,?,?,?,?,?)",
            (
                event_id,
                handle.owner_id,
                _iso(handle.acquired_at_utc),
                _iso(released),
                outcome_text,
                _json(dict(detail or {})),
            ),
        )
        handle.connection.execute("COMMIT")
    except Exception as exc:
        if handle.connection.in_transaction:
            try:
                handle.connection.execute("ROLLBACK")
            except Exception:
                pass
        raise WNBASchedulerCycleLockError(
            f"WNBA Step 5Q could not release scheduler lock cleanly: {exc}"
        ) from exc
    finally:
        handle.connection.close()
        handle.released = True
    return {
        "released": True,
        "event_id": event_id,
        "owner_id": handle.owner_id,
        "lock_path": str(handle.lock_path),
        "acquired_at_utc": _iso(handle.acquired_at_utc),
        "released_at_utc": _iso(released),
        "outcome": outcome_text,
    }


def probe_cycle_lock_available(
    *,
    path: str | os.PathLike[str] | None = None,
    board_store_path: str | os.PathLike[str] | None = None,
    env: Mapping[str, str] | None = None,
) -> bool:
    resolved = resolve_lock_path(path, board_store_path=board_store_path, env=env)
    try:
        initialize_lock_store(resolved, board_store_path=board_store_path, env=env)
    except WNBASchedulerCycleLockError as exc:
        if _is_locked(exc):
            return False
        raise
    conn = _connect(resolved, 0.0)
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("ROLLBACK")
        return True
    except sqlite3.OperationalError as exc:
        if conn.in_transaction:
            try:
                conn.execute("ROLLBACK")
            except Exception:
                pass
        if _is_locked(exc):
            return False
        raise WNBASchedulerCycleLockError(
            f"WNBA Step 5Q could not probe scheduler lock: {exc}"
        ) from exc
    finally:
        conn.close()


def list_lock_history(
    *,
    limit: int = 50,
    path: str | os.PathLike[str] | None = None,
    board_store_path: str | os.PathLike[str] | None = None,
    env: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_HISTORY_LIMIT:
        raise ValueError(f"WNBA Step 5Q lock history limit must be 1..{MAX_HISTORY_LIMIT}.")
    resolved = resolve_lock_path(path, board_store_path=board_store_path, env=env)
    initialize_lock_store(resolved, board_store_path=board_store_path, env=env)
    conn = _connect(resolved, 5.0)
    try:
        rows = conn.execute(
            "SELECT event_id,owner_id,acquired_at_utc,released_at_utc,outcome,detail_json FROM wnba_scheduler_lock_history ORDER BY released_at_utc DESC,event_id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    finally:
        conn.close()
    return [
        {
            "event_id": row["event_id"],
            "owner_id": row["owner_id"],
            "acquired_at_utc": row["acquired_at_utc"],
            "released_at_utc": row["released_at_utc"],
            "outcome": row["outcome"],
            "detail": json.loads(row["detail_json"]),
        }
        for row in rows
    ]


def get_cycle_lock_status(
    *,
    path: str | os.PathLike[str] | None = None,
    board_store_path: str | os.PathLike[str] | None = None,
    env: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    initialized = initialize_lock_store(path, board_store_path=board_store_path, env=env)
    history = list_lock_history(
        limit=1,
        path=path,
        board_store_path=board_store_path,
        env=env,
    )
    return {
        **initialized,
        "generated_at_utc": _iso(),
        "available_now": probe_cycle_lock_available(
            path=path,
            board_store_path=board_store_path,
            env=env,
        ),
        "last_completed_lock_event": history[0] if history else None,
        "semantics": {
            "single_cycle_across_worker_processes": True,
            "lock_is_os_backed_by_sqlite_transaction": True,
            "lock_is_not_a_ttl_lease": True,
            "process_crash_does_not_leave_stale_lock": True,
            "step_5p_board_database_remains_writable_while_lock_is_held": True,
        },
    }
