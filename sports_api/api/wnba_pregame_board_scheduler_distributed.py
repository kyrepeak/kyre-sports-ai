"""FastAPI transport for WNBA Step 5Q multi-worker scheduler safety.

This layer wraps the frozen Step-5P scheduler with a dedicated SQLite
cross-process mutex.  It does not change collection cadence, model inputs,
Monte Carlo behavior, ranking, publication contents, or archive semantics.
"""
from __future__ import annotations

from datetime import datetime, timezone
import os
import socket
import threading
from typing import Any, Callable
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query

from sports_api.database.wnba_current_board_store import (
    MAX_PUBLICATION_LIMIT,
    MAX_RUN_LIMIT,
    WNBACurrentBoardStoreConflictError,
    WNBACurrentBoardStoreError,
    WNBACurrentBoardStoreNotReadyError,
    list_publications,
    list_scheduler_runs,
)
from sports_api.database.wnba_scheduler_cycle_lock import (
    WNBASchedulerCycleLockConfigurationError,
    WNBASchedulerCycleLockError,
    WNBASchedulerCycleLockHandle,
    get_cycle_lock_status,
    list_lock_history,
    release_cycle_lock,
    try_acquire_cycle_lock,
)
from sports_api.wnba_league import CURRENT_SUPPORTED_SEASON
from sports_api.wnba_pregame_board_scheduler import (
    WNBAPregameBoardSchedulerModelInputError,
    WNBAPregameBoardSchedulerNotReadyError,
    WNBAPregameBoardSchedulerStoreError,
    WNBAPregameBoardSchedulerUpstreamError,
    get_current_published_board,
    get_scheduler_configuration,
    get_scheduler_status,
    run_pregame_board_cycle,
)

MODEL_SOURCE = "Kyre Sports API WNBA Step 5Q multi-worker scheduler transport"
MODEL_VERSION = "wnba_step_5q_multi_worker_scheduler_transport_v1"
INSTANCE_ID_ENV = "WNBA_BOARD_SCHEDULER_INSTANCE_ID"

router = APIRouter(prefix="/api/v1/wnba", tags=["wnba"])

_worker_lock = threading.Lock()
_cycle_lock = threading.Lock()
_worker_stop = threading.Event()
_worker_thread: threading.Thread | None = None


def _build_instance_owner_id() -> str:
    explicit = str(os.environ.get(INSTANCE_ID_ENV) or "").strip()
    if explicit:
        return explicit[:240]
    return f"{socket.gethostname()}:{os.getpid()}:{uuid4().hex[:12]}"


_instance_owner_id = _build_instance_owner_id()
_worker_state: dict[str, Any] = {
    "thread_running": False,
    "instance_owner_id": _instance_owner_id,
    "cross_process_lock_enabled": True,
    "last_cycle_started_at_utc": None,
    "last_cycle_completed_at_utc": None,
    "last_cycle_outcome": None,
    "last_publication_id": None,
    "last_error": None,
    "last_cross_process_lock_acquired": None,
    "last_cross_process_lock_contention_at_utc": None,
    "last_cross_process_lock_event_id": None,
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _provider_ids(value: str | None) -> list[str] | None:
    if value is None:
        return None
    items = [item.strip() for item in value.split(",") if item.strip()]
    if not items:
        raise WNBAPregameBoardSchedulerModelInputError(
            "WNBA Step 5Q provider_ids must contain at least one comma-separated provider id."
        )
    return items


def _raise_api_error(exc: Exception) -> None:
    if isinstance(exc, (ValueError, WNBAPregameBoardSchedulerModelInputError)):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if isinstance(
        exc,
        (
            WNBAPregameBoardSchedulerNotReadyError,
            WNBACurrentBoardStoreNotReadyError,
            WNBACurrentBoardStoreConflictError,
        ),
    ):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(exc, WNBAPregameBoardSchedulerUpstreamError):
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if isinstance(
        exc,
        (
            WNBAPregameBoardSchedulerStoreError,
            WNBACurrentBoardStoreError,
            WNBASchedulerCycleLockError,
            WNBASchedulerCycleLockConfigurationError,
        ),
    ):
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    raise exc


def _try_distributed_lock() -> WNBASchedulerCycleLockHandle | None:
    return try_acquire_cycle_lock(_instance_owner_id)


def _release_distributed_lock(
    handle: WNBASchedulerCycleLockHandle,
    *,
    result: dict[str, Any] | None = None,
    error: Exception | None = None,
) -> dict[str, Any] | None:
    if error is not None:
        outcome = "cycle_error"
        detail = {"error_type": type(error).__name__, "detail": str(error)}
    else:
        outcome = str((result or {}).get("outcome") or "cycle_completed")
        publication = (result or {}).get("publication") or (result or {}).get("current_publication") or {}
        detail = {
            "cycle_outcome": outcome,
            "publication_id": publication.get("publication_id"),
        }
    try:
        event = release_cycle_lock(handle, outcome=outcome, detail=detail)
    except Exception:
        if error is not None:
            # Preserve the model/provider/store exception that caused the cycle
            # to fail. Closing the SQLite connection in release_cycle_lock's
            # finally block still relinquishes the OS lock.
            return None
        raise
    with _worker_lock:
        _worker_state["last_cross_process_lock_event_id"] = event.get("event_id")
    return event


def _run_cycle_with_distributed_lock(
    call: Callable[[], dict[str, Any]],
    *,
    contention_is_error: bool,
) -> dict[str, Any]:
    handle = _try_distributed_lock()
    if handle is None:
        with _worker_lock:
            _worker_state["last_cross_process_lock_acquired"] = False
            _worker_state["last_cross_process_lock_contention_at_utc"] = _utc_now_iso()
            _worker_state["last_error"] = None
        if contention_is_error:
            raise WNBAPregameBoardSchedulerNotReadyError(
                "WNBA Step 5Q scheduler cycle is already owned by another FastAPI worker process."
            )
        return {
            "source": MODEL_SOURCE,
            "data_type": "wnba_step_5q_scheduler_cycle",
            "model_version": MODEL_VERSION,
            "outcome": "skipped_cross_process_lock",
            "provider_collection_attempted": False,
            "board_rebuild_attempted": False,
            "instance_owner_id": _instance_owner_id,
        }

    with _worker_lock:
        _worker_state["last_cross_process_lock_acquired"] = True
    try:
        result = call()
    except Exception as exc:
        _release_distributed_lock(handle, error=exc)
        raise
    _release_distributed_lock(handle, result=result)
    return result


def _run_one_background_cycle() -> dict[str, Any]:
    if not _cycle_lock.acquire(blocking=False):
        raise WNBAPregameBoardSchedulerNotReadyError(
            "WNBA Step 5Q scheduler cycle is already running in this process."
        )
    started = _utc_now_iso()
    with _worker_lock:
        _worker_state["last_cycle_started_at_utc"] = started
        _worker_state["last_error"] = None
    try:
        result = _run_cycle_with_distributed_lock(
            lambda: run_pregame_board_cycle(),
            contention_is_error=False,
        )
        with _worker_lock:
            _worker_state["last_cycle_outcome"] = result.get("outcome")
            publication = result.get("publication") or result.get("current_publication") or {}
            _worker_state["last_publication_id"] = publication.get("publication_id")
        return result
    except Exception as exc:
        with _worker_lock:
            _worker_state["last_error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        with _worker_lock:
            _worker_state["last_cycle_completed_at_utc"] = _utc_now_iso()
        _cycle_lock.release()


def _worker_loop(loop_seconds: int) -> None:
    with _worker_lock:
        _worker_state["thread_running"] = True
    try:
        while not _worker_stop.is_set():
            try:
                _run_one_background_cycle()
            except Exception:
                # Expected provider/schedule/model/store failures are surfaced
                # through status. One transient failure must not kill the worker.
                pass
            if _worker_stop.wait(loop_seconds):
                break
    finally:
        with _worker_lock:
            _worker_state["thread_running"] = False


def _start_worker() -> None:
    global _worker_thread
    config = get_scheduler_configuration()
    if not config["enabled"]:
        return
    with _worker_lock:
        if _worker_thread is not None and _worker_thread.is_alive():
            return
        _worker_stop.clear()
        _worker_thread = threading.Thread(
            target=_worker_loop,
            args=(config["loop_seconds"],),
            name="wnba-step-5q-board-scheduler",
            daemon=True,
        )
        _worker_thread.start()


def _stop_worker() -> None:
    global _worker_thread
    _worker_stop.set()
    thread = _worker_thread
    if thread is not None and thread.is_alive():
        thread.join(timeout=2.0)
    _worker_thread = None


@router.on_event("startup")
def start_wnba_step_5q_scheduler() -> None:
    _start_worker()


@router.on_event("shutdown")
def stop_wnba_step_5q_scheduler() -> None:
    _stop_worker()


@router.get("/rankings/player-props/current")
def get_current_wnba_player_prop_board(
    date: str | None = Query(default=None, description="Arizona slate date YYYY-MM-DD; defaults to today."),
    season: int = Query(default=CURRENT_SUPPORTED_SEASON, ge=1),
    require_current: bool = Query(
        default=True,
        description="Reject an expired publication instead of serving stale pregame picks.",
    ),
):
    """Return the durable Step-5P board with zero sportsbook/model work."""
    try:
        return get_current_published_board(
            date=date,
            season=season,
            require_current=require_current,
        )
    except Exception as exc:
        _raise_api_error(exc)


@router.post("/rankings/player-props/current/refresh")
def refresh_current_wnba_player_prop_board(
    date: str | None = Query(default=None),
    season: int = Query(default=CURRENT_SUPPORTED_SEASON, ge=1),
    provider_ids: str | None = Query(
        default=None,
        description="Optional comma-separated Step-5O failover order override.",
    ),
    force: bool = Query(
        default=True,
        description="Bypass the normal next-due clock; the hard provider-spacing guard still applies.",
    ),
):
    """Run one Step-5P cycle only when this worker owns the Step-5Q mutex."""
    if not _cycle_lock.acquire(blocking=False):
        raise HTTPException(
            status_code=409,
            detail="WNBA Step 5Q scheduler cycle is already running in this process.",
        )
    try:
        try:
            return _run_cycle_with_distributed_lock(
                lambda: run_pregame_board_cycle(
                    date=date,
                    season=season,
                    provider_ids=_provider_ids(provider_ids),
                    force=force,
                ),
                contention_is_error=True,
            )
        except Exception as exc:
            _raise_api_error(exc)
    finally:
        _cycle_lock.release()


@router.get("/rankings/player-props/current/status")
def get_current_wnba_player_prop_scheduler_status(
    date: str | None = Query(default=None),
    season: int = Query(default=CURRENT_SUPPORTED_SEASON, ge=1),
):
    try:
        status = get_scheduler_status(date=date, season=season)
        with _worker_lock:
            status["background_worker"] = dict(_worker_state)
        try:
            lock_status = get_cycle_lock_status()
        except Exception as exc:
            lock_status = {
                "source": MODEL_SOURCE,
                "model_version": MODEL_VERSION,
                "ready": False,
                "error_type": type(exc).__name__,
                "detail": str(exc),
            }
        status["cross_process_cycle_lock"] = lock_status
        status["step_5q"] = {
            "source": MODEL_SOURCE,
            "model_version": MODEL_VERSION,
            "instance_owner_id": _instance_owner_id,
            "frozen_step_5p_semantics_preserved": True,
            "one_cycle_across_fastapi_worker_processes": True,
        }
        return status
    except Exception as exc:
        _raise_api_error(exc)


@router.get("/rankings/player-props/current/history")
def get_current_wnba_player_prop_publication_history(
    date: str | None = Query(default=None),
    season: int | None = Query(default=None, ge=1),
    publication_limit: int = Query(default=25, ge=1, le=MAX_PUBLICATION_LIMIT),
    run_limit: int = Query(default=50, ge=1, le=MAX_RUN_LIMIT),
):
    try:
        publications = list_publications(
            date=date,
            season=season,
            limit=publication_limit,
        )
        runs = list_scheduler_runs(
            date=date,
            season=season,
            limit=run_limit,
        )
        try:
            lock_events = list_lock_history(limit=min(run_limit, 2_000))
        except Exception as exc:
            lock_events = [{"unavailable": True, "error_type": type(exc).__name__, "detail": str(exc)}]
        return {
            "source": "Kyre Sports API WNBA Step 5Q publication + scheduler history",
            "publication_count": len(publications),
            "scheduler_run_count": len(runs),
            "cross_process_lock_event_count": len(lock_events),
            "publications": publications,
            "scheduler_runs": runs,
            "cross_process_lock_events": lock_events,
        }
    except Exception as exc:
        _raise_api_error(exc)
