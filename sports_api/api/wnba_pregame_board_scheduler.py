"""FastAPI transport and background worker for WNBA Step 5P."""
from __future__ import annotations

from datetime import datetime, timezone
import threading
from typing import Any

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

router = APIRouter(prefix="/api/v1/wnba", tags=["wnba"])

_worker_lock = threading.Lock()
_cycle_lock = threading.Lock()
_worker_stop = threading.Event()
_worker_thread: threading.Thread | None = None
_worker_state: dict[str, Any] = {
    "thread_running": False,
    "last_cycle_started_at_utc": None,
    "last_cycle_completed_at_utc": None,
    "last_cycle_outcome": None,
    "last_publication_id": None,
    "last_error": None,
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _provider_ids(value: str | None) -> list[str] | None:
    if value is None:
        return None
    items = [item.strip() for item in value.split(",") if item.strip()]
    if not items:
        raise WNBAPregameBoardSchedulerModelInputError(
            "WNBA Step 5P provider_ids must contain at least one comma-separated provider id."
        )
    return items


def _raise_api_error(exc: Exception) -> None:
    if isinstance(
        exc,
        (
            ValueError,
            WNBAPregameBoardSchedulerModelInputError,
        ),
    ):
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
        ),
    ):
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    raise exc


def _run_one_background_cycle() -> dict[str, Any]:
    if not _cycle_lock.acquire(blocking=False):
        raise WNBAPregameBoardSchedulerNotReadyError(
            "WNBA Step 5P scheduler cycle is already running in this process."
        )
    started = _utc_now_iso()
    with _worker_lock:
        _worker_state["last_cycle_started_at_utc"] = started
        _worker_state["last_error"] = None
    try:
        result = run_pregame_board_cycle()
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
                # Provider, schedule, model, and store outages are reported in status;
                # one transient failure must never kill the scheduling thread.
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
            name="wnba-step-5p-board-scheduler",
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
def start_wnba_step_5p_scheduler() -> None:
    _start_worker()


@router.on_event("shutdown")
def stop_wnba_step_5p_scheduler() -> None:
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
    """Return the last durable current board without any network/model work."""
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
    """Run one synchronous Step-5P cycle using the same logic as the background worker."""
    if not _cycle_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="WNBA Step 5P scheduler cycle is already running in this process.")
    try:
        try:
            return run_pregame_board_cycle(
                date=date,
                season=season,
                provider_ids=_provider_ids(provider_ids),
                force=force,
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
        return {
            "source": "Kyre Sports API WNBA Step 5P history",
            "publication_count": len(publications),
            "scheduler_run_count": len(runs),
            "publications": publications,
            "scheduler_runs": runs,
        }
    except Exception as exc:
        _raise_api_error(exc)
