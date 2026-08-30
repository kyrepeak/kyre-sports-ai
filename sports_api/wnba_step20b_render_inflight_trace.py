"""WNBA Step20B: semantics-neutral Render in-flight runtime trace.

This diagnostic layer exists only to isolate the hosted Step17B/Step12B runtime
bottleneck observed during Step20 production certification. It patches three
private Step12B orchestration seams and returns every original value/exception
unchanged:

* provider bridge fetch timing,
* exact multibook target discovery timing/counts, and
* the private frozen Step8 distribution builder, reproduced call-for-call with
  timing markers between Step8A/8B/8C/8D.

It does not alter any official-data provider seam, sportsbook transport, player
identity, market matching, projection inputs/math, simulation count, batch size,
controller state, persistence, or wagering behavior.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import threading
import time
from typing import Any, Mapping, Sequence

from sports_api import wnba_step12b_live_runtime_assembly as step12b
from sports_api import wnba_step19j_runtime_acceleration as step19j
from sports_api import wnba_step20b_shared_input_cache as shared_cache

SOURCE = "Kyre Sports API WNBA Step20B Render in-flight runtime trace"
MODEL_VERSION = "wnba_step20b_render_inflight_trace_v1"

_ORIGINAL_FETCH_PROVIDER_BRIDGE = step12b._fetch_provider_bridge
_ORIGINAL_EXACT_MULTIBOOK_TARGETS = step12b._exact_multibook_targets
_ORIGINAL_BUILD_FROZEN_STEP8_DISTRIBUTION = step12b._build_frozen_step8_distribution

_LOCK = threading.RLock()
_INSTALLED = False
_TRACE: dict[str, Any] = {}
_CYCLE_COUNT = 0
_ACTIVE_STARTED_MONO: float | None = None
_CACHE_HIT_BASELINE: dict[str, int] = {}
_CACHE_MISS_BASELINE: dict[str, int] = {}
_REST_HIT_BASELINE = 0
_REST_MISS_BASELINE = 0


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cache_totals() -> tuple[dict[str, int], dict[str, int]]:
    status = shared_cache.installation_status()
    hits = status.get("total_hits") or {}
    misses = status.get("total_misses") or {}
    return (
        {str(k): int(v or 0) for k, v in dict(hits).items()},
        {str(k): int(v or 0) for k, v in dict(misses).items()},
    )


def _rest_totals() -> tuple[int, int]:
    status = step19j.installation_status()
    return (
        int(status.get("total_rest_context_hits") or 0),
        int(status.get("total_rest_context_misses") or 0),
    )


def _start_cycle(provider: str) -> None:
    global _CYCLE_COUNT, _ACTIVE_STARTED_MONO
    global _CACHE_HIT_BASELINE, _CACHE_MISS_BASELINE
    global _REST_HIT_BASELINE, _REST_MISS_BASELINE
    hits, misses = _cache_totals()
    rest_hits, rest_misses = _rest_totals()
    with _LOCK:
        _CYCLE_COUNT += 1
        _ACTIVE_STARTED_MONO = time.perf_counter()
        _CACHE_HIT_BASELINE = hits
        _CACHE_MISS_BASELINE = misses
        _REST_HIT_BASELINE = rest_hits
        _REST_MISS_BASELINE = rest_misses
        _TRACE.clear()
        _TRACE.update(
            {
                "cycle_number": _CYCLE_COUNT,
                "cycle_started_at_utc": _now(),
                "last_progress_at_utc": _now(),
                "phase": "provider_discovery",
                "current_provider": provider,
                "provider_timings": {},
                "target_total": None,
                "exact_group_count": None,
                "target_started_count": 0,
                "target_completed_count": 0,
                "target_raised_count": 0,
                "current_target": None,
                "recent_targets": [],
                "last_error_type": None,
            }
        )


def _patch(**changes: Any) -> None:
    with _LOCK:
        _TRACE.update(deepcopy(changes))
        _TRACE["last_progress_at_utc"] = _now()


def _append_recent(target: Mapping[str, Any]) -> None:
    with _LOCK:
        rows = list(_TRACE.get("recent_targets") or [])
        rows.append(deepcopy(dict(target)))
        _TRACE["recent_targets"] = rows[-12:]
        _TRACE["last_progress_at_utc"] = _now()


def fetch_provider_bridge_step20b_trace(*args: Any, **kwargs: Any) -> Any:
    provider = str(kwargs.get("provider") or "unknown")
    if provider.casefold() == "draftkings":
        _start_cycle(provider)
    else:
        _patch(phase="provider_discovery", current_provider=provider)
    started = time.perf_counter()
    try:
        value = _ORIGINAL_FETCH_PROVIDER_BRIDGE(*args, **kwargs)
    except Exception as exc:
        elapsed = time.perf_counter() - started
        with _LOCK:
            timings = dict(_TRACE.get("provider_timings") or {})
            timings[provider] = {
                "seconds": round(elapsed, 3),
                "status": "raised",
                "error_type": type(exc).__name__,
            }
        _patch(provider_timings=timings, last_error_type=type(exc).__name__)
        raise
    elapsed = time.perf_counter() - started
    try:
        discovery = value[1]
        records = int((discovery or {}).get("record_count") or 0)
    except Exception:
        records = None
    with _LOCK:
        timings = dict(_TRACE.get("provider_timings") or {})
        timings[provider] = {
            "seconds": round(elapsed, 3),
            "status": "returned",
            "record_count": records,
        }
    _patch(provider_timings=timings, current_provider=None)
    return value


def exact_multibook_targets_step20b_trace(
    draftkings_records: Sequence[Mapping[str, Any]],
    fanduel_records: Sequence[Mapping[str, Any]],
) -> Any:
    _patch(phase="exact_target_discovery")
    started = time.perf_counter()
    try:
        value = _ORIGINAL_EXACT_MULTIBOOK_TARGETS(draftkings_records, fanduel_records)
    except Exception as exc:
        _patch(
            phase="exact_target_discovery_raised",
            last_error_type=type(exc).__name__,
            exact_target_discovery_seconds=round(time.perf_counter() - started, 3),
        )
        raise
    targets, groups = value
    _patch(
        phase="targets_ready",
        target_total=len(targets),
        exact_group_count=len(groups),
        exact_target_discovery_seconds=round(time.perf_counter() - started, 3),
    )
    return value


def _target_phase(
    *,
    target: dict[str, Any],
    phase: str,
    fn: Any,
    args: tuple[Any, ...] = (),
    kwargs: Mapping[str, Any] | None = None,
) -> Any:
    _patch(phase=phase, current_target=target)
    started = time.perf_counter()
    try:
        value = fn(*args, **dict(kwargs or {}))
    except Exception as exc:
        elapsed = time.perf_counter() - started
        target.setdefault("phase_seconds", {})[phase] = round(elapsed, 3)
        target["status"] = "raised"
        target["error_phase"] = phase
        target["error_type"] = type(exc).__name__
        _patch(current_target=target, last_error_type=type(exc).__name__)
        raise
    target.setdefault("phase_seconds", {})[phase] = round(time.perf_counter() - started, 3)
    _patch(current_target=target)
    return value


def build_frozen_step8_distribution_step20b_trace(
    *,
    game_id: str,
    player_id: int,
    env: Mapping[str, str] | None,
) -> dict[str, Any]:
    with _LOCK:
        index = int(_TRACE.get("target_started_count") or 0) + 1
        _TRACE["target_started_count"] = index
    target: dict[str, Any] = {
        "index": index,
        "game_id": str(game_id),
        "player_id": int(player_id),
        "started_at_utc": _now(),
        "status": "running",
        "phase_seconds": {},
    }
    _patch(current_target=target)
    target_started = time.perf_counter()
    try:
        handoff = _target_phase(
            target=target,
            phase="step8a_handoff",
            fn=step12b.step8a.get_player_game_step8_projection_handoff,
            args=(player_id, game_id),
            kwargs={"env": env},
        )
        baseline = _target_phase(
            target=target,
            phase="step8b_baseline",
            fn=step12b.step8b.build_step8_official_box_baseline,
            args=(handoff,),
        )
        adjusted = _target_phase(
            target=target,
            phase="step8c_context",
            fn=step12b.step8c.build_step8_context_adjusted_projection,
            args=(handoff, baseline),
        )
        distribution = _target_phase(
            target=target,
            phase="step8d_monte_carlo",
            fn=step12b.step8d.simulate_step8_joint_distribution,
            args=(adjusted, baseline),
            kwargs={
                "simulations": step12b.CERTIFIED_SIMULATIONS,
                "batch_size": step12b.CERTIFIED_BATCH_SIZE,
                "env": env,
            },
        )
    except Exception:
        target["total_seconds"] = round(time.perf_counter() - target_started, 3)
        target["finished_at_utc"] = _now()
        with _LOCK:
            _TRACE["target_raised_count"] = int(_TRACE.get("target_raised_count") or 0) + 1
        _append_recent(target)
        _patch(phase="between_targets", current_target=target)
        raise

    target["status"] = "returned"
    target["total_seconds"] = round(time.perf_counter() - target_started, 3)
    target["finished_at_utc"] = _now()
    with _LOCK:
        _TRACE["target_completed_count"] = int(_TRACE.get("target_completed_count") or 0) + 1
    _append_recent(target)
    _patch(phase="between_targets", current_target=target)
    return distribution


def install_step20b_render_inflight_trace() -> dict[str, Any]:
    global _INSTALLED
    seams = (
        ("provider fetch", "_fetch_provider_bridge", _ORIGINAL_FETCH_PROVIDER_BRIDGE, fetch_provider_bridge_step20b_trace),
        ("exact target discovery", "_exact_multibook_targets", _ORIGINAL_EXACT_MULTIBOOK_TARGETS, exact_multibook_targets_step20b_trace),
        ("Step8 distribution builder", "_build_frozen_step8_distribution", _ORIGINAL_BUILD_FROZEN_STEP8_DISTRIBUTION, build_frozen_step8_distribution_step20b_trace),
    )
    for label, attribute, original, target in seams:
        current = getattr(step12b, attribute)
        if current not in {original, target}:
            raise RuntimeError(f"Step20B trace refuses unknown {label} override.")
        setattr(step12b, attribute, target)
    _INSTALLED = True
    return installation_status()


def installation_status() -> dict[str, Any]:
    with _LOCK:
        trace = deepcopy(_TRACE)
        installed = bool(_INSTALLED)
        started_mono = _ACTIVE_STARTED_MONO
        hit_baseline = dict(_CACHE_HIT_BASELINE)
        miss_baseline = dict(_CACHE_MISS_BASELINE)
        rest_hit_baseline = int(_REST_HIT_BASELINE)
        rest_miss_baseline = int(_REST_MISS_BASELINE)
    hits, misses = _cache_totals()
    rest_hits, rest_misses = _rest_totals()
    if trace and started_mono is not None:
        trace["elapsed_seconds"] = round(max(0.0, time.perf_counter() - started_mono), 3)
        trace["shared_cache_cycle_hits"] = {
            name: int(hits.get(name, 0)) - int(hit_baseline.get(name, 0))
            for name in set(hits) | set(hit_baseline)
        }
        trace["shared_cache_cycle_misses"] = {
            name: int(misses.get(name, 0)) - int(miss_baseline.get(name, 0))
            for name in set(misses) | set(miss_baseline)
        }
        trace["step19j_rest_hits"] = rest_hits - rest_hit_baseline
        trace["step19j_rest_misses"] = rest_misses - rest_miss_baseline
    return {
        "data_type": "wnba_step20b_render_inflight_trace_status",
        "source": SOURCE,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _now(),
        "installed": installed,
        "private_seams_active": {
            "provider_fetch": step12b._fetch_provider_bridge is fetch_provider_bridge_step20b_trace,
            "exact_target_discovery": step12b._exact_multibook_targets is exact_multibook_targets_step20b_trace,
            "step8_distribution_builder": step12b._build_frozen_step8_distribution is build_frozen_step8_distribution_step20b_trace,
        },
        "trace": trace or None,
        "guardrails": {
            "diagnostic_only": True,
            "official_data_provider_seams_modified": False,
            "sportsbook_transport_modified": False,
            "player_identity_modified": False,
            "exact_line_matching_modified": False,
            "different_lines_blended": False,
            "player_coverage_modified": False,
            "step8_call_order_modified": False,
            "projection_math_modified": False,
            "monte_carlo_simulation_count_modified": False,
            "monte_carlo_batch_size_modified": False,
            "readiness_relaxed": False,
            "controller_state_modified": False,
            "durable_lease_policy_modified": False,
            "persistence_modified": False,
            "wagering_enabled": False,
        },
    }


__all__ = [
    "MODEL_VERSION",
    "SOURCE",
    "build_frozen_step8_distribution_step20b_trace",
    "exact_multibook_targets_step20b_trace",
    "fetch_provider_bridge_step20b_trace",
    "install_step20b_render_inflight_trace",
    "installation_status",
]
