"""WNBA Step20B: cycle-local Step4W exact-input reuse with live timing.

Run #24 proved the remaining Step20B runtime miss was dominated by repeated
pre-model input construction, not Monte Carlo. This compatibility layer keeps
all frozen Step4W/provider implementations unchanged while reusing only
successful exact-call results inside one Step12B invocation.

In addition to the previously certified Step4W component cache, v2 reuses the
full content-addressed Step4W snapshot at the Step4X -> Step8A readiness
boundary. The readiness result itself is deliberately NOT cached: Step4X still
re-evaluates freshness/readiness on every call. This preserves the frozen
readiness semantics while avoiding an identical expensive snapshot rebuild.

Every cached value is returned by deep copy. Raised exceptions are never
cached. Optional unavailable results remain uncached. Step7G-protected
shot/advanced/whistle provider aliases are never replaced.

Monotonic timing is diagnostic only. It records per-component call counts,
upstream calls, direct cache hits, raises, cumulative/max/last milliseconds,
and currently active calls. Live-cycle timing is exposed through
installation_status() from a process-global registry while the actual cache
remains ContextVar cycle-local. No projection math, readiness rule, simulation
count, batch size, sportsbook transport, persistence behavior, or wagering
capability is changed.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from datetime import datetime, timezone
import threading
import time
from typing import Any, Iterator

from sports_api import wnba_model_input_readiness as step4x
from sports_api import wnba_projection_input_snapshot as step4w
from sports_api import wnba_step12b_live_runtime_assembly as step12b

SOURCE = "Kyre Sports API WNBA Step20B cycle-local Step4W exact-input cache"
MODEL_VERSION = "wnba_step20b_step4w_cycle_cache_v2"

_CACHE_NAMES = (
    "projection_snapshot",
    "player_opportunity",
    "rest_travel",
    "optional_component",
    "matchup_source_status",
)
_PROTECTED_STEP7G_ALIASES = (
    "get_player_shot_chart_dataset",
    "get_opponent_defense_by_shot_zone_dataset",
    "get_player_advanced_stats_dataset",
    "get_team_advanced_stats_dataset",
    "get_game_whistle_context",
)

_ACTIVE_CACHE: ContextVar[dict[str, Any] | None] = ContextVar(
    "wnba_step20b_active_step4w_cycle_cache",
    default=None,
)
_UPSTREAM_HELPERS: dict[str, Callable[..., Any]] = {}
_UPSTREAM_RUN_STEP12B: Callable[..., Any] | None = None
_INSTALLED = False
_LOCK = threading.RLock()
_CYCLE_COUNT = 0
_TIMING_SEQUENCE = 0
_LAST_CYCLE: dict[str, Any] | None = None
_LIVE_CYCLES: dict[int, dict[str, Any]] = {}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return tuple(sorted((str(key), _freeze(item)) for key, item in value.items()))
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(item) for item in value)
    if isinstance(value, set):
        return tuple(sorted(_freeze(item) for item in value))
    if isinstance(value, type):
        return (value.__module__, value.__qualname__)
    try:
        hash(value)
    except TypeError:
        return repr(value)
    return value


def _call_key(args: tuple[Any, ...], kwargs: dict[str, Any]) -> tuple[Any, ...]:
    return (_freeze(args), _freeze(kwargs))


def _empty_timing_row() -> dict[str, Any]:
    return {
        "calls": 0,
        "upstream_calls": 0,
        "direct_cache_hits": 0,
        "returned": 0,
        "raised": 0,
        "cumulative_ms": 0.0,
        "upstream_ms": 0.0,
        "cache_hit_ms": 0.0,
        "max_ms": 0.0,
        "last_ms": 0.0,
    }


def _new_cache() -> dict[str, Any]:
    return {
        "buckets": {name: {} for name in _CACHE_NAMES},
        "hits": {name: 0 for name in _CACHE_NAMES},
        "misses": {name: 0 for name in _CACHE_NAMES},
        "timing_ms": {},
        "active_timing_calls": [],
        "cycle_number": None,
        "cycle_started_at_utc": None,
        "_cycle_started_perf": None,
    }


def _active_bucket(name: str) -> dict[Any, Any] | None:
    cache = _ACTIVE_CACHE.get()
    if cache is None:
        return None
    return cache["buckets"][name]


def _record(name: str, outcome: str) -> None:
    cache = _ACTIVE_CACHE.get()
    if cache is None:
        return
    with _LOCK:
        cache[outcome][name] = int(cache[outcome].get(name, 0)) + 1


def _begin_timing(stage: str) -> tuple[int | None, int]:
    global _TIMING_SEQUENCE
    started_ns = time.perf_counter_ns()
    cache = _ACTIVE_CACHE.get()
    if cache is None:
        return None, started_ns
    with _LOCK:
        _TIMING_SEQUENCE += 1
        sequence = _TIMING_SEQUENCE
        cache["active_timing_calls"].append(
            {
                "sequence": sequence,
                "stage": stage,
                "started_at_utc": _now(),
                "_started_ns": started_ns,
            }
        )
        row = cache["timing_ms"].setdefault(stage, _empty_timing_row())
        row["calls"] = int(row["calls"]) + 1
    return sequence, started_ns


def _finish_timing(
    stage: str,
    sequence: int | None,
    started_ns: int,
    *,
    upstream_called: bool,
    direct_cache_hit: bool,
    raised: bool,
) -> float:
    elapsed_ms = round((time.perf_counter_ns() - started_ns) / 1_000_000.0, 3)
    cache = _ACTIVE_CACHE.get()
    if cache is None:
        return elapsed_ms
    with _LOCK:
        row = cache["timing_ms"].setdefault(stage, _empty_timing_row())
        if upstream_called:
            row["upstream_calls"] = int(row["upstream_calls"]) + 1
            row["upstream_ms"] = round(float(row["upstream_ms"]) + elapsed_ms, 3)
        if direct_cache_hit:
            row["direct_cache_hits"] = int(row["direct_cache_hits"]) + 1
            row["cache_hit_ms"] = round(float(row["cache_hit_ms"]) + elapsed_ms, 3)
        outcome = "raised" if raised else "returned"
        row[outcome] = int(row[outcome]) + 1
        row["cumulative_ms"] = round(float(row["cumulative_ms"]) + elapsed_ms, 3)
        row["max_ms"] = round(max(float(row["max_ms"]), elapsed_ms), 3)
        row["last_ms"] = elapsed_ms
        if sequence is not None:
            for index in range(len(cache["active_timing_calls"]) - 1, -1, -1):
                if cache["active_timing_calls"][index].get("sequence") == sequence:
                    del cache["active_timing_calls"][index]
                    break
    return elapsed_ms


def _cached_success(
    name: str,
    key: tuple[Any, ...],
    upstream: Callable[[], Any],
    *,
    timing_stage: str | None = None,
) -> Any:
    stage = timing_stage or name
    sequence, started_ns = _begin_timing(stage)
    bucket = _active_bucket(name)
    if bucket is None:
        try:
            value = upstream()
        except Exception:
            _finish_timing(stage, sequence, started_ns, upstream_called=True, direct_cache_hit=False, raised=True)
            raise
        _finish_timing(stage, sequence, started_ns, upstream_called=True, direct_cache_hit=False, raised=False)
        return value

    with _LOCK:
        if key in bucket:
            _record(name, "hits")
            value = deepcopy(bucket[key])
            _finish_timing(stage, sequence, started_ns, upstream_called=False, direct_cache_hit=True, raised=False)
            return value

    try:
        value = upstream()
    except Exception:
        _finish_timing(stage, sequence, started_ns, upstream_called=True, direct_cache_hit=False, raised=True)
        raise

    stored = deepcopy(value)
    with _LOCK:
        bucket = _active_bucket(name)
        if bucket is None:
            result = value
        elif key not in bucket:
            bucket[key] = stored
            _record(name, "misses")
            result = deepcopy(bucket[key])
        else:
            _record(name, "hits")
            result = deepcopy(bucket[key])
    _finish_timing(stage, sequence, started_ns, upstream_called=True, direct_cache_hit=False, raised=False)
    return result


def _upstream(name: str) -> Callable[..., Any]:
    func = _UPSTREAM_HELPERS.get(name)
    if func is None:
        raise RuntimeError(f"Step20B Step4W cache helper {name!r} is not installed.")
    return func


def get_player_game_projection_input_snapshot_step20b(*args: Any, **kwargs: Any) -> Any:
    key = _call_key(args, kwargs)
    return _cached_success(
        "projection_snapshot",
        key,
        lambda: _upstream("get_player_game_projection_input_snapshot")(*args, **kwargs),
    )


def get_player_opportunity_context_step20b(*args: Any, **kwargs: Any) -> Any:
    key = _call_key(args, kwargs)
    return _cached_success(
        "player_opportunity",
        key,
        lambda: _upstream("get_player_opportunity_context")(*args, **kwargs),
    )


def get_game_rest_travel_context_step20b(*args: Any, **kwargs: Any) -> Any:
    key = _call_key(args, kwargs)
    return _cached_success(
        "rest_travel",
        key,
        lambda: _upstream("get_game_rest_travel_context")(*args, **kwargs),
    )


def get_matchup_source_status_step20b(*args: Any, **kwargs: Any) -> Any:
    key = _call_key(args, kwargs)
    return _cached_success(
        "matchup_source_status",
        key,
        lambda: _upstream("get_matchup_source_status")(*args, **kwargs),
    )


def optional_component_step20b(
    name: str,
    func: Callable[..., dict[str, Any]],
    *args: Any,
    exceptions: tuple[type[BaseException], ...],
    **kwargs: Any,
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    stage = f"optional_component:{str(name).strip() or 'unknown'}"
    sequence, started_ns = _begin_timing(stage)
    cache = _ACTIVE_CACHE.get()
    upstream = _upstream("_optional_component")
    if cache is None:
        try:
            result = upstream(name, func, *args, exceptions=exceptions, **kwargs)
        except Exception:
            _finish_timing(stage, sequence, started_ns, upstream_called=True, direct_cache_hit=False, raised=True)
            raise
        _finish_timing(stage, sequence, started_ns, upstream_called=True, direct_cache_hit=False, raised=False)
        return result

    func_identity = (
        getattr(func, "__module__", ""),
        getattr(func, "__qualname__", getattr(func, "__name__", repr(func))),
    )
    key = (
        str(name),
        func_identity,
        _freeze(args),
        _freeze(kwargs),
        tuple((exc.__module__, exc.__qualname__) for exc in exceptions),
    )
    bucket = cache["buckets"]["optional_component"]
    with _LOCK:
        if key in bucket:
            _record("optional_component", "hits")
            result = deepcopy(bucket[key])
            _finish_timing(stage, sequence, started_ns, upstream_called=False, direct_cache_hit=True, raised=False)
            return result

    try:
        result = upstream(name, func, *args, exceptions=exceptions, **kwargs)
    except Exception:
        _finish_timing(stage, sequence, started_ns, upstream_called=True, direct_cache_hit=False, raised=True)
        raise

    cacheable = (
        isinstance(result, tuple)
        and len(result) == 2
        and isinstance(result[1], Mapping)
        and result[1].get("available") is True
    )
    if not cacheable:
        _finish_timing(stage, sequence, started_ns, upstream_called=True, direct_cache_hit=False, raised=False)
        return result

    stored = deepcopy(result)
    with _LOCK:
        bucket = cache["buckets"]["optional_component"]
        if key not in bucket:
            bucket[key] = stored
            _record("optional_component", "misses")
        else:
            _record("optional_component", "hits")
        returned = deepcopy(bucket[key])
    _finish_timing(stage, sequence, started_ns, upstream_called=True, direct_cache_hit=False, raised=False)
    return returned


@contextmanager
def cycle_local_cache_scope() -> Iterator[dict[str, Any]]:
    existing = _ACTIVE_CACHE.get()
    if existing is not None:
        yield existing
        return
    cache = _new_cache()
    token = _ACTIVE_CACHE.set(cache)
    try:
        yield cache
    finally:
        _ACTIVE_CACHE.reset(token)


def _active_timing_snapshot(source: Mapping[str, Any]) -> list[dict[str, Any]]:
    now_ns = time.perf_counter_ns()
    rows: list[dict[str, Any]] = []
    for item in source.get("active_timing_calls") or []:
        if not isinstance(item, Mapping):
            continue
        started_ns = item.get("_started_ns")
        elapsed_ms = None
        if isinstance(started_ns, int):
            elapsed_ms = round((now_ns - started_ns) / 1_000_000.0, 3)
        rows.append(
            {
                "sequence": item.get("sequence"),
                "stage": item.get("stage"),
                "started_at_utc": item.get("started_at_utc"),
                "elapsed_ms_now": elapsed_ms,
            }
        )
    return rows


def cache_stats(cache: Mapping[str, Any] | None = None) -> dict[str, Any]:
    source = cache if cache is not None else _ACTIVE_CACHE.get()
    if not isinstance(source, Mapping):
        return {
            "active": False,
            "entries": {name: 0 for name in _CACHE_NAMES},
            "hits": {name: 0 for name in _CACHE_NAMES},
            "misses": {name: 0 for name in _CACHE_NAMES},
            "total_hits": 0,
            "total_misses": 0,
            "timing_unit": "milliseconds",
            "timing_ms": {},
            "active_timing_calls": [],
        }
    with _LOCK:
        buckets = source.get("buckets") or {}
        hits = deepcopy(dict(source.get("hits") or {}))
        misses = deepcopy(dict(source.get("misses") or {}))
        timings = deepcopy(dict(source.get("timing_ms") or {}))
        active_timing = _active_timing_snapshot(source)
        return {
            "active": True,
            "entries": {name: len(buckets.get(name) or {}) for name in _CACHE_NAMES},
            "hits": hits,
            "misses": misses,
            "total_hits": sum(int(value) for value in hits.values()),
            "total_misses": sum(int(value) for value in misses.values()),
            "timing_unit": "milliseconds",
            "timing_ms": timings,
            "active_timing_calls": active_timing,
        }


def _live_cycle_summaries() -> list[dict[str, Any]]:
    now_perf = time.perf_counter()
    with _LOCK:
        items = list(_LIVE_CYCLES.items())
    rows: list[dict[str, Any]] = []
    for cycle_number, cache in items:
        stats = cache_stats(cache)
        started_perf = cache.get("_cycle_started_perf")
        elapsed_ms_now = None
        if isinstance(started_perf, (int, float)):
            elapsed_ms_now = round((now_perf - float(started_perf)) * 1000.0, 3)
        stats.update(
            {
                "cycle_number": cycle_number,
                "status": "running",
                "started_at_utc": cache.get("cycle_started_at_utc"),
                "elapsed_ms_now": elapsed_ms_now,
            }
        )
        rows.append(stats)
    rows.sort(key=lambda row: int(row.get("cycle_number") or 0))
    return rows


def run_step12b_with_step4w_cycle_cache(*args: Any, **kwargs: Any) -> Any:
    upstream = _UPSTREAM_RUN_STEP12B
    if upstream is None:
        raise RuntimeError("Step20B Step4W cycle cache is not installed.")

    global _CYCLE_COUNT, _LAST_CYCLE
    existing = _ACTIVE_CACHE.get()
    if existing is not None:
        return upstream(*args, **kwargs)

    with _LOCK:
        _CYCLE_COUNT += 1
        cycle_number = _CYCLE_COUNT
    started = time.perf_counter()
    started_utc = _now()
    status = "returned"
    error_type: str | None = None
    with cycle_local_cache_scope() as cache:
        cache["cycle_number"] = cycle_number
        cache["cycle_started_at_utc"] = started_utc
        cache["_cycle_started_perf"] = started
        with _LOCK:
            _LIVE_CYCLES[cycle_number] = cache
        try:
            return upstream(*args, **kwargs)
        except Exception as exc:
            status = "raised"
            error_type = type(exc).__name__
            raise
        finally:
            summary = cache_stats(cache)
            summary.update(
                {
                    "cycle_number": cycle_number,
                    "started_at_utc": started_utc,
                    "finished_at_utc": _now(),
                    "status": status,
                    "error_type": error_type,
                    "elapsed_seconds": round(time.perf_counter() - started, 3),
                }
            )
            with _LOCK:
                _LAST_CYCLE = deepcopy(summary)
                _LIVE_CYCLES.pop(cycle_number, None)


def _binding_contains(current: Callable[..., Any], target: Callable[..., Any]) -> bool:
    seen: set[int] = set()
    candidate: Any = current
    while callable(candidate) and id(candidate) not in seen:
        if candidate is target:
            return True
        seen.add(id(candidate))
        candidate = getattr(candidate, "__wrapped__", None)
    return False


def _install_binding(module: Any, attr: str, target: Callable[..., Any], *, label: str) -> None:
    current = getattr(module, attr)
    if _binding_contains(current, target):
        return
    previous = _UPSTREAM_HELPERS.get(attr)
    if previous is not None and current is not previous:
        raise RuntimeError(f"Step20B refuses unknown {label} override for {attr}.")
    _UPSTREAM_HELPERS[attr] = current
    setattr(module, attr, target)


def install_step20b_step4w_cycle_cache() -> dict[str, Any]:
    global _INSTALLED, _UPSTREAM_RUN_STEP12B

    step4w_targets: tuple[tuple[str, Callable[..., Any]], ...] = (
        ("get_player_opportunity_context", get_player_opportunity_context_step20b),
        ("get_game_rest_travel_context", get_game_rest_travel_context_step20b),
        ("_optional_component", optional_component_step20b),
        ("get_matchup_source_status", get_matchup_source_status_step20b),
    )
    for attr, target in step4w_targets:
        _install_binding(step4w, attr, target, label="Step4W")

    _install_binding(
        step4x,
        "get_player_game_projection_input_snapshot",
        get_player_game_projection_input_snapshot_step20b,
        label="Step4X snapshot",
    )

    current_run = step12b.run_step12b_live_runtime_job
    if current_run is not run_step12b_with_step4w_cycle_cache:
        if _UPSTREAM_RUN_STEP12B is not None and current_run is not _UPSTREAM_RUN_STEP12B:
            raise RuntimeError("Step20B refuses unknown Step12B runtime override for Step4W cache.")
        _UPSTREAM_RUN_STEP12B = current_run
        step12b.run_step12b_live_runtime_job = run_step12b_with_step4w_cycle_cache

    _INSTALLED = True
    return installation_status()


def installation_status() -> dict[str, Any]:
    bindings = {
        "projection_snapshot": _binding_contains(
            step4x.get_player_game_projection_input_snapshot,
            get_player_game_projection_input_snapshot_step20b,
        ),
        "player_opportunity": _binding_contains(step4w.get_player_opportunity_context, get_player_opportunity_context_step20b),
        "rest_travel": _binding_contains(step4w.get_game_rest_travel_context, get_game_rest_travel_context_step20b),
        "optional_component_dispatch": _binding_contains(step4w._optional_component, optional_component_step20b),
        "matchup_source_status": _binding_contains(step4w.get_matchup_source_status, get_matchup_source_status_step20b),
        "step12b_wrapper": _binding_contains(step12b.run_step12b_live_runtime_job, run_step12b_with_step4w_cycle_cache),
    }
    with _LOCK:
        last_cycle = deepcopy(_LAST_CYCLE)
        cycles = int(_CYCLE_COUNT)
    return {
        "data_type": "wnba_step20b_step4w_cycle_cache_status",
        "source": SOURCE,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _now(),
        "installed": bool(_INSTALLED),
        "all_bindings_active": bool(_INSTALLED and all(bindings.values())),
        "bindings": bindings,
        "cycle_count": cycles,
        "last_cycle": last_cycle,
        "live_cycles": _live_cycle_summaries(),
        "current_cache": cache_stats(),
        "guardrails": {
            "cache_scope": "single_step12b_call_only",
            "cache_cleared_after_every_cycle": True,
            "cached_values_returned_by_deepcopy": True,
            "raised_exceptions_cached": False,
            "optional_unavailable_results_cached": False,
            "exact_call_arguments_are_cache_key": True,
            "full_step4w_snapshot_reuse_enabled": True,
            "full_snapshot_cache_scope": "single_step12b_call_exact_arguments_only",
            "readiness_result_cached": False,
            "step8a_handoff_result_cached": False,
            "freshness_recomputed_by_step4x_on_every_readiness_call": True,
            "timing_uses_monotonic_clock": True,
            "timing_unit": "milliseconds",
            "timing_changes_execution": False,
            "step7g_protected_provider_aliases_modified": False,
            "projection_math_modified": False,
            "readiness_relaxed": False,
            "monte_carlo_simulation_count_modified": False,
            "monte_carlo_batch_size_modified": False,
            "sportsbook_transport_modified": False,
            "persistence_modified": False,
            "wagering_enabled": False,
        },
    }


__all__ = [
    "MODEL_VERSION",
    "SOURCE",
    "cache_stats",
    "cycle_local_cache_scope",
    "get_game_rest_travel_context_step20b",
    "get_matchup_source_status_step20b",
    "get_player_game_projection_input_snapshot_step20b",
    "get_player_opportunity_context_step20b",
    "install_step20b_step4w_cycle_cache",
    "installation_status",
    "optional_component_step20b",
    "run_step12b_with_step4w_cycle_cache",
]
