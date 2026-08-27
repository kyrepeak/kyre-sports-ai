"""FastAPI transport for WNBA hosted-staging activation with Step 6K interlock.

Frozen Step 5P owns scheduler/model/publication semantics, Step 5Q owns the
cross-process cycle lock, Step 5R remains the production runtime preflight, and
Step 5W remains the explicit immutable activation approval. Step 6K adds the
mandatory completed Step 6J durable-canary proof before a worker thread may
start or any manual/background cycle may reach provider collection or Monte
Carlo work.
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
    build_staging_activation_plan,
    get_first_live_cycle_verification,
    get_staging_activation_gate,
)
from sports_api.wnba_step6k_activation_preflight import (
    WNBAStep6KActivationNotReadyError,
    get_step6k_activation_preflight,
    require_step6k_scheduler_authorized,
)

MODEL_SOURCE = "Kyre Sports API WNBA Step 6K-interlocked staging activation transport"
MODEL_VERSION = "wnba_step_6k_interlocked_staging_activation_transport_v1"

router = APIRouter(prefix="/api/v1/wnba", tags=["wnba"])

_worker_lock = threading.Lock()
_worker_stop = threading.Event()
_worker_thread: threading.Thread | None = None
_worker_state: dict[str, Any] = {
    "thread_running": False,
    "startup_evaluated_at_utc": None,
    "startup_activation_requested": False,
    "startup_live_cycle_allowed": False,
    "startup_step6k_scheduler_authorized": False,
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
            _set_state(last_gate_evaluated_at_utc=started, last_cycle_started_at_utc=started, last_error=None)
            try:
                require_step6k_scheduler_authorized()
                _set_state(last_gate_passed=True)
                result = step5q._run_one_background_cycle()
                _set_state(last_cycle_outcome=result.get("outcome"))
            except WNBAStep6KActivationNotReadyError as exc:
                _set_state(
                    last_gate_passed=False,
                    last_cycle_outcome="blocked_by_step_6k_post_canary_gate",
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
    step6k = get_step6k_activation_preflight()
    activation_requested = step6k.get("activation_requested") is True
    scheduler_authorized = step6k.get("scheduler_authorized") is True
    _set_state(
        startup_evaluated_at_utc=_utc_now_iso(),
        startup_activation_requested=activation_requested,
        startup_live_cycle_allowed=(step6k.get("step_5w") or {}).get("live_cycle_allowed") is True,
        startup_step6k_scheduler_authorized=scheduler_authorized,
        startup_phase=step6k.get("phase"),
        startup_blocking_reasons=list(step6k.get("blocking_reasons") or []),
    )
    # Hard Step 6K boundary: even an old Step 5W activation request cannot
    # create a worker thread until the completed Step 6J durable canary is
    # verified and Step 5W itself permits live cycles.
    if not scheduler_authorized:
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
            name="wnba-step-6k-post-canary-activation",
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
def start_wnba_step_6k_runtime() -> None:
    _start_worker()


@router.on_event("shutdown")
def stop_wnba_step_6k_runtime() -> None:
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
        require_step6k_scheduler_authorized()
    except WNBAStep6KActivationNotReadyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return step5q.refresh_current_wnba_player_prop_board(date=date, season=season, provider_ids=provider_ids, force=force)


@router.get("/rankings/player-props/current/status")
def get_current_wnba_player_prop_scheduler_status(
    date: str | None = Query(default=None),
    season: int = Query(default=CURRENT_SUPPORTED_SEASON, ge=1),
):
    status = step5q.get_current_wnba_player_prop_scheduler_status(date=date, season=season)
    step5r = get_production_runtime_readiness()
    step5w = get_staging_activation_gate()
    step6k = get_step6k_activation_preflight()
    with _worker_lock:
        worker = dict(_worker_state)
    status["production_runtime"] = {
        "source": MODEL_SOURCE,
        "model_version": MODEL_VERSION,
        "step_5r": step5r,
        "step_5w": step5w,
        "step_6k": step6k,
        "worker": worker,
        "semantics": {
            "read_path_remains_network_free": True,
            "scheduler_cycle_requires_step_6k_gate": True,
            "step_6j_durable_canary_required": True,
            "step_5w_explicit_activation_remains_required": True,
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
    report["step_6k_post_canary_gate"] = get_step6k_activation_preflight()
    with _worker_lock:
        report["runtime_worker"] = dict(_worker_state)
    return report


@router.get("/runtime/health")
def get_wnba_production_runtime_health():
    step6k = get_step6k_activation_preflight()
    if step6k.get("scheduler_authorized") is not True:
        raise HTTPException(
            status_code=503,
            detail={
                "source": MODEL_SOURCE,
                "model_version": MODEL_VERSION,
                "scheduler_authorized": False,
                "phase": step6k.get("phase"),
                "activation_requested": step6k.get("activation_requested"),
                "activation_checkpoint_sha256": step6k.get("activation_checkpoint_sha256"),
                "blocking_reasons": step6k.get("blocking_reasons"),
            },
        )
    return {
        "source": MODEL_SOURCE,
        "model_version": MODEL_VERSION,
        "status": "ready",
        "scheduler_authorized": True,
        "step_6k_activation_checkpoint_sha256": step6k.get("activation_checkpoint_sha256"),
        "step_6j_verified": step6k.get("step6j_verified"),
        "step_5w_activation_checkpoint_sha256": (step6k.get("step_5w") or {}).get("activation_checkpoint_sha256"),
    }


@router.get("/runtime/activation-gate")
def get_wnba_staging_activation_gate():
    return get_staging_activation_gate()


@router.get("/runtime/staging-activation-plan")
def get_wnba_staging_activation_plan():
    return build_staging_activation_plan()


@router.get("/runtime/first-live-cycle")
def get_wnba_first_live_cycle_verification(
    date: str | None = Query(default=None),
    season: int | None = Query(default=None, ge=1),
):
    return get_first_live_cycle_verification(date=date, season=season)
