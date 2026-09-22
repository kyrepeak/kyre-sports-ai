"""WNBA Step 5J: durable pregame prediction archive and automated grading store.

Step 5J builds on the frozen Step-5I signed archive/grade format. It never
retroactively creates audit-grade history. Only verifiably HMAC-signed pregame
archives may enter the durable store, and archives/graded observations are
append-only once written.

Production should set WNBA_BACKTEST_STORE_PATH to a SQLite file on a persistent
volume. SQLite is intentionally used for the first durable backend because the
repository's database package did not yet contain a storage implementation.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from typing import Any, Callable

from sports_api.wnba_historical_backtest_calibration import (
    WNBAHistoricalBacktestModelInputError,
    WNBAHistoricalBacktestNotFoundError,
    WNBAHistoricalBacktestNotReadyError,
    WNBAHistoricalBacktestUpstreamError,
    _verify_archive_envelope,
    build_pregame_archive_envelope,
    evaluate_backtest_observations,
    get_graded_archived_prediction,
)

MODEL_SOURCE = "Kyre Sports API WNBA Step 5J durable pregame archive and grading store"
MODEL_VERSION = "wnba_step_5j_durable_archive_store_v1"
STORE_SCHEMA_VERSION = "wnba_step_5j_sqlite_store_v1"
STORE_PATH_ENV = "WNBA_BACKTEST_STORE_PATH"
DEFAULT_STORE_PATH = Path(__file__).resolve().with_name("wnba_backtest_store.sqlite3")
MAX_SWEEP_LIMIT = 500
MAX_OBSERVATION_LIMIT = 10_000


class WNBAPregameStoreError(RuntimeError):
    pass


class WNBAPregameStoreConflictError(WNBAPregameStoreError):
    pass


class WNBAPregameStoreNotReadyError(WNBAPregameStoreError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None = None) -> str:
    value = value or _now()
    if value.tzinfo is None or value.utcoffset() is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _dt(value: Any, label: str) -> datetime:
    if value is None:
        raise WNBAPregameStoreError(f"{label} is missing.")
    text = str(value).strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        out = datetime.fromisoformat(text)
    except ValueError as exc:
        raise WNBAPregameStoreError(f"{label} must be timezone-aware ISO-8601.") from exc
    if out.tzinfo is None or out.utcoffset() is None:
        raise WNBAPregameStoreError(f"{label} must include a timezone offset or Z.")
    return out.astimezone(timezone.utc)


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def _hash(value: Any) -> str:
    return hashlib.sha256(_json(value).encode("utf-8")).hexdigest()


def resolve_store_path(db_path: str | os.PathLike[str] | None = None) -> Path:
    raw = db_path if db_path is not None else os.environ.get(STORE_PATH_ENV)
    path = Path(raw).expanduser() if raw else DEFAULT_STORE_PATH
    if path.exists() and path.is_dir():
        raise WNBAPregameStoreError(f"{STORE_PATH_ENV} must point to a SQLite file, not a directory.")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _connect(db_path: str | os.PathLike[str] | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(str(resolve_store_path(db_path)), timeout=30.0, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    try:
        conn.execute("PRAGMA journal_mode = WAL")
    except sqlite3.DatabaseError:
        pass
    return conn


_SCHEMA = """
CREATE TABLE IF NOT EXISTS wnba_store_metadata (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS wnba_pregame_archives (
  archive_id TEXT PRIMARY KEY,
  content_sha256 TEXT NOT NULL UNIQUE,
  logical_prediction_key TEXT NOT NULL UNIQUE,
  archive_json TEXT NOT NULL,
  stored_at_utc TEXT NOT NULL,
  official_game_tip_utc TEXT NOT NULL,
  archived_at_utc TEXT NOT NULL,
  season INTEGER,
  season_type TEXT,
  game_id TEXT NOT NULL,
  player_id INTEGER NOT NULL,
  team_key TEXT NOT NULL,
  opponent_team_key TEXT NOT NULL,
  stat TEXT NOT NULL,
  line REAL NOT NULL,
  probability_model_version TEXT,
  probability_fingerprint_sha256 TEXT,
  snapshot_content_sha256 TEXT,
  signature_value TEXT NOT NULL,
  signature_verified INTEGER NOT NULL CHECK(signature_verified IN (0,1))
);
CREATE INDEX IF NOT EXISTS idx_wnba_archives_game_player ON wnba_pregame_archives(game_id,player_id);
CREATE INDEX IF NOT EXISTS idx_wnba_archives_due ON wnba_pregame_archives(official_game_tip_utc);

CREATE TABLE IF NOT EXISTS wnba_backtest_observations (
  observation_id TEXT PRIMARY KEY,
  observation_content_sha256 TEXT NOT NULL UNIQUE,
  observation_json TEXT NOT NULL,
  archive_id TEXT NOT NULL UNIQUE,
  stored_at_utc TEXT NOT NULL,
  generated_at_utc TEXT,
  game_id TEXT NOT NULL,
  player_id INTEGER NOT NULL,
  stat TEXT NOT NULL,
  line REAL NOT NULL,
  settlement TEXT NOT NULL CHECK(settlement IN ('over','under','push')),
  target_stat_value REAL NOT NULL,
  probability_model_version TEXT,
  audit_grade INTEGER NOT NULL CHECK(audit_grade IN (0,1)),
  FOREIGN KEY(archive_id) REFERENCES wnba_pregame_archives(archive_id)
);
CREATE INDEX IF NOT EXISTS idx_wnba_obs_model ON wnba_backtest_observations(probability_model_version);
CREATE INDEX IF NOT EXISTS idx_wnba_obs_stat ON wnba_backtest_observations(stat);

CREATE TABLE IF NOT EXISTS wnba_grading_attempts (
  attempt_id INTEGER PRIMARY KEY AUTOINCREMENT,
  archive_id TEXT NOT NULL,
  attempted_at_utc TEXT NOT NULL,
  outcome TEXT NOT NULL,
  detail TEXT,
  observation_id TEXT,
  FOREIGN KEY(archive_id) REFERENCES wnba_pregame_archives(archive_id)
);
CREATE INDEX IF NOT EXISTS idx_wnba_attempt_archive ON wnba_grading_attempts(archive_id,attempted_at_utc);

CREATE TRIGGER IF NOT EXISTS wnba_archives_no_update BEFORE UPDATE ON wnba_pregame_archives
BEGIN SELECT RAISE(ABORT,'wnba_pregame_archives is immutable'); END;
CREATE TRIGGER IF NOT EXISTS wnba_archives_no_delete BEFORE DELETE ON wnba_pregame_archives
BEGIN SELECT RAISE(ABORT,'wnba_pregame_archives is immutable'); END;
CREATE TRIGGER IF NOT EXISTS wnba_observations_no_update BEFORE UPDATE ON wnba_backtest_observations
BEGIN SELECT RAISE(ABORT,'wnba_backtest_observations is immutable'); END;
CREATE TRIGGER IF NOT EXISTS wnba_observations_no_delete BEFORE DELETE ON wnba_backtest_observations
BEGIN SELECT RAISE(ABORT,'wnba_backtest_observations is immutable'); END;
"""


def initialize_store(db_path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    path = resolve_store_path(db_path)
    conn = _connect(path)
    try:
        conn.executescript(_SCHEMA)
        conn.execute(
            "INSERT OR IGNORE INTO wnba_store_metadata(key,value) VALUES('schema_version',?)",
            (STORE_SCHEMA_VERSION,),
        )
        row = conn.execute("SELECT value FROM wnba_store_metadata WHERE key='schema_version'").fetchone()
        if row is None or row["value"] != STORE_SCHEMA_VERSION:
            raise WNBAPregameStoreError("Unexpected WNBA Step 5J store schema version.")
    finally:
        conn.close()
    return {
        "source": MODEL_SOURCE,
        "model_version": MODEL_VERSION,
        "schema_version": STORE_SCHEMA_VERSION,
        "store_path": str(path),
        "persistent_path_explicitly_configured": db_path is not None or os.environ.get(STORE_PATH_ENV) is not None,
    }


def _archive_row(archive: dict[str, Any], verified: bool) -> dict[str, Any]:
    content = archive.get("content")
    if not isinstance(content, dict):
        raise WNBAPregameStoreError("Step 5J archive content is missing.")
    if not verified:
        raise WNBAHistoricalBacktestNotReadyError(
            "Step 5J durable store accepts only verifiably signed audit-grade archives."
        )
    prop = content.get("prop") or {}
    threshold = content.get("threshold_reference") or {}
    snapshot = content.get("snapshot_reference") or {}
    signature = archive.get("signature") or {}
    signature_value = signature.get("value")
    if not isinstance(signature_value, str) or len(signature_value) != 64:
        raise WNBAPregameStoreError("Step 5J archive HMAC signature is missing or malformed.")
    tip = _dt(content.get("official_game_tip_utc"), "official game tip")
    archived = _dt(content.get("archived_at_utc"), "archive timestamp")
    if archived >= tip:
        raise WNBAHistoricalBacktestNotReadyError("Step 5J cannot persist an archive created at or after tip.")
    logical_identity = {
        "game_id": content.get("game_id"),
        "player_id": content.get("player_id"),
        "stat": prop.get("stat"),
        "line": prop.get("line"),
        "probability_model_version": threshold.get("model_version"),
        "probability_fingerprint_sha256": threshold.get("probability_fingerprint_sha256"),
        "snapshot_content_sha256": snapshot.get("content_sha256"),
    }
    try:
        return {
            "archive_id": str(archive["archive_id"]),
            "content_sha256": str(archive["content_sha256"]),
            "logical_prediction_key": _hash(logical_identity),
            "archive_json": _json(archive),
            "official_game_tip_utc": tip.isoformat(),
            "archived_at_utc": archived.isoformat(),
            "season": content.get("season"),
            "season_type": content.get("season_type"),
            "game_id": str(content["game_id"]),
            "player_id": int(content["player_id"]),
            "team_key": str(content["team_key"]),
            "opponent_team_key": str(content["opponent_team_key"]),
            "stat": str(prop["stat"]),
            "line": float(prop["line"]),
            "probability_model_version": threshold.get("model_version"),
            "probability_fingerprint_sha256": threshold.get("probability_fingerprint_sha256"),
            "snapshot_content_sha256": snapshot.get("content_sha256"),
            "signature_value": signature_value,
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise WNBAPregameStoreError("Step 5J archive identity is malformed.") from exc


def persist_pregame_archive(
    archive: dict[str, Any], *, db_path: str | os.PathLike[str] | None = None,
    signing_secret: str | bytes | None = None,
) -> dict[str, Any]:
    initialize_store(db_path)
    _, verified = _verify_archive_envelope(
        archive, signing_secret=signing_secret, require_audit_grade=True
    )
    row = _archive_row(archive, verified)
    conn = _connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        same_id = conn.execute(
            "SELECT archive_id,content_sha256,archive_json FROM wnba_pregame_archives WHERE archive_id=?",
            (row["archive_id"],),
        ).fetchone()
        if same_id is not None:
            if same_id["content_sha256"] != row["content_sha256"] or same_id["archive_json"] != row["archive_json"]:
                raise WNBAPregameStoreConflictError("Immutable archive_id already exists with different content.")
            conn.execute("COMMIT")
            return {"stored":False,"idempotent_replay":True,"logical_idempotent_replay":False,
                    "archive_id":same_id["archive_id"],"request_archive_id":row["archive_id"],
                    "content_sha256":same_id["content_sha256"],"signature_verified":True}
        logical = conn.execute(
            "SELECT archive_id,content_sha256 FROM wnba_pregame_archives WHERE logical_prediction_key=?",
            (row["logical_prediction_key"],),
        ).fetchone()
        if logical is not None:
            conn.execute("COMMIT")
            return {"stored":False,"idempotent_replay":True,"logical_idempotent_replay":True,
                    "archive_id":logical["archive_id"],"request_archive_id":row["archive_id"],
                    "content_sha256":logical["content_sha256"],"signature_verified":True}
        collision = conn.execute(
            "SELECT archive_id FROM wnba_pregame_archives WHERE content_sha256=?",
            (row["content_sha256"],),
        ).fetchone()
        if collision is not None:
            raise WNBAPregameStoreConflictError("Archive content hash already exists under a different archive_id.")
        conn.execute(
            """INSERT INTO wnba_pregame_archives(
            archive_id,content_sha256,logical_prediction_key,archive_json,stored_at_utc,
            official_game_tip_utc,archived_at_utc,season,season_type,game_id,player_id,
            team_key,opponent_team_key,stat,line,probability_model_version,
            probability_fingerprint_sha256,snapshot_content_sha256,signature_value,signature_verified)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1)""",
            (row["archive_id"],row["content_sha256"],row["logical_prediction_key"],row["archive_json"],_iso(),
             row["official_game_tip_utc"],row["archived_at_utc"],row["season"],row["season_type"],
             row["game_id"],row["player_id"],row["team_key"],row["opponent_team_key"],row["stat"],row["line"],
             row["probability_model_version"],row["probability_fingerprint_sha256"],row["snapshot_content_sha256"],
             row["signature_value"]),
        )
        conn.execute("COMMIT")
    except Exception:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
    return {"stored":True,"idempotent_replay":False,"logical_idempotent_replay":False,
            "archive_id":row["archive_id"],"request_archive_id":row["archive_id"],
            "content_sha256":row["content_sha256"],"signature_verified":True}


def get_stored_archive(archive_id: str, *, db_path: str | os.PathLike[str] | None = None) -> dict[str, Any]:
    initialize_store(db_path)
    conn = _connect(db_path)
    try:
        row = conn.execute("SELECT archive_json FROM wnba_pregame_archives WHERE archive_id=?",(archive_id,)).fetchone()
    finally:
        conn.close()
    if row is None:
        raise WNBAPregameStoreError(f"Stored archive {archive_id} was not found.")
    return json.loads(row["archive_json"])


def archive_and_persist_prediction(
    threshold: dict[str, Any], snapshot: dict[str, Any], *,
    db_path: str | os.PathLike[str] | None = None,
    archived_at_utc: datetime | None = None,
    signing_secret: str | bytes | None = None,
) -> dict[str, Any]:
    archive = build_pregame_archive_envelope(
        threshold, snapshot, archived_at_utc=archived_at_utc, signing_secret=signing_secret
    )
    persistence = persist_pregame_archive(
        archive, db_path=db_path, signing_secret=signing_secret
    )
    return {
        "source":MODEL_SOURCE,"data_type":"wnba_durable_pregame_prediction_archive",
        "schema_version":STORE_SCHEMA_VERSION,"model_version":MODEL_VERSION,
        "archive":get_stored_archive(persistence["archive_id"],db_path=db_path),
        "persistence":persistence,
    }


def _observation_row(observation: dict[str, Any]) -> dict[str, Any]:
    content = observation.get("content") if isinstance(observation,dict) else None
    digest = observation.get("observation_content_sha256") if isinstance(observation,dict) else None
    if not isinstance(content,dict) or not isinstance(digest,str) or len(digest)!=64 or _hash(content)!=digest:
        raise WNBAPregameStoreError("Step 5J observation integrity check failed.")
    ref, actual, prop, trust = (content.get(k) or {} for k in ("archive_reference","actual","prop","trust"))
    if ref.get("signature_verified") is not True or trust.get("audit_grade") is not True:
        raise WNBAHistoricalBacktestNotReadyError(
            "Step 5J stores only audit-grade observations from verified signed archives."
        )
    settlement = actual.get("settlement")
    if settlement not in {"over","under","push"}:
        raise WNBAPregameStoreError("Step 5J observation settlement is invalid.")
    try:
        return {
            "observation_id":str(observation["observation_id"]),"digest":digest,
            "json":_json(observation),"archive_id":str(ref["archive_id"]),
            "archive_hash":str(ref["content_sha256"]),"generated_at_utc":observation.get("generated_at_utc"),
            "game_id":str(content["game_id"]),"player_id":int(content["player_id"]),
            "stat":str(prop["stat"]),"line":float(prop["line"]),"settlement":settlement,
            "target_stat_value":float(actual["target_stat_value"]),
            "probability_model_version":content.get("probability_model_version"),
        }
    except (KeyError,TypeError,ValueError) as exc:
        raise WNBAPregameStoreError("Step 5J observation identity is malformed.") from exc


def persist_graded_observation(
    observation: dict[str, Any], *, db_path: str | os.PathLike[str] | None = None
) -> dict[str, Any]:
    initialize_store(db_path)
    row = _observation_row(observation)
    conn = _connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        archive = conn.execute(
            "SELECT content_sha256,game_id,player_id,stat,line FROM wnba_pregame_archives WHERE archive_id=?",
            (row["archive_id"],),
        ).fetchone()
        if archive is None:
            raise WNBAPregameStoreConflictError("Cannot store an observation before its immutable pregame archive exists.")
        if row["archive_hash"] != archive["content_sha256"] or str(archive["game_id"])!=row["game_id"] \
           or int(archive["player_id"])!=row["player_id"] or str(archive["stat"])!=row["stat"] \
           or abs(float(archive["line"])-row["line"])>1e-12:
            raise WNBAPregameStoreConflictError("Observation identity does not match stored archive.")
        existing = conn.execute(
            "SELECT observation_id,observation_content_sha256,observation_json FROM wnba_backtest_observations WHERE archive_id=?",
            (row["archive_id"],),
        ).fetchone()
        if existing is not None:
            if existing["observation_content_sha256"]!=row["digest"] or existing["observation_json"]!=row["json"]:
                raise WNBAPregameStoreConflictError("Immutable archive already has a different graded observation.")
            conn.execute("COMMIT")
            return {"stored":False,"idempotent_replay":True,"archive_id":row["archive_id"],
                    "observation_id":existing["observation_id"],"observation_content_sha256":row["digest"]}
        conn.execute(
            """INSERT INTO wnba_backtest_observations(
            observation_id,observation_content_sha256,observation_json,archive_id,stored_at_utc,
            generated_at_utc,game_id,player_id,stat,line,settlement,target_stat_value,
            probability_model_version,audit_grade) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,1)""",
            (row["observation_id"],row["digest"],row["json"],row["archive_id"],_iso(),row["generated_at_utc"],
             row["game_id"],row["player_id"],row["stat"],row["line"],row["settlement"],row["target_stat_value"],
             row["probability_model_version"]),
        )
        conn.execute("COMMIT")
    except Exception:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()
    return {"stored":True,"idempotent_replay":False,"archive_id":row["archive_id"],
            "observation_id":row["observation_id"],"observation_content_sha256":row["digest"]}


def list_pending_archives(
    *, db_path: str | os.PathLike[str] | None = None,
    now_utc: datetime | None = None, limit: int = 100,
) -> list[dict[str, Any]]:
    if not isinstance(limit,int) or not 1<=limit<=MAX_SWEEP_LIMIT:
        raise ValueError(f"Step 5J pending archive limit must be 1 through {MAX_SWEEP_LIMIT}.")
    initialize_store(db_path)
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            """SELECT a.archive_json FROM wnba_pregame_archives a
            LEFT JOIN wnba_backtest_observations o ON o.archive_id=a.archive_id
            WHERE o.archive_id IS NULL AND a.official_game_tip_utc < ?
            ORDER BY a.official_game_tip_utc,a.archive_id LIMIT ?""",
            (_iso(now_utc),limit),
        ).fetchall()
    finally:
        conn.close()
    return [json.loads(r["archive_json"]) for r in rows]


def _attempt(db_path: str | os.PathLike[str] | None, archive_id: str, outcome: str,
             detail: str | None, observation_id: str | None) -> None:
    conn = _connect(db_path)
    try:
        conn.execute(
            "INSERT INTO wnba_grading_attempts(archive_id,attempted_at_utc,outcome,detail,observation_id) VALUES(?,?,?,?,?)",
            (archive_id,_iso(),outcome,detail,observation_id),
        )
    finally:
        conn.close()


def grade_pending_archives(
    *, db_path: str | os.PathLike[str] | None = None,
    signing_secret: str | bytes | None = None,
    now_utc: datetime | None = None, limit: int = 100,
    grader: Callable[...,dict[str,Any]] | None = None,
) -> dict[str, Any]:
    grade_fn = grader or get_graded_archived_prediction
    pending = list_pending_archives(db_path=db_path,now_utc=now_utc,limit=limit)
    counts = {k:0 for k in (
        "attempted","graded","idempotent_observation","not_found","not_ready",
        "upstream_error","model_input_error","store_error"
    )}
    results=[]
    for archive in pending:
        aid=str(archive.get("archive_id")); counts["attempted"]+=1
        outcome="unknown"; detail=None; oid=None
        try:
            obs=grade_fn(archive,signing_secret=signing_secret,require_audit_grade=True)
            stored=persist_graded_observation(obs,db_path=db_path); oid=stored["observation_id"]
            outcome="graded" if stored["stored"] else "idempotent_observation"; counts[outcome]+=1
        except WNBAHistoricalBacktestNotFoundError as exc:
            outcome="not_found"; detail=str(exc); counts[outcome]+=1
        except WNBAHistoricalBacktestNotReadyError as exc:
            outcome="not_ready"; detail=str(exc); counts[outcome]+=1
        except WNBAHistoricalBacktestUpstreamError as exc:
            outcome="upstream_error"; detail=str(exc); counts[outcome]+=1
        except WNBAHistoricalBacktestModelInputError as exc:
            outcome="model_input_error"; detail=str(exc); counts[outcome]+=1
        except Exception as exc:
            outcome="store_error"; detail=f"{type(exc).__name__}: {exc}"; counts[outcome]+=1
        _attempt(db_path,aid,outcome,detail,oid)
        row={"archive_id":aid,"outcome":outcome}
        if oid: row["observation_id"]=oid
        if detail: row["detail"]=detail
        results.append(row)
    return {
        "source":MODEL_SOURCE,"data_type":"wnba_automated_backtest_grading_sweep",
        "schema_version":STORE_SCHEMA_VERSION,"model_version":MODEL_VERSION,
        "generated_at_utc":_iso(),"pending_candidates_loaded":len(pending),
        "counts":counts,"results":results,
        "retry_semantics":{"not_found_and_not_ready_remain_pending":True,
                           "successful_observations_are_immutable":True,
                           "repeated_sweeps_are_idempotent":True},
    }


def get_stored_observations(
    *, db_path: str | os.PathLike[str] | None = None,
    probability_model_version: str | None = None,
    stat: str | None = None, limit: int = MAX_OBSERVATION_LIMIT,
) -> list[dict[str, Any]]:
    if not isinstance(limit,int) or not 1<=limit<=MAX_OBSERVATION_LIMIT:
        raise ValueError(f"Step 5J observation limit must be 1 through {MAX_OBSERVATION_LIMIT:,}.")
    initialize_store(db_path)
    clauses=["audit_grade=1"]; params=[]
    if probability_model_version:
        clauses.append("probability_model_version=?"); params.append(probability_model_version)
    if stat:
        clauses.append("stat=?"); params.append(stat)
    params.append(limit)
    conn=_connect(db_path)
    try:
        rows=conn.execute(
            f"SELECT observation_json FROM wnba_backtest_observations WHERE {' AND '.join(clauses)} ORDER BY stored_at_utc,observation_id LIMIT ?",
            tuple(params),
        ).fetchall()
    finally:
        conn.close()
    return [json.loads(r["observation_json"]) for r in rows]


def evaluate_stored_calibration(
    *, db_path: str | os.PathLike[str] | None = None,
    probability_model_version: str | None = None,
    require_single_probability_model_version: bool = True,
) -> dict[str, Any]:
    rows=get_stored_observations(db_path=db_path,probability_model_version=probability_model_version)
    if not rows:
        raise WNBAPregameStoreNotReadyError("No audit-grade graded WNBA observations are stored yet.")
    return evaluate_backtest_observations(
        rows,require_audit_grade=True,
        require_single_probability_model_version=require_single_probability_model_version,
    )


def get_store_status(
    *, db_path: str | os.PathLike[str] | None = None,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    init=initialize_store(db_path); cutoff=_iso(now_utc); conn=_connect(db_path)
    try:
        archives=int(conn.execute("SELECT COUNT(*) n FROM wnba_pregame_archives").fetchone()["n"])
        obs=int(conn.execute("SELECT COUNT(*) n FROM wnba_backtest_observations").fetchone()["n"])
        due=int(conn.execute("""SELECT COUNT(*) n FROM wnba_pregame_archives a
            LEFT JOIN wnba_backtest_observations o ON o.archive_id=a.archive_id
            WHERE o.archive_id IS NULL AND a.official_game_tip_utc < ?""",(cutoff,)).fetchone()["n"])
        future=int(conn.execute("""SELECT COUNT(*) n FROM wnba_pregame_archives a
            LEFT JOIN wnba_backtest_observations o ON o.archive_id=a.archive_id
            WHERE o.archive_id IS NULL AND a.official_game_tip_utc >= ?""",(cutoff,)).fetchone()["n"])
        attempts=int(conn.execute("SELECT COUNT(*) n FROM wnba_grading_attempts").fetchone()["n"])
        settlements={r["settlement"]:int(r["n"]) for r in conn.execute(
            "SELECT settlement,COUNT(*) n FROM wnba_backtest_observations GROUP BY settlement").fetchall()}
    finally:
        conn.close()
    return {
        "source":MODEL_SOURCE,"data_type":"wnba_durable_backtest_store_status",
        "schema_version":STORE_SCHEMA_VERSION,"model_version":MODEL_VERSION,"generated_at_utc":_iso(),
        "store":init,
        "counts":{"pregame_archives":archives,"graded_observations":obs,
                  "due_ungraded_archives":due,"future_ungraded_archives":future,
                  "grading_attempts":attempts,
                  "settlements":{k:settlements.get(k,0) for k in ("over","under","push")}},
        "guardrails":{"archives_are_append_only":True,"graded_observations_are_append_only":True,
                      "audit_grade_signature_required_for_persistence":True,
                      "logical_prediction_retries_are_idempotent_first_write_wins":True,
                      "grading_only_considers_archives_after_official_tip":True,
                      "calibration_reuses_step_5i_version_isolation_and_push_rules":True,
                      "production_requires_persistent_filesystem_for_sqlite_durability":True},
    }
