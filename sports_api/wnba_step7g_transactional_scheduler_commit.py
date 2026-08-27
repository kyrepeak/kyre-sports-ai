"""Transactional publication/run commit adapter for WNBA Step 7G.

Frozen Step 5P calls publication persistence before run-history persistence.  This
adapter defers a new publication until Step 5P supplies the matching run and then
commits both through one Supabase RPC transaction.  Existing/idempotent
publications are never rewritten.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from sports_api.database.wnba_current_board_store import (
    WNBACurrentBoardStoreConflictError,
    WNBACurrentBoardStoreError,
    _dt as _board_dt,
    _publication_row,
)
from sports_api.wnba_step6q_durable_storage import SUPABASE_BACKEND
from sports_api.wnba_step7g_supabase_scheduler_storage import (
    BOARD_PUBLICATIONS_TABLE,
    Step7GSupabaseSchedulerStore,
    WNBAStep7GSchedulerStorageError,
)

ATOMIC_COMMIT_RPC = "wnba_step7g_commit_publication_and_run"
MODEL_VERSION = "wnba_step_7g_transactional_scheduler_commit_v1"


class WNBAStep7GTransactionalCommitError(WNBAStep7GSchedulerStorageError):
    pass


def _optional_sha(value: Any) -> str | None:
    text = str(value or "").strip().casefold()
    return text or None


def _run_row(run: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(run, Mapping):
        raise WNBACurrentBoardStoreError("WNBA Step 7G scheduler run must be an object.")
    try:
        run_id = str(run["run_id"])
        started = _board_dt(run["started_at_utc"], "scheduler started_at_utc")
        completed = _board_dt(run["completed_at_utc"], "scheduler completed_at_utc")
        date = str(run["date"])
        season = int(run["season"])
        outcome = str(run["outcome"])
        provider_attempted = bool(run["provider_collection_attempted"])
        rebuild_attempted = bool(run["board_rebuild_attempted"])
    except (KeyError, TypeError, ValueError) as exc:
        raise WNBACurrentBoardStoreError("WNBA Step 7G scheduler run identity is malformed.") from exc
    if not run_id or completed < started or season <= 0 or not outcome:
        raise WNBACurrentBoardStoreError("WNBA Step 7G scheduler run timing/identity is invalid.")
    next_due = run.get("next_due_at_utc")
    if next_due is not None:
        next_due = _board_dt(next_due, "scheduler next_due_at_utc").isoformat()
    return {
        "run_id": run_id,
        "started_at_utc": started.isoformat(),
        "completed_at_utc": completed.isoformat(),
        "date": date,
        "season": season,
        "outcome": outcome,
        "provider_collection_attempted": provider_attempted,
        "board_rebuild_attempted": rebuild_attempted,
        "publication_id": str(run.get("publication_id") or "") or None,
        "selected_provider_id": str(run.get("selected_provider_id") or "") or None,
        "source_feed_fingerprint_sha256": _optional_sha(run.get("source_feed_fingerprint_sha256")),
        "next_due_at_utc": next_due,
    }


class Step7GTransactionalSchedulerCommit:
    def __init__(self, store: Step7GSupabaseSchedulerStore):
        self.store = store
        self._pending_publication: tuple[dict[str, Any], dict[str, Any]] | None = None

    def persist_publication(
        self,
        publication: dict[str, Any],
        *,
        path: Any = None,
        env: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        del path, env
        row = _publication_row(publication)
        if self._pending_publication is not None:
            raise WNBAStep7GTransactionalCommitError(
                "Step 7G already has an uncommitted publication in this cycle."
            )

        existing = self.store._select(
            BOARD_PUBLICATIONS_TABLE,
            select="publication_id,content_sha256,logical_publication_key,publication_json",
            filters={"publication_id": f"eq.{row['publication_id']}"},
            limit=1,
            operation="Step 7G transactional publication id lookup",
        )
        if existing:
            current = existing[0]
            if (
                current.get("content_sha256") != row["content_sha256"]
                or current.get("logical_publication_key") != row["logical_publication_key"]
                or current.get("publication_json") != publication
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
                "atomic_commit_deferred": False,
            }

        logical = self.store._select(
            BOARD_PUBLICATIONS_TABLE,
            select="publication_id,content_sha256,publication_json",
            filters={"logical_publication_key": f"eq.{row['logical_publication_key']}"},
            limit=1,
            operation="Step 7G transactional logical publication lookup",
        )
        if logical:
            return {
                "stored": False,
                "idempotent_replay": True,
                "logical_idempotent_replay": True,
                "publication_id": logical[0]["publication_id"],
                "content_sha256": logical[0]["content_sha256"],
                "storage_backend": SUPABASE_BACKEND,
                "atomic_commit_deferred": False,
            }

        collision = self.store._select(
            BOARD_PUBLICATIONS_TABLE,
            select="publication_id",
            filters={"content_sha256": f"eq.{row['content_sha256']}"},
            limit=1,
            operation="Step 7G transactional publication content lookup",
        )
        if collision:
            raise WNBACurrentBoardStoreConflictError(
                "Step 7G publication content hash exists under another publication_id."
            )

        self._pending_publication = (row, dict(publication))
        return {
            "stored": True,
            "idempotent_replay": False,
            "logical_idempotent_replay": False,
            "publication_id": row["publication_id"],
            "content_sha256": row["content_sha256"],
            "storage_backend": SUPABASE_BACKEND,
            "atomic_commit_deferred": True,
        }

    def append_scheduler_run(
        self,
        run: dict[str, Any],
        *,
        path: Any = None,
        env: Mapping[str, str] | None = None,
    ) -> dict[str, Any]:
        del path, env
        row = _run_row(run)
        pending_row: dict[str, Any] | None = None
        pending_document: dict[str, Any] | None = None
        if self._pending_publication is not None:
            pending_row, pending_document = self._pending_publication
            if row.get("publication_id") != pending_row.get("publication_id"):
                raise WNBAStep7GTransactionalCommitError(
                    "Step 7G scheduler run does not reference the pending publication."
                )

        response = self.store.backend._request(
            "POST",
            f"rpc/{ATOMIC_COMMIT_RPC}",
            json_body={
                "p_publication_row": pending_row,
                "p_publication_document": pending_document,
                "p_run_row": row,
                "p_run_document": dict(run),
            },
            operation="Step 7G atomic publication/run commit",
        )
        try:
            result = response.json()
        except ValueError as exc:
            raise WNBAStep7GTransactionalCommitError(
                "Step 7G atomic commit returned invalid JSON."
            ) from exc
        if not isinstance(result, dict) or result.get("run_id") != row["run_id"]:
            raise WNBAStep7GTransactionalCommitError(
                "Step 7G atomic commit acknowledgement is malformed."
            )
        self._pending_publication = None
        return {
            "stored": bool(result.get("run_inserted")),
            "idempotent_replay": not bool(result.get("run_inserted")),
            "run_id": row["run_id"],
            "publication_inserted": bool(result.get("publication_inserted")),
            "publication_id": result.get("publication_id"),
            "storage_backend": SUPABASE_BACKEND,
            "atomic_commit": True,
        }

    def assert_clean(self) -> None:
        if self._pending_publication is not None:
            raise WNBAStep7GTransactionalCommitError(
                "Step 7G cycle ended with an uncommitted publication."
            )
