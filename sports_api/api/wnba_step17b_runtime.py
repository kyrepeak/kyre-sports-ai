import hmac
import os
import threading
import time
from copy import deepcopy

from fastapi import APIRouter, Header, HTTPException

from sports_api import wnba_projection_input_snapshot as _step4w
from sports_api import wnba_step12b_live_runtime_assembly as _step12b
from sports_api import wnba_step17b_always_on_runtime as _step17b
from sports_api import wnba_step19e_cooldown_aware_cycle as _step19e
from sports_api import wnba_step19g_hosted_provider_trace as _step19g
from sports_api import wnba_step19h_fanduel_hosted_transport as _step19h
from sports_api import wnba_step19i_official_slate_transport as _step19i
from sports_api import wnba_step19j_runtime_acceleration as _step19j
from sports_api import wnba_step19k_market_not_ready as _step19k
from sports_api import wnba_step19l_fanduel_identity_trace as _step19l
from sports_api import wnba_step19m_fanduel_line_move as _step19m
from sports_api import wnba_step19n_fanduel_empty_market as _step19n
from sports_api import wnba_step20b_runtime_acceleration as _step20b_accel
from sports_api import wnba_step20b_optional_workload_compat as _step20b_workload
from sports_api import wnba_step20b_monte_carlo_acceleration as _step20b_mc
from sports_api import wnba_step20b_rollover_stage_trace as _step20b
from sports_api.runtime_fingerprint import get_runtime_build_identity

_step19e.install_step19e_cooldown_aware_cycle()
_step19g.install_step19g_hosted_provider_trace()
_step19h.install_step19h_fanduel_hosted_transport()
_step19i.install_step19i_official_slate_transport()
_step19j.install_step19j_runtime_acceleration()
_step19k.install_step19k_market_not_ready()
_step19l.install_step19l_fanduel_identity_trace()
_step19m.install_step19m_fanduel_line_move()
_step19n.install_step19n_fanduel_empty_market()
_step20b_accel.install_step20b_runtime_acceleration()
_step20b_workload.install_step20b_optional_workload_compat()
# Install the semantics-preserving Step8D accelerator before the diagnostic
# trace wraps Step8D, so the trace measures the accelerated implementation.
_step20b_mc.install_step20b_monte_carlo_acceleration()
_step20b.install_step20b_rollover_stage_trace()

router = APIRouter(prefix="/api/v1/wnba/runtime", tags=["wnba-runtime"])

_STEP20B_PROBE_ENABLED_ENV = "WNBA_STEP20B_PROBE_ENABLED"
_STEP20B_PROBE_TOKEN_ENV = "WNBA_STEP20B_PROBE_TOKEN"
_STEP20B_PROBE_PLAYER_ID = 203825
_STEP20B_PROBE_SEASON = 2026
_FULL_PROBE_LOCK = threading.RLock()
_FULL_PROBE: dict = {"status": "idle"}
_FULL_PROBE_THREAD: threading.Thread | None = None


def _truthy(value: object) -> bool:
    return str(value or "").strip().casefold() not in {"", "0", "false", "no", "off", "disabled"}


def _authorize_step20b_probe(token: str | None) -> None:
    if not _truthy(os.environ.get(_STEP20B_PROBE_ENABLED_ENV)):
        raise HTTPException(status_code=404, detail="Not found")
    expected = str(os.environ.get(_STEP20B_PROBE_TOKEN_ENV) or "")
    supplied = str(token or "")
    if len(expected) < 32:
        raise HTTPException(status_code=503, detail="Diagnostic probe is not configured")
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=403, detail="Forbidden")


def _run_fixed_opportunity_probe() -> dict:
    return _step4w.get_player_opportunity_context(
        _STEP20B_PROBE_PLAYER_ID,
        _STEP20B_PROBE_SEASON,
        season_type="Regular Season",
        last_n_games=5,
        include_current_availability=True,
    )


def _set_full_probe(**changes) -> None:
    with _FULL_PROBE_LOCK:
        _FULL_PROBE.update(deepcopy(changes))


def _full_probe_worker() -> None:
    started = time.perf_counter()
    _set_full_probe(status="running", started_at_monotonic=started, error_type=None, error_message=None)
    try:
        runtime_env = _step17b.build_runtime_env(os.environ)
        slate_date = _step17b._slate_date()
        request = _step12b.build_step12b_request(
            season=_STEP20B_PROBE_SEASON,
            slate_date=slate_date,
        )
        result = _step12b.run_step12b_live_runtime_job(request, env=runtime_env)
        projection = result.get("projection_assembly") if isinstance(result, dict) else None
        market = result.get("market_overlap") if isinstance(result, dict) else None
        summary = result.get("runtime_summary") if isinstance(result, dict) else None
        accel = _step20b_accel.installation_status()
        workload = _step20b_workload.installation_status()
        monte_carlo = _step20b_mc.installation_status()
        _set_full_probe(
            status="returned",
            elapsed_seconds=round(time.perf_counter() - started, 3),
            slate_date=slate_date,
            result_status=result.get("status") if isinstance(result, dict) else None,
            result_health=result.get("health") if isinstance(result, dict) else None,
            projection_assembly=projection,
            market_overlap={
                "exact_line_multibook_group_count": (market or {}).get("exact_line_multibook_group_count"),
                "unique_projection_target_count": (market or {}).get("unique_projection_target_count"),
            },
            runtime_summary=summary,
            acceleration_last_cycle=accel.get("last_cycle"),
            optional_workload_compat=workload,
            monte_carlo_acceleration=monte_carlo,
        )
    except Exception as exc:
        _set_full_probe(
            status="raised",
            elapsed_seconds=round(time.perf_counter() - started, 3),
            error_type=type(exc).__name__,
            error_message=str(exc)[:1500],
            acceleration_last_cycle=_step20b_accel.installation_status().get("last_cycle"),
            optional_workload_compat=_step20b_workload.installation_status(),
            monte_carlo_acceleration=_step20b_mc.installation_status(),
        )


@router.get("/step17b")
def step17b_runtime_status():
    return _step17b.get_step17b_status()


@router.get("/step19g-provider-trace")
def step19g_provider_trace_status():
    return _step19g.get_step19g_hosted_provider_trace()


@router.get("/step19h-fanduel-transport")
def step19h_fanduel_transport_status():
    return _step19h.get_step19h_fanduel_transport_status()


@router.get("/step19i-official-slate-transport")
def step19i_official_slate_transport_status():
    return _step19i.installation_status()


@router.get("/step19j-runtime-acceleration")
def step19j_runtime_acceleration_status():
    return _step19j.installation_status()


@router.get("/step19k-market-not-ready")
def step19k_market_not_ready_status():
    return _step19k.installation_status()


@router.get("/step19l-fanduel-identity-trace")
def step19l_fanduel_identity_trace_status():
    return _step19l.get_step19l_fanduel_identity_trace()


@router.get("/step19m-fanduel-line-move")
def step19m_fanduel_line_move_status():
    return _step19m.installation_status()


@router.get("/step19n-fanduel-empty-market")
def step19n_fanduel_empty_market_status():
    return _step19n.installation_status()


@router.get("/step20b-runtime-acceleration")
def step20b_runtime_acceleration_status():
    return _step20b_accel.installation_status()


@router.get("/step20b-optional-workload-compat")
def step20b_optional_workload_compat_status():
    return _step20b_workload.installation_status()


@router.get("/step20b-monte-carlo-acceleration")
def step20b_monte_carlo_acceleration_status():
    return _step20b_mc.installation_status()


@router.get("/step20b-rollover-stage-trace")
def step20b_rollover_stage_trace_status():
    return _step20b.installation_status()


@router.post("/step20b-player-opportunity-probe")
def step20b_player_opportunity_probe(
    x_step20b_diagnostic_token: str | None = Header(default=None, alias="X-Step20B-Diagnostic-Token"),
):
    _authorize_step20b_probe(x_step20b_diagnostic_token)
    try:
        with _step20b_accel.cycle_local_cache_scope() as cache:
            cold_started = time.perf_counter()
            cold = _run_fixed_opportunity_probe()
            cold_elapsed = round(time.perf_counter() - cold_started, 3)
            warm_started = time.perf_counter()
            warm = _run_fixed_opportunity_probe()
            warm_elapsed = round(time.perf_counter() - warm_started, 3)
            stats = _step20b_accel.cache_stats(cache)
        comparable = (
            isinstance(cold, dict) and isinstance(warm, dict)
            and cold.get("data_type") == warm.get("data_type")
            and cold.get("player_id") == warm.get("player_id")
            and cold.get("latest_observed_team_key") == warm.get("latest_observed_team_key")
            and cold.get("requested_last_n_games") == warm.get("requested_last_n_games")
            and cold.get("components") == warm.get("components")
        )
        return {
            "data_type": "wnba_step20b_player_opportunity_probe",
            "trace_model_version": _step20b.MODEL_VERSION,
            "acceleration_model_version": _step20b_accel.MODEL_VERSION,
            "monte_carlo_acceleration_model_version": _step20b_mc.MODEL_VERSION,
            "status": "returned",
            "player_id": _STEP20B_PROBE_PLAYER_ID,
            "season": _STEP20B_PROBE_SEASON,
            "cold_elapsed_seconds": cold_elapsed,
            "warm_elapsed_seconds": warm_elapsed,
            "elapsed_reduction_seconds": round(cold_elapsed - warm_elapsed, 3),
            "speedup_ratio": round(cold_elapsed / warm_elapsed, 3) if warm_elapsed > 0 else None,
            "comparison_surface_equal": comparable,
            "cache": stats,
        }
    except Exception as exc:
        return {
            "data_type": "wnba_step20b_player_opportunity_probe",
            "status": "raised",
            "error_type": type(exc).__name__,
            "error_message": str(exc)[:1000],
        }


@router.post("/step20b-full-runtime-probe/start")
def step20b_full_runtime_probe_start(
    x_step20b_diagnostic_token: str | None = Header(default=None, alias="X-Step20B-Diagnostic-Token"),
):
    global _FULL_PROBE_THREAD
    _authorize_step20b_probe(x_step20b_diagnostic_token)
    with _FULL_PROBE_LOCK:
        if _FULL_PROBE.get("status") == "running":
            return deepcopy(_FULL_PROBE)
        _FULL_PROBE.clear()
        _FULL_PROBE.update({"status": "starting"})
        _FULL_PROBE_THREAD = threading.Thread(
            target=_full_probe_worker,
            name="wnba-step20b-full-runtime-probe",
            daemon=True,
        )
        _FULL_PROBE_THREAD.start()
        return deepcopy(_FULL_PROBE)


@router.get("/step20b-full-runtime-probe/status")
def step20b_full_runtime_probe_status(
    x_step20b_diagnostic_token: str | None = Header(default=None, alias="X-Step20B-Diagnostic-Token"),
):
    _authorize_step20b_probe(x_step20b_diagnostic_token)
    with _FULL_PROBE_LOCK:
        result = deepcopy(_FULL_PROBE)
    if result.get("status") == "running" and result.get("started_at_monotonic") is not None:
        result["elapsed_seconds_now"] = round(time.perf_counter() - float(result["started_at_monotonic"]), 3)
        trace = _step20b.installation_status()
        active = trace.get("active_calls") or []
        recent = trace.get("recent_completed") or []
        result["trace_progress"] = {
            "call_counts": trace.get("call_counts") or {},
            "active_calls": active,
            "recent_completed_tail": recent[-8:],
        }
        result["monte_carlo_acceleration"] = _step20b_mc.installation_status()
    result.pop("started_at_monotonic", None)
    return result


@router.get("/build")
def runtime_build_identity():
    return get_runtime_build_identity()