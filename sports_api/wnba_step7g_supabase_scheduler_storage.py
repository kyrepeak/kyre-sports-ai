"""Step 7G Supabase persistence adapter for the frozen WNBA scheduler chain.

This module moves only scheduler/provider state off Render's ephemeral filesystem.
It deliberately reuses the frozen Step 5P/5O validators and payload semantics.
No model, ranking, Monte Carlo, provider-selection, or publication math lives here.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
from typing import Any, Mapping
from uuid import uuid4

from sports_api.database.wnba_current_board_store import (
    MAX_PUBLICATION_LIMIT,
    MAX_RUN_LIMIT,
    WNBACurrentBoardStoreConflictError,
    WNBACurrentBoardStoreError,
    WNBACurrentBoardStoreNotReadyError,
    _dt as _board_dt,
    _publication_row,
)
from sports_api.database.wnba_prop_feed_store import (
    MAX_HEALTH_ATTEMPTS,
    MAX_LIST_LIMIT,
    SUCCESS_OUTCOMES,
    WNBAPropFeedStoreConflictError,
    WNBAPropFeedStoreError,
    _parse_timestamp,
    _provider_health_from_attempts,
    _snapshot_payload,
)
from sports_api.wnba_step6q_durable_storage import SUPABASE_BACKEND
from sports_api.wnba_step6r_supabase_storage import (
    SupabaseDurableStorage,
    build_step6r_durable_storage,
)

MODEL_SOURCE = "Kyre Sports API WNBA Step 7G Supabase scheduler persistence"
MODEL_VERSION = "wnba_step_7g_supabase_scheduler_persistence_v1"

BOARD_PUBLICATIONS_TABLE = "wnba_step7g_board_publications"
SCHEDULER_RUNS_TABLE = "wnba_step7g_board_scheduler_runs"
FEED_SNAPSHOTS_TABLE = "wnba_step7g_prop_feed_snapshots"
FEED_ATTEMPTS_TABLE = "wnba_step7g_prop_feed_attempts"
SCHEDULER_LOCKS_TABLE = "wnba_step7g_scheduler_locks"
LOCK_HISTORY_TABLE = "wnba_step7g_scheduler_lock_history"
LOCK_ACQUIRE_RPC = "wnba_step7g_scheduler_lock_acquire"
LOCK_RELEASE_RPC = "wnba_step7g_scheduler_lock_release"
SCHEDULER_LOCK_KEY = "wnba-step7g-production-cycle.lock"
DEFAULT_LOCK_LEASE_SECONDS = 3600


class WNBAStep7GSchedulerStorageError(RuntimeError):
    pass


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime | None = None) -> str:
    dt = value or _utc_now()
    if dt.tzinfo is None or dt.utcoffset() is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def _json_list(response: Any, *, operation: str) -> list[dict[str, Any]]:
    try:
        payload = response.json()
    except (ValueError, json.JSONDecodeError) as exc:
        raise WNBAStep7GSchedulerStorageError(
            f"Supabase returned invalid JSON during {operation}."
        ) from exc
    if not isinstance(payload, list) or any(not isinstance(row, dict) for row in payload):
        raise WNBAStep7GSchedulerStorageError(
            f"Supabase returned an unexpected row shape during {operation}."
        )
    return payload


def _optional_sha(value: Any) -> str | None:
    text = str(value or "").strip().casefold()
    return text or None


class Step7GSupabaseSchedulerStore:
    """Adapter exposing Step-5P/5O-compatible persistence call signatures."""

    def __init__(self, env: Mapping[str, str]):
        backend = build_step6r_durable_storage(env=env)
        if backend.backend_id != SUPABASE_BACKEND or not isinstance(backend, SupabaseDurableStorage):
            raise WNBAStep7GSchedulerStorageError(
                "Step 7G scheduler persistence requires the configured Supabase backend."
            )
        self.backend = backend

    def _select(
        self,
        table: str,
        *,
        select: str = "*",
        filters: Mapping[str, str] | None = None,
        order: str | None = None,
        limit: int | None = None,
        operation: str,
    ) -> list[dict[str, Any]]:
        params: dict[str, str] = {"select": select}
        params.update(dict(filters or {}))
        if order:
            params["order"] = order
        if limit is not None:
            params["limit"] = str(int(limit))
        response = self.backend._request(  # isolated server-side adapter over frozen Step 6R transport
            "GET", table, params=params, operation=operation
        )
        return _json_list(response, operation=operation)

    def _insert(self, table: str, row: Mapping[str, Any], *, operation: str) -> dict[str, Any]:
        response = self.backend._request(
            "POST",
            table,
            json_body=dict(row),
            prefer="return=representation",
            operation=operation,
        )
        rows = _json_list(response, operation=operation)
        if len(rows) != 1:
            raise WNBAStep7GSchedulerStorageError(
                f"Supabase did not return exactly one row during {operation}."
            )
        return rows[0]

    # ------------------------------------------------------------------
    # Frozen Step 5P publication + scheduler-run signatures
    # ------------------------------------------------------------------
    def persist_publication(
        self,
        publication: dict[str, Any],
        *,
        path: Any = None,
        env: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        del path, env
        try:
            row = _publication_row(publication)
        except WNBACurrentBoardStoreError:
            raise
        except Exception as exc:
            raise WNBACurrentBoardStoreError(str(exc)) from exc

        by_id = self._select(
            BOARD_PUBLICATIONS_TABLE,
            select="publication_id,content_sha256,publication_json",
            filters={"publication_id": f"eq.{row['publication_id']}"},
            limit=1,
            operation="Step 7G publication id lookup",
        )
        if by_id:
            existing = by_id[0]
            if (
                str(existing.get("content_sha256")) != row["content_sha256"]
                or existing.get("publication_json") != publication
            ):
                raise WNBACurrentBoardStoreConflictError(
                    "Immutable Step 7G publication_id already exists with different content."
                )
            return {
                "stored": False,
                "idempotent_replay": True,
                "logical_idempotent_replay": False,
                "publication_id": row["publication_id"],
                "content_sha256": row["content_sha256"],
                "storage_backend": SUPABASE_BACKEND,
            }

        logical = self._select(
            BOARD_PUBLICATIONS_TABLE,
            select="publication_id,content_sha256",
            filters={"logical_publication_key": f"eq.{row['logical_publication_key']}"},
            limit=1,
            operation="Step 7G logical publication lookup",
        )
        if logical:
            return {
                "stored": False,
                "idempotent_replay": True,
                "logical_idempotent_replay": True,
                "publication_id": logical[0]["publication_id"],
                "content_sha256": logical[0]["content_sha256"],
                "storage_backend": SUPABASE_BACKEND,
            }

        collision = self._select(
            BOARD_PUBLICATIONS_TABLE,
            select="publication_id",
            filters={"content_sha256": f"eq.{row['content_sha256']}"},
            limit=1,
            operation="Step 7G publication content lookup",
        )
        if collision:
            raise WNBACurrentBoardStoreConflictError(
                "Step 7G publication content hash exists under another publication_id."
            )

        stored = self._insert(
            BOARD_PUBLICATIONS_TABLE,
            {
                "publication_id": row["publication_id"],
                "content_sha256": row["content_sha256"],
                "logical_publication_key": row["logical_publication_key"],
                "publication_json": publication,
                "published_at_utc": row["published_at_utc"],
                "valid_until_utc": row["valid_until_utc"],
                "date": row["date"],
                "season": row["season"],
                "season_type": row["season_type"],
                "serving_state": row["serving_state"],
                "selected_provider_id": row["selected_provider_id"],
                "source_feed_fingerprint_sha256": row["source_feed_fingerprint_sha256"],
                "step_5l_daily_board_fingerprint_sha256": row["step_5l_daily_board_fingerprint_sha256"],
                "probability_board_count": row["probability_board_count"],
                "value_board_count": row["value_board_count"],
                "archived_prediction_count": row["archived_prediction_count"],
            },
            operation="Step 7G publication insert",
        )
        if stored.get("publication_id") != row["publication_id"]:
            raise WNBACurrentBoardStoreError("Step 7G publication acknowledgement mismatch.")
        return {
            "stored": True,
            "idempotent_replay": False,
            "logical_idempotent_replay": False,
            "publication_id": row["publication_id"],
            "content_sha256": row["content_sha256"],
            "storage_backend": SUPABASE_BACKEND,
        }

    def get_latest_publication(
        self,
        *,
        date: str | None = None,
        season: int | None = None,
        now_utc: datetime | None = None,
        require_current: bool = False,
        path: Any = None,
        env: Mapping[str, str] | None = None,
    ) -> dict[str, Any] | None:
        del path, env
        filters: dict[str, str] = {}
        if date is not None:
            filters["date"] = f"eq.{date}"
        if season is not None:
            filters["season"] = f"eq.{int(season)}"
        rows = self._select(
            BOARD_PUBLICATIONS_TABLE,
            select="publication_json,valid_until_utc",
            filters=filters,
            order="published_at_utc.desc,publication_id.desc",
            limit=1,
            operation="Step 7G latest publication read",
        )
        if not rows:
            return None
        publication = rows[0].get("publication_json")
        if not isinstance(publication, dict):
            raise WNBACurrentBoardStoreError("Step 7G stored publication JSON is malformed.")
        now = now_utc or _utc_now()
        if now.tzinfo is None or now.utcoffset() is None:
            now = now.replace(tzinfo=timezone.utc)
        else:
            now = now.astimezone(timezone.utc)
        valid_until = _board_dt(rows[0].get("valid_until_utc"), "stored valid-until timestamp")
        is_current = now < valid_until
        result = dict(publication)
        result["serving"] = {
            "is_current": is_current,
            "evaluated_at_utc": now.isoformat(),
            "seconds_until_expiry": max(0.0, round((valid_until - now).total_seconds(), 3)),
        }
        if require_current and not is_current:
            raise WNBACurrentBoardStoreNotReadyError(
                "WNBA Step 7G latest published board is expired."
            )
        return result

    def list_publications(
        self,
        *,
        date: str | None = None,
        season: int | None = None,
        limit: int = 100,
        path: Any = None,
        env: Mapping[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        del path, env
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_PUBLICATION_LIMIT:
            raise ValueError(f"WNBA Step 7G publication limit must be 1 through {MAX_PUBLICATION_LIMIT}.")
        filters: dict[str, str] = {}
        if date is not None:
            filters["date"] = f"eq.{date}"
        if season is not None:
            filters["season"] = f"eq.{int(season)}"
        rows = self._select(
            BOARD_PUBLICATIONS_TABLE,
            select="publication_json",
            filters=filters,
            order="published_at_utc.desc,publication_id.desc",
            limit=limit,
            operation="Step 7G publication history read",
        )
        return [row["publication_json"] for row in rows if isinstance(row.get("publication_json"), dict)]

    def append_scheduler_run(
        self,
        run: dict[str, Any],
        *,
        path: Any = None,
        env: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        del path, env
        if not isinstance(run, dict):
            raise WNBACurrentBoardStoreError("WNBA Step 7G scheduler run must be an object.")
        try:
            run_id = str(run["run_id"])
            started = _board_dt(run["started_at_utc"], "scheduler started_at_utc")
            completed = _board_dt(run["completed_at_utc"], "scheduler completed_at_utc")
            target_date = str(run["date"])
            season = int(run["season"])
            outcome = str(run["outcome"])
            provider_attempted = bool(run["provider_collection_attempted"])
            rebuild_attempted = bool(run["board_rebuild_attempted"])
        except (KeyError, TypeError, ValueError) as exc:
            raise WNBACurrentBoardStoreError("WNBA Step 7G scheduler run identity is malformed.") from exc
        if not run_id or completed < started or season <= 0 or not outcome:
            raise WNBACurrentBoardStoreError("WNBA Step 7G scheduler run timing/identity is invalid.")
        existing = self._select(
            SCHEDULER_RUNS_TABLE,
            select="run_id,run_json",
            filters={"run_id": f"eq.{run_id}"},
            limit=1,
            operation="Step 7G scheduler run lookup",
        )
        if existing:
            if existing[0].get("run_json") != run:
                raise WNBACurrentBoardStoreConflictError(
                    "WNBA Step 7G scheduler run_id already exists with different content."
                )
            return {"stored": False, "idempotent_replay": True, "run_id": run_id, "storage_backend": SUPABASE_BACKEND}
        next_due = run.get("next_due_at_utc")
        if next_due is not None:
            next_due = _board_dt(next_due, "scheduler next_due_at_utc").isoformat()
        stored = self._insert(
            SCHEDULER_RUNS_TABLE,
            {
                "run_id": run_id,
                "run_json": run,
                "started_at_utc": started.isoformat(),
                "completed_at_utc": completed.isoformat(),
                "date": target_date,
                "season": season,
                "outcome": outcome,
                "provider_collection_attempted": provider_attempted,
                "board_rebuild_attempted": rebuild_attempted,
                "publication_id": run.get("publication_id"),
                "selected_provider_id": run.get("selected_provider_id"),
                "source_feed_fingerprint_sha256": _optional_sha(run.get("source_feed_fingerprint_sha256")),
                "next_due_at_utc": next_due,
            },
            operation="Step 7G scheduler run insert",
        )
        if stored.get("run_id") != run_id:
            raise WNBACurrentBoardStoreError("Step 7G scheduler run acknowledgement mismatch.")
        return {"stored": True, "run_id": run_id, "storage_backend": SUPABASE_BACKEND}

    def get_latest_scheduler_run(
        self,
        *,
        date: str | None = None,
        season: int | None = None,
        path: Any = None,
        env: Mapping[str, str] | None = None,
    ) -> dict[str, Any] | None:
        del path, env
        filters: dict[str, str] = {}
        if date is not None:
            filters["date"] = f"eq.{date}"
        if season is not None:
            filters["season"] = f"eq.{int(season)}"
        rows = self._select(
            SCHEDULER_RUNS_TABLE,
            select="run_json",
            filters=filters,
            order="completed_at_utc.desc,run_id.desc",
            limit=1,
            operation="Step 7G latest scheduler run read",
        )
        return rows[0].get("run_json") if rows and isinstance(rows[0].get("run_json"), dict) else None

    def list_scheduler_runs(
        self,
        *,
        date: str | None = None,
        season: int | None = None,
        limit: int = 100,
        path: Any = None,
        env: Mapping[str, str] | None = None,
    ) -> list[dict[str, Any]]:
        del path, env
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_RUN_LIMIT:
            raise ValueError(f"WNBA Step 7G scheduler run limit must be 1 through {MAX_RUN_LIMIT}.")
        filters: dict[str, str] = {}
        if date is not None:
            filters["date"] = f"eq.{date}"
        if season is not None:
            filters["season"] = f"eq.{int(season)}"
        rows = self._select(
            SCHEDULER_RUNS_TABLE,
            select="run_json",
            filters=filters,
            order="completed_at_utc.desc,run_id.desc",
            limit=limit,
            operation="Step 7G scheduler history read",
        )
        return [row["run_json"] for row in rows if isinstance(row.get("run_json"), dict)]

    def get_board_store_status(self, *, path: Any = None, env: Mapping[str, str] | None = None) -> dict[str, Any]:
        del path, env
        publications = self._select(
            BOARD_PUBLICATIONS_TABLE,
            select="publication_id,published_at_utc,valid_until_utc,date,season,serving_state,selected_provider_id,probability_board_count,value_board_count,archived_prediction_count",
            order="published_at_utc.desc,publication_id.desc",
            limit=1,
            operation="Step 7G board status publication read",
        )
        runs = self._select(
            SCHEDULER_RUNS_TABLE,
            select="run_id,completed_at_utc,date,season,outcome,next_due_at_utc",
            order="completed_at_utc.desc,run_id.desc",
            limit=1,
            operation="Step 7G board status run read",
        )
        pub_count_rows = self._select(
            BOARD_PUBLICATIONS_TABLE,
            select="publication_id",
            operation="Step 7G publication count read",
        )
        run_count_rows = self._select(
            SCHEDULER_RUNS_TABLE,
            select="run_id",
            operation="Step 7G run count read",
        )
        return {
            "source": MODEL_SOURCE,
            "model_version": MODEL_VERSION,
            "storage_backend": SUPABASE_BACKEND,
            "persistent": True,
            "publication_count": len(pub_count_rows),
            "scheduler_run_count": len(run_count_rows),
            "latest_publication": publications[0] if publications else None,
            "latest_scheduler_run": runs[0] if runs else None,
            "append_only_publications": True,
            "append_only_scheduler_runs": True,
        }

    # ------------------------------------------------------------------
    # Frozen Step 5O snapshot + attempt signatures
    # ------------------------------------------------------------------
    def persist_feed_snapshot(
        self,
        *,
        provider_id: str,
        collection: dict[str, Any],
        feed_source: str,
        feed_format: str,
        odds_format: str,
        normalized_input_feed: dict[str, Any],
        adapter: dict[str, Any] | None = None,
        path: Any = None,
        env: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        del path, env
        try:
            payload = _snapshot_payload(
                provider_id=provider_id,
                collection=collection,
                feed_source=feed_source,
                feed_format=feed_format,
                odds_format=odds_format,
                normalized_input_feed=normalized_input_feed,
                adapter=adapter,
            )
        except WNBAPropFeedStoreError:
            raise
        except Exception as exc:
            raise WNBAPropFeedStoreError(str(exc)) from exc

        existing = self._select(
            FEED_SNAPSHOTS_TABLE,
            select="snapshot_id,snapshot_fingerprint_sha256",
            filters={"snapshot_id": f"eq.{payload['snapshot_id']}"},
            limit=1,
            operation="Step 7G feed snapshot lookup",
        )
        if existing:
            if existing[0].get("snapshot_fingerprint_sha256") != payload["snapshot_fingerprint_sha256"]:
                raise WNBAPropFeedStoreConflictError("WNBA Step 7G feed snapshot id collision detected.")
            return {
                "snapshot_id": payload["snapshot_id"],
                "snapshot_fingerprint_sha256": payload["snapshot_fingerprint_sha256"],
                "provider_id": payload["provider_id"],
                "collected_at_utc": payload["collected_at_utc"],
                "normalized_input_feed_sha256": payload["normalized_input_feed_sha256"],
                "inserted": False,
                "idempotent_replay": True,
                "storage_backend": SUPABASE_BACKEND,
            }

        stored = self._insert(
            FEED_SNAPSHOTS_TABLE,
            {
                "snapshot_id": payload["snapshot_id"],
                "snapshot_fingerprint_sha256": payload["snapshot_fingerprint_sha256"],
                "provider_id": payload["provider_id"],
                "feed_source": payload["feed_source"],
                "feed_format": payload["feed_format"],
                "odds_format": payload["odds_format"],
                "season": payload["season"],
                "date": payload["date"],
                "collected_at_utc": payload["collected_at_utc"],
                "stored_at_utc": payload["stored_at_utc"],
                "collection_id": payload["collection_id"],
                "collection_fingerprint_sha256": payload["collection_fingerprint_sha256"],
                "source_raw_feed_sha256": payload["source_raw_feed_sha256"],
                "normalized_input_feed_sha256": payload["normalized_input_feed_sha256"],
                "collection_json": collection,
                "normalized_input_feed_json": normalized_input_feed,
                "adapter_json": adapter,
            },
            operation="Step 7G feed snapshot insert",
        )
        if stored.get("snapshot_id") != payload["snapshot_id"]:
            raise WNBAPropFeedStoreError("Step 7G feed snapshot acknowledgement mismatch.")
        return {
            "snapshot_id": payload["snapshot_id"],
            "snapshot_fingerprint_sha256": payload["snapshot_fingerprint_sha256"],
            "provider_id": payload["provider_id"],
            "collected_at_utc": payload["collected_at_utc"],
            "normalized_input_feed_sha256": payload["normalized_input_feed_sha256"],
            "inserted": True,
            "idempotent_replay": False,
            "storage_backend": SUPABASE_BACKEND,
        }

    def append_feed_attempt(
        self,
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
        path: Any = None,
        env: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        del path, env
        provider = str(provider_id or "").strip()
        outcome_text = str(outcome or "").strip()
        if not provider or not outcome_text:
            raise WNBAPropFeedStoreError("WNBA Step 7G attempt provider/outcome cannot be empty.")
        if not isinstance(failover_rank, int) or isinstance(failover_rank, bool) or failover_rank < 1:
            raise WNBAPropFeedStoreError("WNBA Step 7G failover_rank must be a positive integer.")
        if not _parse_timestamp(started_at_utc):
            raise WNBAPropFeedStoreError("WNBA Step 7G attempt start timestamp is invalid.")
        completed = completed_at_utc or _iso()
        if not _parse_timestamp(completed):
            raise WNBAPropFeedStoreError("WNBA Step 7G attempt completion timestamp is invalid.")
        row = self._insert(
            FEED_ATTEMPTS_TABLE,
            {
                "provider_id": provider,
                "failover_rank": failover_rank,
                "started_at_utc": started_at_utc,
                "completed_at_utc": completed,
                "outcome": outcome_text,
                "error_type": str(error_type).strip() if error_type else None,
                "snapshot_id": str(snapshot_id).strip() if snapshot_id else None,
                "normalized_line_count": normalized_line_count,
                "playable_game_count": playable_game_count,
                "detail_json": detail,
            },
            operation="Step 7G provider attempt insert",
        )
        return {
            "attempt_id": int(row["attempt_id"]),
            "provider_id": provider,
            "failover_rank": failover_rank,
            "outcome": outcome_text,
            "snapshot_id": str(snapshot_id).strip() if snapshot_id else None,
            "completed_at_utc": completed,
            "storage_backend": SUPABASE_BACKEND,
        }

    def list_feed_snapshots(
        self,
        *,
        provider_id: str | None = None,
        date: str | None = None,
        season: int | None = None,
        limit: int = 100,
        include_payload: bool = False,
        path: Any = None,
        env: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        del path, env
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_LIST_LIMIT:
            raise ValueError(f"WNBA Step 7G snapshot limit must be 1 through {MAX_LIST_LIMIT}.")
        filters: dict[str, str] = {}
        if provider_id:
            filters["provider_id"] = f"eq.{str(provider_id).strip().casefold()}"
        if date:
            filters["date"] = f"eq.{str(date).strip()}"
        if season is not None:
            filters["season"] = f"eq.{int(season)}"
        select = "*" if include_payload else (
            "snapshot_id,snapshot_fingerprint_sha256,provider_id,feed_source,feed_format,odds_format,season,date,collected_at_utc,stored_at_utc,collection_id,collection_fingerprint_sha256,source_raw_feed_sha256,normalized_input_feed_sha256"
        )
        rows = self._select(
            FEED_SNAPSHOTS_TABLE,
            select=select,
            filters=filters,
            order="collected_at_utc.desc,stored_at_utc.desc",
            limit=limit,
            operation="Step 7G feed snapshot history read",
        )
        if include_payload:
            for row in rows:
                row["collection"] = row.pop("collection_json", None)
                row["normalized_input_feed"] = row.pop("normalized_input_feed_json", None)
                row["adapter"] = row.pop("adapter_json", None)
        return {
            "source": MODEL_SOURCE,
            "data_type": "wnba_step7g_prop_feed_snapshots",
            "model_version": MODEL_VERSION,
            "generated_at_utc": _iso(),
            "count": len(rows),
            "snapshots": rows,
        }

    def get_provider_health(
        self,
        provider_id: str | None = None,
        *,
        attempts_per_provider: int = 20,
        now_utc: datetime | None = None,
        path: Any = None,
        env: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        del path, env
        if not isinstance(attempts_per_provider, int) or isinstance(attempts_per_provider, bool) or not 1 <= attempts_per_provider <= MAX_HEALTH_ATTEMPTS:
            raise ValueError(f"WNBA Step 7G attempts_per_provider must be 1 through {MAX_HEALTH_ATTEMPTS}.")
        current = now_utc or _utc_now()
        if current.tzinfo is None or current.utcoffset() is None:
            raise ValueError("WNBA Step 7G now_utc must be timezone-aware.")
        current = current.astimezone(timezone.utc)
        if provider_id:
            provider_ids = [str(provider_id).strip().casefold()]
        else:
            rows = self._select(
                FEED_ATTEMPTS_TABLE,
                select="provider_id",
                order="provider_id.asc",
                operation="Step 7G provider id read",
            )
            provider_ids = sorted({str(row.get("provider_id")) for row in rows if row.get("provider_id")})
        health: list[dict[str, Any]] = []
        for pid in provider_ids:
            attempts = self._select(
                FEED_ATTEMPTS_TABLE,
                select="attempt_id,provider_id,started_at_utc,completed_at_utc,outcome,error_type,snapshot_id,normalized_line_count,playable_game_count,detail_json",
                filters={"provider_id": f"eq.{pid}"},
                order="completed_at_utc.desc,attempt_id.desc",
                limit=attempts_per_provider,
                operation=f"Step 7G provider health read {pid}",
            )
            health.append(_provider_health_from_attempts(pid, attempts, current))
        return {
            "source": MODEL_SOURCE,
            "data_type": "wnba_step7g_prop_feed_provider_health",
            "model_version": MODEL_VERSION,
            "generated_at_utc": _iso(),
            "attempts_per_provider": attempts_per_provider,
            "provider_count": len(health),
            "providers": health,
        }

    def get_feed_store_status(self) -> dict[str, Any]:
        snapshots = self._select(
            FEED_SNAPSHOTS_TABLE,
            select="snapshot_id",
            operation="Step 7G snapshot count read",
        )
        attempts = self._select(
            FEED_ATTEMPTS_TABLE,
            select="attempt_id,provider_id,outcome",
            operation="Step 7G attempt count read",
        )
        return {
            "source": MODEL_SOURCE,
            "model_version": MODEL_VERSION,
            "storage_backend": SUPABASE_BACKEND,
            "persistent": True,
            "snapshot_count": len(snapshots),
            "attempt_count": len(attempts),
            "provider_count": len({row.get('provider_id') for row in attempts if row.get('provider_id')}),
            "successful_attempt_count": sum(1 for row in attempts if row.get("outcome") in SUCCESS_OUTCOMES),
            "append_only_snapshots": True,
            "append_only_attempts": True,
        }

    # ------------------------------------------------------------------
    # Phase 7G long-lease production-cycle mutex
    # ------------------------------------------------------------------
    @contextmanager
    def scheduler_lock(
        self,
        activation_id: str,
        *,
        lease_seconds: int = DEFAULT_LOCK_LEASE_SECONDS,
    ):
        owner_token = str(uuid4())
        acquired = self.backend._rpc_bool(
            LOCK_ACQUIRE_RPC,
            {
                "p_lock_key": SCHEDULER_LOCK_KEY,
                "p_owner_token": owner_token,
                "p_activation_id": str(activation_id),
                "p_lease_seconds": int(lease_seconds),
            },
            operation="acquire Step 7G scheduler lock",
        )
        if not acquired:
            raise WNBAStep7GSchedulerStorageError(
                "Step 7G production scheduler lock is already owned by another activation."
            )
        outcome = "completed"
        detail: dict[str, Any] = {"released_cleanly": True}
        try:
            yield {"owner_token": owner_token, "activation_id": str(activation_id)}
        except Exception as exc:
            outcome = "cycle_error"
            detail = {"error_type": type(exc).__name__, "released_cleanly": True}
            raise
        finally:
            event_id = f"step7g-lock-{uuid4().hex}"
            active_error = outcome != "completed"
            try:
                released = self.backend._rpc_bool(
                    LOCK_RELEASE_RPC,
                    {
                        "p_lock_key": SCHEDULER_LOCK_KEY,
                        "p_owner_token": owner_token,
                        "p_event_id": event_id,
                        "p_outcome": outcome,
                        "p_detail": detail,
                    },
                    operation="release Step 7G scheduler lock",
                )
                if not released and not active_error:
                    raise WNBAStep7GSchedulerStorageError(
                        "Step 7G scheduler lock could not be released by its owner."
                    )
            except Exception:
                if not active_error:
                    raise

    def active_scheduler_locks(self) -> list[dict[str, Any]]:
        return self._select(
            SCHEDULER_LOCKS_TABLE,
            select="lock_key,activation_id,acquired_at_utc,expires_at_utc",
            operation="Step 7G active scheduler lock read",
        )

    def lock_history(self, limit: int = 20) -> list[dict[str, Any]]:
        return self._select(
            LOCK_HISTORY_TABLE,
            select="event_id,lock_key,activation_id,acquired_at_utc,released_at_utc,outcome,detail_json",
            order="released_at_utc.desc,event_id.desc",
            limit=limit,
            operation="Step 7G scheduler lock history read",
        )

    def describe(self) -> dict[str, Any]:
        desc = self.backend.describe()
        return {
            "source": MODEL_SOURCE,
            "model_version": MODEL_VERSION,
            "storage_backend": SUPABASE_BACKEND,
            "project_host": desc.get("project_host"),
            "board_publications_table": BOARD_PUBLICATIONS_TABLE,
            "scheduler_runs_table": SCHEDULER_RUNS_TABLE,
            "feed_snapshots_table": FEED_SNAPSHOTS_TABLE,
            "feed_attempts_table": FEED_ATTEMPTS_TABLE,
            "scheduler_locks_table": SCHEDULER_LOCKS_TABLE,
            "lock_history_table": LOCK_HISTORY_TABLE,
            "append_only_history": True,
            "secret_value_returned": False,
        }
