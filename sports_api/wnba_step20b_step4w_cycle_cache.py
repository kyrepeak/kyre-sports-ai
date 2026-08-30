"""WNBA Step20B: cycle-local Step4W component reuse.

Step20B runtime traces showed the full Step12B cycle repeatedly rebuilding the
same Step4W inputs for multiple projection targets. The slowest repeated work
was inside Step4W optional components (shot context, advanced context,
availability, whistle context) plus repeated player opportunity/rest lookups.

This compatibility layer keeps the frozen Step4W/provider implementations
unchanged. It wraps only Step4W's local dispatcher and unprotected local helper
aliases, memoizes successful exact-call results for one Step12B invocation, and
returns deep copies. Optional unavailable results are deliberately not cached so
the existing fail-soft retry behavior remains authoritative. Raised exceptions
are never cached. Every memo is discarded when the Step12B call exits.

The Step7G-protected shot/advanced/whistle provider aliases are never replaced.
No projection math, readiness rule, simulation count, batch size, sportsbook
transport, persistence behavior, or wagering capability is changed.
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

from sports_api import wnba_projection_input_snapshot as step4w
from sports_api import wnba_step12b_live_runtime_assembly as step12b

SOURCE = "Kyre Sports API WNBA Step20B cycle-local Step4W component cache"
MODEL_VERSION = "wnba_step20b_step4w_cycle_cache_v1"

_CACHE_NAMES = (
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
_LAST_CYCLE: dict[str, Any] | None = None


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


def _new_cache() -> dict[str, Any]:
    return {
        "buckets": {name: {} for name in _CACHE_NAMES},
        "hits": {name: 0 for name in _CACHE_NAMES},
        "misses": {name: 0 for name in _CACHE_NAMES},
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


def _cached_success(
    name: str,
    key: tuple[Any, ...],
    upstream: Callable[[], Any],
) -> Any:
    bucket = _active_bucket(name)
    if bucket is None:
        return upstream()

    with _LOCK:
        if key in bucket:
            _record(name, "hits")
            return deepcopy(bucket[key])

    # Exceptions remain authoritative and are never memoized.
    value = upstream()
    stored = deepcopy(value)
    with _LOCK:
        bucket = _active_bucket(name)
        if bucket is None:
            return value
        if key not in bucket:
            bucket[key] = stored
            _record(name, "misses")
        else:
            _record(name, "hits")
        return deepcopy(bucket[key])


def _upstream(name: str) -> Callable[..., Any]:
    func = _UPSTREAM_HELPERS.get(name)
    if func is None:
        raise RuntimeError(f"Step20B Step4W cache helper {name!r} is not installed.")
    return func


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
    """Memoize only successful exact Step4W optional-dispatch results.

    The dispatcher is the safe place to reuse protected-provider results because
    the protected provider aliases themselves remain untouched. Unavailable
    results are not cached, preserving the frozen optional retry semantics.
    """
    cache = _ACTIVE_CACHE.get()
    upstream = _upstream("_optional_component")
    if cache is None:
        return upstream(name, func, *args, exceptions=exceptions, **kwargs)

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
            return deepcopy(bucket[key])

    result = upstream(name, func, *args, exceptions=exceptions, **kwargs)
    cacheable = (
        isinstance(result, tuple)
        and len(result) == 2
        and isinstance(result[1], Mapping)
        and result[1].get("available") is True
    )
    if not cacheable:
        return result

    stored = deepcopy(result)
    with _LOCK:
        bucket = cache["buckets"]["optional_component"]
        if key not in bucket:
            bucket[key] = stored
            _record("optional_component", "misses")
        else:
            _record("optional_component", "hits")
        return deepcopy(bucket[key])


@contextmanager
def cycle_local_cache_scope() -> Iterator[dict[str, Any]]:
    """Create one exact-call cache; nested use reuses the existing cycle."""
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
        }
    with _LOCK:
        buckets = source.get("buckets") or {}
        hits = deepcopy(dict(source.get("hits") or {}))
        misses = deepcopy(dict(source.get("misses") or {}))
        return {
            "active": True,
            "entries": {name: len(buckets.get(name) or {}) for name in _CACHE_NAMES},
            "hits": hits,
            "misses": misses,
            "total_hits": sum(int(value) for value in hits.values()),
            "total_misses": sum(int(value) for value in misses.values()),
        }


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
    status = "returned"
    error_type: str | None = None
    with cycle_local_cache_scope() as cache:
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
                    "finished_at_utc": _now(),
                    "status": status,
                    "error_type": error_type,
                    "elapsed_seconds": round(time.perf_counter() - started, 3),
                }
            )
            with _LOCK:
                _LAST_CYCLE = deepcopy(summary)


def _binding_contains(current: Callable[..., Any], target: Callable[..., Any]) -> bool:
    seen: set[int] = set()
    candidate: Any = current
    while callable(candidate) and id(candidate) not in seen:
        if candidate is target:
            return True
        seen.add(id(candidate))
        candidate = getattr(candidate, "__wrapped__", None)
    return False


def install_step20b_step4w_cycle_cache() -> dict[str, Any]:
    """Install before the Step20B trace so tracing remains the outer observer."""
    global _INSTALLED, _UPSTREAM_RUN_STEP12B

    targets: tuple[tuple[str, Callable[..., Any]], ...] = (
        ("get_player_opportunity_context", get_player_opportunity_context_step20b),
        ("get_game_rest_travel_context", get_game_rest_travel_context_step20b),
        ("_optional_component", optional_component_step20b),
        ("get_matchup_source_status", get_matchup_source_status_step20b),
    )

    for attr, target in targets:
        current = getattr(step4w, attr)
        if _binding_contains(current, target):
            continue
        previous = _UPSTREAM_HELPERS.get(attr)
        if previous is not None and current is not previous:
            raise RuntimeError(f"Step20B refuses unknown Step4W override for {attr}.")
        _UPSTREAM_HELPERS[attr] = current
        setattr(step4w, attr, target)

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
        "player_opportunity": _binding_contains(
            step4w.get_player_opportunity_context,
            get_player_opportunity_context_step20b,
        ),
        "rest_travel": _binding_contains(
            step4w.get_game_rest_travel_context,
            get_game_rest_travel_context_step20b,
        ),
        "optional_component_dispatch": _binding_contains(
            step4w._optional_component,
            optional_component_step20b,
        ),
        "matchup_source_status": _binding_contains(
            step4w.get_matchup_source_status,
            get_matchup_source_status_step20b,
        ),
        "step12b_wrapper": step12b.run_step12b_live_runtime_job
        is run_step12b_with_step4w_cycle_cache,
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
        "current_cache": cache_stats(),
        "guardrails": {
            "cache_scope": "single_step12b_call_only",
            "cache_cleared_after_every_cycle": True,
            "cached_values_returned_by_deepcopy": True,
            "raised_exceptions_cached": False,
            "optional_unavailable_results_cached": False,
            "exact_call_arguments_are_cache_key": True,
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
    "get_player_opportunity_context_step20b",
    "install_step20b_step4w_cycle_cache",
    "installation_status",
    "optional_component_step20b",
    "run_step12b_with_step4w_cycle_cache",
]
