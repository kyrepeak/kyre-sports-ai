"""FastAPI transport for WNBA Step 5J durable prediction storage."""
from __future__ import annotations

from datetime import datetime, timezone
import os
import threading
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from sports_api.database.wnba_pregame_prediction_store import (
    MAX_OBSERVATION_LIMIT,
    MAX_SWEEP_LIMIT,
    STORE_PATH_ENV,
    WNBAPregameStoreConflictError,
    WNBAPregameStoreError,
    WNBAPregameStoreNotReadyError,
    archive_and_persist_prediction,
    evaluate_stored_calibration,
    get_store_status,
    get_stored_observations,
    grade_pending_archives,
    initialize_store,
)
from sports_api.wnba_historical_backtest_calibration import (
    ARCHIVE_SIGNING_ENV,
    WNBAHistoricalBacktestModelInputError,
    WNBAHistoricalBacktestNotFoundError,
    WNBAHistoricalBacktestNotReadyError,
    WNBAHistoricalBacktestUpstreamError,
)

router = APIRouter(prefix="/api/v1/wnba", tags=["wnba"])

AUTOGRADE_ENABLED_ENV = "WNBA_BACKTEST_AUTOGRADE_ENABLED"
AUTOGRADE_INTERVAL_ENV = "WNBA_BACKTEST_AUTOGRADE_INTERVAL_SECONDS"
AUTOGRADE_BATCH_ENV = "WNBA_BACKTEST_AUTOGRADE_BATCH_LIMIT"
DEFAULT_AUTOGRADE_INTERVAL_SECONDS = 300
DEFAULT_AUTOGRADE_BATCH_LIMIT = 100
MIN_AUTOGRADE_INTERVAL_SECONDS = 60
MAX_AUTOGRADE_INTERVAL_SECONDS = 86_400


class DurablePregameArchiveInput(BaseModel):
    threshold: dict[str, Any]
    snapshot: dict[str, Any]


_worker_lock = threading.Lock()
_worker_stop = threading.Event()
_worker_thread: threading.Thread | None = None
_worker_state: dict[str, Any] = {
    "thread_running": False,
    "last_sweep_started_at_utc": None,
    "last_sweep_completed_at_utc": None,
    "last_sweep_counts": None,
    "last_error": None,
}


def _truthy_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() not in {"0", "false", "no", "off", "disabled"}


def _bounded_int_env(name: str, default: int, low: int, high: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return min(high, max(low, value))


def _autograde_config() -> dict[str, Any]:
    requested = _truthy_env(AUTOGRADE_ENABLED_ENV, True)
    secret = os.environ.get(ARCHIVE_SIGNING_ENV)
    secret_ready = bool(secret and len(secret.encode("utf-8")) >= 32)
    persistent_path_ready = bool(os.environ.get(STORE_PATH_ENV))
    enabled = requested and secret_ready and persistent_path_ready
    if enabled:
        reason = None
    elif requested and not secret_ready:
        reason = f"{ARCHIVE_SIGNING_ENV} must be configured with at least 32 bytes"
    elif requested and not persistent_path_ready:
        reason = f"{STORE_PATH_ENV} must point to a persistent SQLite path"
    else:
        reason = "disabled by environment"
    return {
        "requested": requested,
        "enabled": enabled,
        "disabled_reason": reason,
        "interval_seconds": _bounded_int_env(
            AUTOGRADE_INTERVAL_ENV,
            DEFAULT_AUTOGRADE_INTERVAL_SECONDS,
            MIN_AUTOGRADE_INTERVAL_SECONDS,
            MAX_AUTOGRADE_INTERVAL_SECONDS,
        ),
        "batch_limit": _bounded_int_env(
            AUTOGRADE_BATCH_ENV, DEFAULT_AUTOGRADE_BATCH_LIMIT, 1, MAX_SWEEP_LIMIT
        ),
        "persistent_store_path_explicitly_configured": persistent_path_ready,
    }


def _run_one_sweep() -> dict[str, Any]:
    started = datetime.now(timezone.utc).isoformat()
    with _worker_lock:
        _worker_state["last_sweep_started_at_utc"] = started
        _worker_state["last_error"] = None
    try:
        result = grade_pending_archives(limit=_autograde_config()["batch_limit"])
        with _worker_lock:
            _worker_state["last_sweep_counts"] = result.get("counts")
        return result
    except Exception as exc:
        with _worker_lock:
            _worker_state["last_error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        with _worker_lock:
            _worker_state["last_sweep_completed_at_utc"] = datetime.now(timezone.utc).isoformat()


def _worker_loop(interval_seconds: int) -> None:
    with _worker_lock:
        _worker_state["thread_running"] = True
    try:
        while not _worker_stop.is_set():
            try:
                _run_one_sweep()
            except Exception:
                # A transient upstream or store problem must not kill the worker.
                pass
            if _worker_stop.wait(interval_seconds):
                break
    finally:
        with _worker_lock:
            _worker_state["thread_running"] = False


def _start_worker() -> None:
    global _worker_thread
    initialize_store()
    config = _autograde_config()
    if not config["enabled"]:
        return
    with _worker_lock:
        if _worker_thread is not None and _worker_thread.is_alive():
            return
        _worker_stop.clear()
        _worker_thread = threading.Thread(
            target=_worker_loop,
            args=(config["interval_seconds"],),
            name="wnba-step-5j-autograder",
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
def start_wnba_backtest_autograder() -> None:
    _start_worker()


@router.on_event("shutdown")
def stop_wnba_backtest_autograder() -> None:
    _stop_worker()


def _raise_api_error(exc: Exception) -> None:
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if isinstance(exc, (WNBAPregameStoreConflictError, WNBAPregameStoreNotReadyError, WNBAHistoricalBacktestNotReadyError)):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(exc, WNBAHistoricalBacktestNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, WNBAHistoricalBacktestModelInputError):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if isinstance(exc, WNBAHistoricalBacktestUpstreamError):
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if isinstance(exc, WNBAPregameStoreError):
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    raise exc


@router.post("/backtests/player-props/archive-and-store")
def create_and_store_player_prop_archive(payload: DurablePregameArchiveInput):
    """Create a signed Step-5I envelope and persist the first logical archive."""
    try:
        return archive_and_persist_prediction(payload.threshold, payload.snapshot)
    except Exception as exc:
        _raise_api_error(exc)


@router.post("/backtests/player-props/store/grade-pending")
def run_player_prop_grading_sweep(
    limit: int = Query(default=DEFAULT_AUTOGRADE_BATCH_LIMIT, ge=1, le=MAX_SWEEP_LIMIT),
):
    """Run immediately the same official-result sweep used by the background worker."""
    try:
        return grade_pending_archives(limit=limit)
    except Exception as exc:
        _raise_api_error(exc)


@router.get("/backtests/player-props/store/status")
def get_player_prop_backtest_store_status():
    try:
        status = get_store_status()
        with _worker_lock:
            worker = dict(_worker_state)
        status["automatic_grading"] = {**_autograde_config(), **worker}
        return status
    except Exception as exc:
        _raise_api_error(exc)


@router.get("/backtests/player-props/store/observations")
def get_player_prop_stored_observations(
    probability_model_version: str | None = Query(default=None),
    stat: str | None = Query(default=None),
    limit: int = Query(default=250, ge=1, le=MAX_OBSERVATION_LIMIT),
):
    try:
        observations = get_stored_observations(
            probability_model_version=probability_model_version,
            stat=stat,
            limit=limit,
        )
        return {
            "count": len(observations),
            "probability_model_version_filter": probability_model_version,
            "stat_filter": stat,
            "observations": observations,
        }
    except Exception as exc:
        _raise_api_error(exc)


@router.get("/backtests/player-props/store/calibration")
def get_player_prop_stored_calibration(
    probability_model_version: str | None = Query(default=None),
    require_single_probability_model_version: bool = Query(default=True),
):
    try:
        return evaluate_stored_calibration(
            probability_model_version=probability_model_version,
            require_single_probability_model_version=require_single_probability_model_version,
        )
    except Exception as exc:
        _raise_api_error(exc)
