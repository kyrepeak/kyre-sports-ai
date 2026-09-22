"""FastAPI transport for WNBA production activation through Step 6M.

Frozen Step 5P owns scheduler/model/publication semantics, Step 5Q owns local
and cross-process cycle locking, Step 5R remains the production runtime
preflight, Step 5W remains the explicit immutable activation approval, Step 6K
requires the completed durable Step 6J canary, Step 6L owns guarded direct-feed
refresh authority, and Step 6M places that refresh inside Step 5Q distributed
ownership immediately before the frozen Step 5P model cycle.
"""
from __future__ import annotations

from datetime import datetime, timezone
import threading
from typing import Any

from fastapi import APIRouter, HTTPException, Query

import sports_api.api.wnba_pregame_board_scheduler_distributed as step5q
import sports_api.wnba_step6m_scheduler_orchestration as step6m
from sports_api.wnba_league import CURRENT_SUPPORTED_SEASON
from sports_api.wnba_production_runtime_readiness import get_production_runtime_readiness
from sports_api.wnba_staging_activation_gate import (
    WNBAStagingActivationNotReadyError,
    build_staging_activation_plan,
    get_first_live_cycle_verification,
    get_staging_activation_gate,
)
from sports_api.wnba_step6k_activation_preflight import (
    WNBAStep6KActivationNotReadyError,
    get_step6k_activation_preflight,
    require_step6k_scheduler_authorized,
)

MODEL_SOURCE = "Kyre Sports API WNBA Step 6M-interlocked production scheduler transport"
MODEL_VERSION = "wnba_step_6m_interlocked_production_scheduler_transport_v1"

router = APIRouter(prefix="/api/v1/wnba", tags=["wnba"])

# Backward-compatible transport symbol only. Existing Step 5W callers/tests may
# still patch this name, but its default authority remains the stronger Step 6K
# gate. Step 6M adds another fail-closed readiness check before any cycle work.
require_staging_activation_ready = require_step6k_scheduler_authorized

_worker_lock = threading.Lock()
_worker_stop = threading.Event()
_worker_thread: threading.Thread | None = None
_worker_state: dict[str, Any] = {
    "thread_running": False,
    "startup_evaluated_at_utc": None,
    "startup_activation_requested": False,
    "startup_live_cycle_allowed": False,
    "startup_step6k_scheduler_authorized": False,
    "startup_step6m_scheduler_cycle_ready": False,
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
                require_staging_activation_ready()
                step6m.require_step6m_scheduler_ready()
                _set_state(last_gate_passed=True)
                result = step6m.run_step6m_background_cycle()
                _set_state(last_cycle_outcome=result.get("outcome"))
            except (
                WNBAStep6KActivationNotReadyError,
                WNBAStagingActivationNotReadyError,
                step6m.WNBAStep6MOrchestrationNotReadyError,
            ) as exc:
                _set_state(
                    last_gate_passed=False,
                    last_cycle_outcome="blocked_by_step_6m_owned_feed_gate",
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
    step6m_status = step6m.get_step6m_scheduler_orchestration_status()
    activation_requested = step6k.get("activation_requested") is True
    scheduler_authorized = step6k.get("scheduler_authorized") is True
    scheduler_cycle_ready = step6m_status.get("scheduler_cycle_ready") is True
    combined_blockers = list(step6k.get("blocking_reasons") or []) + list(step6m_status.get("blocking_reasons") or [])
    _set_state(
        startup_evaluated_at_utc=_utc_now_iso(),
        startup_activation_requested=activation_requested,
        startup_live_cycle_allowed=(step6k.get("step_5w") or {}).get("live_cycle_allowed") is True,
        startup_step6k_scheduler_authorized=scheduler_authorized,
        startup_step6m_scheduler_cycle_ready=scheduler_cycle_ready,
        startup_phase=step6m_status.get("data_type") if scheduler_cycle_ready else "step_6m_blocked",
        startup_blocking_reasons=combined_blockers,
    )
    # Hard Step 6M boundary: no worker thread exists until both Step 6K and
    # Step 6L/6M are ready. That avoids a live thread repeatedly failing while
    # production refresh authority is intentionally disabled.
    if not scheduler_authorized or not scheduler_cycle_ready:
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
            name="wnba-step-6m-owned-feed-scheduler",
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
def start_wnba_step_6m_runtime() -> None:
    _start_worker()


@router.on_event("shutdown")
def stop_wnba_step_6m_runtime() -> None:
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
    provider_ids: str | None = Query(default=None, description="Compatibility parameter; Step 6M permits only provider_ids=kyre."),
    force: bool = Query(default=True, description="Bypass normal next-due clock; frozen provider-spacing guard still applies."),
):
    try:
        require_staging_activation_ready()
        step6m.require_step6m_scheduler_ready()
        return step6m.run_step6m_manual_cycle(
            date=date,
            season=season,
            provider_ids=provider_ids,
            force=force,
        )
    except (
        WNBAStep6KActivationNotReadyError,
        WNBAStagingActivationNotReadyError,
        step6m.WNBAStep6MOrchestrationNotReadyError,
    ) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except step6m.WNBAStep6MOrchestrationUpstreamError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        step5q._raise_api_error(exc)


@router.get("/rankings/player-props/current/status")
def get_current_wnba_player_prop_scheduler_status(
    date: str | None = Query(default=None),
    season: int = Query(default=CURRENT_SUPPORTED_SEASON, ge=1),
):
    status = step5q.get_current_wnba_player_prop_scheduler_status(date=date, season=season)
    step5r = get_production_runtime_readiness()
    step5w = get_staging_activation_gate()
    step6k = get_step6k_activation_preflight()
    step6m_status = step6m.get_step6m_scheduler_orchestration_status()
    with _worker_lock:
        worker = dict(_worker_state)
    status["production_runtime"] = {
        "source": MODEL_SOURCE,
        "model_version": MODEL_VERSION,
        "step_5r": step5r,
        "step_5w": step5w,
        "step_6k": step6k,
        "step_6m": step6m_status,
        "worker": worker,
        "semantics": {
            "read_path_remains_network_free": True,
            "scheduler_cycle_requires_step_6k_gate": True,
            "scheduler_cycle_requires_step_6m_gate": True,
            "step_6j_durable_canary_required": True,
            "step_6l_owned_feed_refresh_required": True,
            "step_5w_explicit_activation_remains_required": True,
            "step_5r_preflight_remains_required": True,
            "step_5q_locking_remains_authoritative": True,
            "step_5p_model_semantics_remain_authoritative": True,
            "paid_provider_fallback_allowed": False,
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
    report["step_6m_owned_feed_orchestration_gate"] = step6m.get_step6m_scheduler_orchestration_status()
    with _worker_lock:
        report["runtime_worker"] = dict(_worker_state)
    return report


@router.get("/runtime/health")
def get_wnba_production_runtime_health():
    step6k = get_step6k_activation_preflight()
    step6m_status = step6m.get_step6m_scheduler_orchestration_status()
    if step6k.get("scheduler_authorized") is not True or step6m_status.get("scheduler_cycle_ready") is not True:
        raise HTTPException(
            status_code=503,
            detail={
                "source": MODEL_SOURCE,
                "model_version": MODEL_VERSION,
                "scheduler_authorized": step6k.get("scheduler_authorized") is True,
                "scheduler_cycle_ready": step6m_status.get("scheduler_cycle_ready") is True,
                "phase": step6k.get("phase"),
                "activation_requested": step6k.get("activation_requested"),
                "activation_checkpoint_sha256": step6k.get("activation_checkpoint_sha256"),
                "blocking_reasons": list(step6k.get("blocking_reasons") or [])
                + list(step6m_status.get("blocking_reasons") or []),
            },
        )
    return {
        "source": MODEL_SOURCE,
        "model_version": MODEL_VERSION,
        "status": "ready",
        "scheduler_authorized": True,
        "scheduler_cycle_ready": True,
        "live_cycle_allowed": True,
        "owned_feed_refresh_ready": True,
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
