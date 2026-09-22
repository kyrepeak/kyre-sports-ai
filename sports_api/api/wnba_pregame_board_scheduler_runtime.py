"""FastAPI transport for WNBA Step 5R production runtime activation.

This router replaces only the serving/orchestration transport registered in
``sports_api.main``.  Frozen Step 5P still owns scheduling/model/publication
semantics and frozen Step 5Q still owns local + cross-process cycle locking.
Step 5R adds a fail-closed production preflight before any scheduler cycle can
reach sportsbook collection or Monte Carlo work.
"""
from __future__ import annotations

from datetime import datetime, timezone
import threading
from typing import Any

from fastapi import APIRouter, HTTPException, Query

import sports_api.api.wnba_pregame_board_scheduler_distributed as step5q
from sports_api.wnba_league import CURRENT_SUPPORTED_SEASON
from sports_api.wnba_production_runtime_readiness import (
    MODEL_SOURCE as READINESS_SOURCE,
    MODEL_VERSION as READINESS_MODEL_VERSION,
    WNBAProductionRuntimeNotReadyError,
    get_production_runtime_readiness,
    require_production_runtime_ready,
)

MODEL_SOURCE = "Kyre Sports API WNBA Step 5R production runtime transport"
MODEL_VERSION = "wnba_step_5r_production_runtime_transport_v1"

router = APIRouter(prefix="/api/v1/wnba", tags=["wnba"])

_runtime_worker_lock = threading.Lock()
_runtime_worker_stop = threading.Event()
_runtime_worker_thread: threading.Thread | None = None
_runtime_worker_state: dict[str, Any] = {
    "thread_running": False,
    "startup_evaluated_at_utc": None,
    "startup_activation_requested": False,
    "startup_scheduler_allowed": False,
    "startup_preflight_ready": False,
    "startup_blocking_reasons": [],
    "last_gate_evaluated_at_utc": None,
    "last_gate_passed": None,
    "last_cycle_started_at_utc": None,
    "last_cycle_completed_at_utc": None,
    "last_cycle_outcome": None,
    "last_error": None,
}


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _set_state(**values: Any) -> None:
    with _runtime_worker_lock:
        _runtime_worker_state.update(values)


def _runtime_worker_loop(loop_seconds: int) -> None:
    _set_state(thread_running=True)
    try:
        while not _runtime_worker_stop.is_set():
            started = _utc_now_iso()
            _set_state(
                last_gate_evaluated_at_utc=started,
                last_cycle_started_at_utc=started,
                last_error=None,
            )
            try:
                require_production_runtime_ready()
                _set_state(last_gate_passed=True)
                result = step5q._run_one_background_cycle()
                _set_state(last_cycle_outcome=result.get("outcome"))
            except WNBAProductionRuntimeNotReadyError as exc:
                _set_state(
                    last_gate_passed=False,
                    last_cycle_outcome="blocked_by_step_5r_runtime_gate",
                    last_error=f"{type(exc).__name__}: {exc}",
                )
            except Exception as exc:
                # Step 5Q already records provider/model/store cycle failures.
                # The Step 5R supervisor stays alive so transient failures do
                # not remove restart/failover protection from the process.
                _set_state(last_error=f"{type(exc).__name__}: {exc}")
            finally:
                _set_state(last_cycle_completed_at_utc=_utc_now_iso())
            if _runtime_worker_stop.wait(loop_seconds):
                break
    finally:
        _set_state(thread_running=False)


def _start_runtime_worker() -> None:
    """Start a fail-closed supervisor in every activated FastAPI worker.

    A worker does not need a green preflight at its exact startup instant to
    run the supervisor. This matters in multi-worker deployments because
    another process may briefly own the Step-5Q lock while this worker boots.
    The supervisor keeps rechecking the Step-5R gate and never delegates a
    cycle until the gate is green.
    """
    global _runtime_worker_thread
    report = get_production_runtime_readiness()
    activation_requested = report.get("activation_requested") is True
    _set_state(
        startup_evaluated_at_utc=_utc_now_iso(),
        startup_activation_requested=activation_requested,
        startup_scheduler_allowed=report.get("scheduler_allowed") is True,
        startup_preflight_ready=report.get("preflight_ready") is True,
        startup_blocking_reasons=list(report.get("blocking_reasons") or []),
    )
    if not activation_requested:
        return
    try:
        config = step5q.get_scheduler_configuration()
        loop_seconds = int(config.get("loop_seconds") or 30)
    except Exception:
        loop_seconds = 30
    with _runtime_worker_lock:
        if _runtime_worker_thread is not None and _runtime_worker_thread.is_alive():
            return
        _runtime_worker_stop.clear()
        _runtime_worker_thread = threading.Thread(
            target=_runtime_worker_loop,
            args=(loop_seconds,),
            name="wnba-step-5r-production-runtime",
            daemon=True,
        )
        _runtime_worker_thread.start()


def _stop_runtime_worker() -> None:
    global _runtime_worker_thread
    _runtime_worker_stop.set()
    thread = _runtime_worker_thread
    if thread is not None and thread.is_alive():
        thread.join(timeout=2.0)
    _runtime_worker_thread = None


@router.on_event("startup")
def start_wnba_step_5r_runtime() -> None:
    _start_runtime_worker()


@router.on_event("shutdown")
def stop_wnba_step_5r_runtime() -> None:
    _stop_runtime_worker()


@router.get("/rankings/player-props/current")
def get_current_wnba_player_prop_board(
    date: str | None = Query(default=None, description="Arizona slate date YYYY-MM-DD; defaults to today."),
    season: int = Query(default=CURRENT_SUPPORTED_SEASON, ge=1),
    require_current: bool = Query(
        default=True,
        description="Reject an expired publication instead of serving stale pregame picks.",
    ),
):
    """Read the durable Step-5P board even when production writes are gated."""
    return step5q.get_current_wnba_player_prop_board(
        date=date,
        season=season,
        require_current=require_current,
    )


@router.post("/rankings/player-props/current/refresh")
def refresh_current_wnba_player_prop_board(
    date: str | None = Query(default=None),
    season: int = Query(default=CURRENT_SUPPORTED_SEASON, ge=1),
    provider_ids: str | None = Query(
        default=None,
        description="Optional comma-separated frozen Step-5O failover order override.",
    ),
    force: bool = Query(
        default=True,
        description="Bypass the normal next-due clock; frozen provider-spacing guard still applies.",
    ),
):
    """Require Step 5R readiness before delegating the cycle to frozen Step 5Q."""
    try:
        require_production_runtime_ready()
    except WNBAProductionRuntimeNotReadyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return step5q.refresh_current_wnba_player_prop_board(
        date=date,
        season=season,
        provider_ids=provider_ids,
        force=force,
    )


@router.get("/rankings/player-props/current/status")
def get_current_wnba_player_prop_scheduler_status(
    date: str | None = Query(default=None),
    season: int = Query(default=CURRENT_SUPPORTED_SEASON, ge=1),
):
    status = step5q.get_current_wnba_player_prop_scheduler_status(
        date=date,
        season=season,
    )
    readiness = get_production_runtime_readiness()
    with _runtime_worker_lock:
        worker = dict(_runtime_worker_state)
    status["production_runtime"] = {
        "source": MODEL_SOURCE,
        "model_version": MODEL_VERSION,
        "readiness_source": READINESS_SOURCE,
        "readiness_model_version": READINESS_MODEL_VERSION,
        "readiness": readiness,
        "worker": worker,
        "semantics": {
            "read_path_remains_network_free": True,
            "scheduler_cycle_requires_step_5r_gate": True,
            "step_5q_locking_remains_authoritative": True,
            "activated_workers_keep_a_fail_closed_supervisor_for_takeover": True,
        },
    }
    return status


@router.get("/rankings/player-props/current/history")
def get_current_wnba_player_prop_publication_history(
    date: str | None = Query(default=None),
    season: int | None = Query(default=None, ge=1),
    publication_limit: int = Query(default=25, ge=1, le=2_000),
    run_limit: int = Query(default=50, ge=1, le=5_000),
):
    return step5q.get_current_wnba_player_prop_publication_history(
        date=date,
        season=season,
        publication_limit=publication_limit,
        run_limit=run_limit,
    )


@router.get("/runtime/readiness")
def get_wnba_production_runtime_readiness():
    """Return the sanitized network-free Step 5R preflight report."""
    report = get_production_runtime_readiness()
    with _runtime_worker_lock:
        report["runtime_worker"] = dict(_runtime_worker_state)
    return report


@router.get("/runtime/health")
def get_wnba_production_runtime_health():
    """Production scheduler health probe: 200 only when cycles are allowed."""
    report = get_production_runtime_readiness()
    if report.get("scheduler_allowed") is not True:
        raise HTTPException(
            status_code=503,
            detail={
                "source": MODEL_SOURCE,
                "model_version": MODEL_VERSION,
                "scheduler_allowed": False,
                "activation_requested": report.get("activation_requested"),
                "preflight_ready": report.get("preflight_ready"),
                "activation_reason": report.get("activation_reason"),
                "blocking_reasons": report.get("blocking_reasons"),
            },
        )
    return {
        "source": MODEL_SOURCE,
        "model_version": MODEL_VERSION,
        "status": "ready",
        "scheduler_allowed": True,
        "configuration_fingerprint_sha256": report.get("configuration_fingerprint_sha256"),
        "restart_recovery": report.get("restart_recovery"),
    }
