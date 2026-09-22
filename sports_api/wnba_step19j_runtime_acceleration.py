"""WNBA Step 19J: semantics-preserving Step12B runtime acceleration.

Step19I proved the hosted provider path but exposed an execution-time bottleneck:
Step8A repeatedly rebuilt the same expensive Step4N game rest/travel context for
multiple players in one Step12B cycle. In addition, the Step7G Cup-safe overlay
used to clear its own team-history cache on every idempotent install.

This compatibility layer does not reduce simulations, loosen readiness, change
projection math, modify sportsbook transport, persist state, or enable wagering.
It gives one Step12B call a private game-context memo so identical game-level
Step4N reads are performed once per cycle and returned by deep copy thereafter.
The memo is discarded in a ``finally`` block at the end of every Step12B call, so
nothing from a prior market cycle can be reused by a later cycle.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from contextvars import ContextVar
from copy import deepcopy
from datetime import datetime, timezone
import threading
import time
from typing import Any

from sports_api import wnba_projection_input_snapshot as projection_snapshot
from sports_api import wnba_step12b_live_runtime_assembly as step12b

SOURCE = "Kyre Sports API WNBA Step19J cycle-local runtime acceleration"
MODEL_VERSION = "wnba_step19j_cycle_local_game_context_v1"

_ORIGINAL_GAME_REST = projection_snapshot.get_game_rest_travel_context
_UPSTREAM_RUN_STEP12B: Callable[..., Any] | None = None
_INSTALLED = False
_LOCK = threading.RLock()
_ACTIVE_GAME_CACHE: ContextVar[dict[tuple[str, int, bool], dict[str, Any]] | None] = ContextVar(
    "wnba_step19j_active_game_context_cache", default=None
)

_CYCLE_COUNT = 0
_TOTAL_REST_HITS = 0
_TOTAL_REST_MISSES = 0
_LAST_CYCLE: dict[str, Any] | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _strict_game_key(
    game_id: str,
    season: int,
    include_observed_workload: bool,
) -> tuple[str, int, bool]:
    return str(game_id), int(season), bool(include_observed_workload)


def get_game_rest_travel_context_step19j(
    game_id: str,
    season: int,
    *,
    include_observed_workload: bool = True,
) -> dict[str, Any]:
    """Return exact Step4N output, memoized only inside the active Step12B call."""
    cache = _ACTIVE_GAME_CACHE.get()
    if cache is None:
        return _ORIGINAL_GAME_REST(
            game_id,
            season,
            include_observed_workload=include_observed_workload,
        )

    key = _strict_game_key(game_id, season, include_observed_workload)
    if key in cache:
        with _LOCK:
            global _TOTAL_REST_HITS
            _TOTAL_REST_HITS += 1
        return deepcopy(cache[key])

    # Exceptions are intentionally not cached. A required upstream failure keeps
    # the original fail-closed behavior on every attempted read.
    value = _ORIGINAL_GAME_REST(
        game_id,
        season,
        include_observed_workload=include_observed_workload,
    )
    if not isinstance(value, Mapping):
        # The frozen function is expected to return an object. Do not turn an
        # unexpected shape into a successful cache entry.
        return value
    cache[key] = deepcopy(dict(value))
    with _LOCK:
        global _TOTAL_REST_MISSES
        _TOTAL_REST_MISSES += 1
    return deepcopy(cache[key])


def run_step12b_with_cycle_local_context(*args: Any, **kwargs: Any) -> Any:
    """Execute the already-installed Step12B chain with a fresh private memo."""
    upstream = _UPSTREAM_RUN_STEP12B
    if upstream is None:
        raise RuntimeError("Step19J runtime acceleration is not installed.")

    token = _ACTIVE_GAME_CACHE.set({})
    started = time.perf_counter()
    start_hits: int
    start_misses: int
    with _LOCK:
        global _CYCLE_COUNT
        _CYCLE_COUNT += 1
        cycle_number = _CYCLE_COUNT
        start_hits = _TOTAL_REST_HITS
        start_misses = _TOTAL_REST_MISSES

    status = "returned"
    error_type: str | None = None
    try:
        return upstream(*args, **kwargs)
    except Exception as exc:
        status = "raised"
        error_type = type(exc).__name__
        raise
    finally:
        cache = _ACTIVE_GAME_CACHE.get() or {}
        elapsed = time.perf_counter() - started
        with _LOCK:
            global _LAST_CYCLE
            _LAST_CYCLE = {
                "cycle_number": cycle_number,
                "finished_at_utc": _now(),
                "status": status,
                "error_type": error_type,
                "elapsed_seconds": round(elapsed, 3),
                "game_context_entry_count": len(cache),
                "rest_context_hits": _TOTAL_REST_HITS - start_hits,
                "rest_context_misses": _TOTAL_REST_MISSES - start_misses,
            }
        _ACTIVE_GAME_CACHE.reset(token)


def install_step19j_runtime_acceleration() -> dict[str, Any]:
    """Install after Step19G so its provider trace remains inside this wrapper."""
    global _INSTALLED, _UPSTREAM_RUN_STEP12B

    current_rest = projection_snapshot.get_game_rest_travel_context
    if current_rest not in {_ORIGINAL_GAME_REST, get_game_rest_travel_context_step19j}:
        raise RuntimeError(
            "Step19J refuses to replace an unknown game rest/travel override."
        )

    current_run = step12b.run_step12b_live_runtime_job
    if current_run is run_step12b_with_cycle_local_context:
        _INSTALLED = True
        return installation_status()

    if _UPSTREAM_RUN_STEP12B is not None and current_run is not _UPSTREAM_RUN_STEP12B:
        raise RuntimeError("Step19J refuses to replace an unknown Step12B runtime override.")

    # Capture the current chain at installation time (not module import time).
    # In hosted startup this is Step19G's trace wrapper, preserving diagnostics.
    _UPSTREAM_RUN_STEP12B = current_run
    projection_snapshot.get_game_rest_travel_context = get_game_rest_travel_context_step19j
    step12b.run_step12b_live_runtime_job = run_step12b_with_cycle_local_context
    _INSTALLED = True
    return installation_status()


def installation_status() -> dict[str, Any]:
    with _LOCK:
        latest = deepcopy(_LAST_CYCLE)
        cycle_count = int(_CYCLE_COUNT)
        hits = int(_TOTAL_REST_HITS)
        misses = int(_TOTAL_REST_MISSES)
    return {
        "data_type": "wnba_step19j_runtime_acceleration_status",
        "source": SOURCE,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _now(),
        "installed": _INSTALLED,
        "step12b_wrapper_active": (
            step12b.run_step12b_live_runtime_job is run_step12b_with_cycle_local_context
        ),
        "game_rest_cycle_cache_active": (
            projection_snapshot.get_game_rest_travel_context
            is get_game_rest_travel_context_step19j
        ),
        "cycle_count": cycle_count,
        "total_rest_context_hits": hits,
        "total_rest_context_misses": misses,
        "last_cycle": latest,
        "guardrails": {
            "cache_scope": "single_step12b_call_only",
            "cache_cleared_after_every_cycle": True,
            "cached_values_returned_by_deepcopy": True,
            "exceptions_cached": False,
            "monte_carlo_simulation_count_modified": False,
            "monte_carlo_batch_size_modified": False,
            "projection_math_modified": False,
            "readiness_relaxed": False,
            "sportsbook_transport_modified": False,
            "controller_state_modified": False,
            "persistence_modified": False,
            "wagering_enabled": False,
        },
    }


__all__ = [
    "MODEL_VERSION",
    "SOURCE",
    "get_game_rest_travel_context_step19j",
    "install_step19j_runtime_acceleration",
    "installation_status",
    "run_step12b_with_cycle_local_context",
]
