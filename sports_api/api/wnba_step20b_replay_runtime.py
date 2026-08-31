"""Step20B certification-only replay runtime probe.

The replay endpoint is protected by the existing Step20B diagnostic token and a
separate default-OFF replay gate. It injects only deterministic DraftKings and
FanDuel provider bridges into frozen Step12B; the production provider bindings and
the Step8 projection loader remain untouched.
"""
from __future__ import annotations

from copy import deepcopy
import os
import threading
import time
from typing import Any, Mapping

from fastapi import APIRouter, Header, HTTPException

from sports_api import wnba_step12b_live_runtime_assembly as step12b
from sports_api import wnba_step20b_market_replay as replay
from sports_api.api import wnba_step17b_runtime as base

router = APIRouter(prefix="/api/v1/wnba/runtime", tags=["wnba-runtime"])

_REPLAY_LOCK = threading.RLock()
_REPLAY_PROBE: dict[str, Any] = {"status": "idle"}
_REPLAY_THREAD: threading.Thread | None = None


def _authorize(token: str | None) -> None:
    base._authorize_step20b_probe(token)
    if not replay.market_replay_enabled(os.environ):
        raise HTTPException(status_code=404, detail="Not found")


def _set_probe(**changes: Any) -> None:
    with _REPLAY_LOCK:
        _REPLAY_PROBE.update(deepcopy(changes))


def _replay_slate_date(runtime_env: Mapping[str, str]) -> str:
    """Return the configured certification slate, never the wall-clock slate."""
    return str(replay.replay_target(runtime_env)["slate_date"])


def _run_replay_job(
    runtime_env: Mapping[str, str],
    *,
    slate_date: str,
) -> dict[str, Any]:
    """Run frozen Step12B with replayed provider fetchers only.

    Deliberately do not pass ``projection_loader``. This is the certification
    invariant that forces Step12B through the real frozen Step8A→8D path.
    """
    request = step12b.build_step12b_request(
        season=base._STEP20B_PROBE_SEASON,
        slate_date=slate_date,
    )
    return step12b.run_step12b_live_runtime_job(
        request,
        env=runtime_env,
        draftkings_fetcher=replay.draftkings_replay_fetcher,
        fanduel_fetcher=replay.fanduel_replay_fetcher,
    )


def _worker() -> None:
    started = time.perf_counter()
    _set_probe(
        status="running",
        started_at_monotonic=started,
        error_type=None,
        error_message=None,
        replay=replay.installation_status(os.environ),
    )
    try:
        runtime_env = base._step17b.build_runtime_env(os.environ)
        runtime_env = dict(runtime_env)
        runtime_env[replay.STEP20B_MARKET_REPLAY_ENABLED_ENV] = "true"
        slate_date = _replay_slate_date(runtime_env)
        result = _run_replay_job(runtime_env, slate_date=slate_date)
        projection = result.get("projection_assembly") if isinstance(result, dict) else None
        market = result.get("market_overlap") if isinstance(result, dict) else None
        summary = result.get("runtime_summary") if isinstance(result, dict) else None
        accel = base._step20b_accel.installation_status()
        workload = base._step20b_workload.installation_status()
        monte_carlo = base._step20b_mc.installation_status()
        monte_carlo_cdf = base._step20b_mc_cdf.installation_status()
        step4w_cache = base._step20b_step4w_cache.installation_status()
        _set_probe(
            status="returned",
            elapsed_seconds=round(time.perf_counter() - started, 3),
            slate_date=slate_date,
            result_status=result.get("status") if isinstance(result, dict) else None,
            result_health=result.get("health") if isinstance(result, dict) else None,
            replay=replay.installation_status(runtime_env),
            projection_assembly=projection,
            market_overlap={
                "exact_line_multibook_group_count": (market or {}).get("exact_line_multibook_group_count"),
                "unique_projection_target_count": (market or {}).get("unique_projection_target_count"),
            },
            runtime_summary=summary,
            acceleration_last_cycle=accel.get("last_cycle"),
            optional_workload_compat=workload,
            monte_carlo_acceleration=monte_carlo,
            monte_carlo_cdf_compat=monte_carlo_cdf,
            step4w_cycle_cache=step4w_cache,
        )
    except Exception as exc:
        _set_probe(
            status="raised",
            elapsed_seconds=round(time.perf_counter() - started, 3),
            error_type=type(exc).__name__,
            error_message=str(exc)[:1500],
            replay=replay.installation_status(os.environ),
            acceleration_last_cycle=base._step20b_accel.installation_status().get("last_cycle"),
            optional_workload_compat=base._step20b_workload.installation_status(),
            monte_carlo_acceleration=base._step20b_mc.installation_status(),
            monte_carlo_cdf_compat=base._step20b_mc_cdf.installation_status(),
            step4w_cycle_cache=base._step20b_step4w_cache.installation_status(),
        )


@router.get("/step20b-market-replay")
def step20b_market_replay_status(
    x_step20b_diagnostic_token: str | None = Header(
        default=None,
        alias="X-Step20B-Diagnostic-Token",
    ),
):
    _authorize(x_step20b_diagnostic_token)
    return replay.installation_status(os.environ)


@router.post("/step20b-replay-runtime-probe/start")
def step20b_replay_runtime_probe_start(
    x_step20b_diagnostic_token: str | None = Header(
        default=None,
        alias="X-Step20B-Diagnostic-Token",
    ),
):
    global _REPLAY_THREAD
    _authorize(x_step20b_diagnostic_token)
    with _REPLAY_LOCK:
        if _REPLAY_PROBE.get("status") == "running":
            return deepcopy(_REPLAY_PROBE)
        _REPLAY_PROBE.clear()
        _REPLAY_PROBE.update({"status": "starting"})
        _REPLAY_THREAD = threading.Thread(
            target=_worker,
            name="wnba-step20b-replay-runtime-probe",
            daemon=True,
        )
        _REPLAY_THREAD.start()
        return deepcopy(_REPLAY_PROBE)


@router.get("/step20b-replay-runtime-probe/status")
def step20b_replay_runtime_probe_status(
    x_step20b_diagnostic_token: str | None = Header(
        default=None,
        alias="X-Step20B-Diagnostic-Token",
    ),
):
    _authorize(x_step20b_diagnostic_token)
    with _REPLAY_LOCK:
        result = deepcopy(_REPLAY_PROBE)
    if result.get("status") == "running" and result.get("started_at_monotonic") is not None:
        result["elapsed_seconds_now"] = round(
            time.perf_counter() - float(result["started_at_monotonic"]),
            3,
        )
        trace = base._step20b.installation_status()
        recent = trace.get("recent_completed") or []
        active = trace.get("active_calls") or []
        result["trace_progress"] = {
            "call_counts": trace.get("call_counts") or {},
            "active_calls": active,
            "recent_completed_tail": recent[-8:],
        }
        result["monte_carlo_acceleration"] = base._step20b_mc.installation_status()
        result["monte_carlo_cdf_compat"] = base._step20b_mc_cdf.installation_status()
        result["step4w_cycle_cache"] = base._step20b_step4w_cache.installation_status()
    result.pop("started_at_monotonic", None)
    return result


__all__ = ["router", "_replay_slate_date", "_run_replay_job"]
