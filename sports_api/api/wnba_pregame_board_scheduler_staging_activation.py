"""FastAPI transport for WNBA Step 5W hosted-staging activation.

This replaces only the serving/orchestration transport registered in main.
Frozen Step 5P owns scheduler/model/publication semantics, Step 5Q owns the
cross-process cycle lock, and Step 5R remains the production runtime preflight.
Step 5W adds an explicit immutable staging checkpoint approval before a cycle
may reach provider collection or Monte Carlo work.
"""
from __future__ import annotations

from datetime import datetime, timezone
import threading
from typing import Any

from fastapi import APIRouter, HTTPException, Query

import sports_api.api.wnba_pregame_board_scheduler_distributed as step5q
from sports_api.wnba_league import CURRENT_SUPPORTED_SEASON
from sports_api.wnba_production_runtime_readiness import get_production_runtime_readiness
from sports_api.wnba_staging_activation_gate import (
    MODEL_SOURCE as ACTIVATION_SOURCE,
    MODEL_VERSION as ACTIVATION_MODEL_VERSION,
    WNBAStagingActivationNotReadyError,
    build_staging_activation_plan,
    get_first_live_cycle_verification,
    get_staging_activation_gate,
    require_staging_activation_ready,
)

MODEL_SOURCE = "Kyre Sports API WNBA Step 5W staging activation transport"
MODEL_VERSION = "wnba_step_5w_staging_activation_transport_v1"

router = APIRouter(prefix="/api/v1/wnba", tags=["wnba"])

_worker_lock = threading.Lock()
_worker_stop = threading.Event()
_worker_thread: threading.Thread | None = None
_worker_state: dict[str, Any] = {
    "thread_running": False,
    "startup_evaluated_at_utc": None,
    "startup_activation_requested": False,
    "startup_live_cycle_allowed": False,
    "startup_phase": None,
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
    with _worker_lock:
        _worker_state.update(values)


def _worker_loop(loop_seconds: int) -> None:
    _set_state(thread_running=True)
    try:
        while not _worker_stop.is_set():
            started = _utc_now_iso()
            _set_state(
                last_gate_evaluated_at_utc=started,
                last_cycle_started_at_utc=started,
                last_error=None,
            )
            try:
                require_staging_activation_ready()
                _set_state(last_gate_passed=True)
                result = step5q._run_one_background_cycle()
                _set_state(last_cycle_outcome=result.get("outcome"))
            except WNBAStagingActivationNotReadyError as exc:
                _set_state(
                    last_gate_passed=False,
                    last_cycle_outcome="blocked_by_step_5w_activation_gate",
                    last_error=f"{type(exc).__name__}: {exc}",
                )
            except Exception as exc:
                _set_state(last_error=f"{type(exc).__name__}: {exc}")
            finally:
                _set_state(last_cycle_completed_at_utc=_utc_now_iso())
            if _worker_stop.wait(loop_seconds):
                break
    finally:
        _set_state(thread_running=False)


def _start_worker() -> None:
    global _worker_thread
    gate = get_staging_activation_gate()
    activation_requested = gate.get("activation_requested") is True
    _set_state(
        startup_evaluated_at_utc=_utc_now_iso(),
        startup_activation_requested=activation_requested,
        startup_live_cycle_allowed=gate.get("live_cycle_allowed") is True,
        startup_phase=gate.get("phase"),
        startup_blocking_reasons=list(gate.get("blocking_reasons") or []),
    )
    if not activation_requested:
        return
    try:
        config = step5q.get_scheduler_configuration()
        loop_seconds = int(config.get("loop_seconds") or 30)
    except Exception:
        loop_seconds = 30
    with _worker_lock:
        if _worker_thread is not None and _worker_thread.is_alive():
            return
        _worker_stop.clear()
        _worker_thread = threading.Thread(
            target=_worker_loop,
            args=(loop_seconds,),
            name="wnba-step-5w-staging-activation",
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
def start_wnba_step_5w_runtime() -> None:
    _start_worker()


@router.on_event("shutdown")
def stop_wnba_step_5w_runtime() -> None:
    _stop_worker()


@router.get("/rankings/player-props/current")
def get_current_wnba_player_prop_board(
    date: str | None = Query(default=None, description="Arizona slate date YYYY-MM-DD; defaults to today."),
    season: int = Query(default=CURRENT_SUPPORTED_SEASON, ge=1),
    require_current: bool = Query(default=True, description="Reject an expired publication instead of serving stale pregame picks."),
):
    return step5q.get_current_wnba_player_prop_board(date=date, season=season, require_current=require_current)


@router.post("/rankings/player-props/current/refresh")
def refresh_current_wnba_player_prop_board(
    date: str | None = Query(default=None),
    season: int = Query(default=CURRENT_SUPPORTED_SEASON, ge=1),
    provider_ids: str | None = Query(default=None, description="Optional comma-separated frozen Step-5O failover order override."),
    force: bool = Query(default=True, description="Bypass normal next-due clock; frozen provider-spacing guard still applies."),
):
    try:
        require_staging_activation_ready()
    except WNBAStagingActivationNotReadyError as exc:
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
    status = step5q.get_current_wnba_player_prop_scheduler_status(date=date, season=season)
    step5r = get_production_runtime_readiness()
    step5w = get_staging_activation_gate()
    with _worker_lock:
        worker = dict(_worker_state)
    status["production_runtime"] = {
        "source": MODEL_SOURCE,
        "model_version": MODEL_VERSION,
        "step_5r": step5r,
        "step_5w": step5w,
        "worker": worker,
        "semantics": {
            "read_path_remains_network_free": True,
            "scheduler_cycle_requires_step_5w_gate": True,
            "step_5r_preflight_remains_required": True,
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
    report = get_production_runtime_readiness()
    report["step_5w_activation_gate"] = get_staging_activation_gate()
    with _worker_lock:
        report["runtime_worker"] = dict(_worker_state)
    return report


@router.get("/runtime/health")
def get_wnba_production_runtime_health():
    gate = get_staging_activation_gate()
    if gate.get("live_cycle_allowed") is not True:
        raise HTTPException(
            status_code=503,
            detail={
                "source": MODEL_SOURCE,
                "model_version": MODEL_VERSION,
                "live_cycle_allowed": False,
                "phase": gate.get("phase"),
                "activation_requested": gate.get("activation_requested"),
                "activation_checkpoint_sha256": gate.get("activation_checkpoint_sha256"),
                "blocking_reasons": gate.get("blocking_reasons"),
            },
        )
    return {
        "source": MODEL_SOURCE,
        "model_version": MODEL_VERSION,
        "status": "ready",
        "live_cycle_allowed": True,
        "activation_checkpoint_sha256": gate.get("activation_checkpoint_sha256"),
        "activated_at_utc": gate.get("activated_at_utc"),
        "step_5r_scheduler_allowed": (gate.get("step_5r") or {}).get("scheduler_allowed"),
    }


@router.get("/runtime/activation-gate")
def get_wnba_staging_activation_gate():
    return get_staging_activation_gate()


@router.get("/runtime/activation-plan")
def get_wnba_staging_activation_plan():
    return build_staging_activation_plan()


@router.get("/runtime/first-live-cycle")
def get_wnba_first_live_cycle_verification(
    date: str | None = Query(default=None),
    season: int | None = Query(default=None, ge=1),
):
    return get_first_live_cycle_verification(date=date, season=season)
