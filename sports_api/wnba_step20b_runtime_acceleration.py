"""WNBA Step20B: cycle-local reuse for expensive observed game context.

Step20B diagnostics proved that Step4V repeatedly rebuilds player-independent
Step4R/Step4T game context while Step12B assembles multiple player projections.
This compatibility layer memoizes only exact function outputs inside one active
Step12B call. Every stored value and cache hit is deep-copied, exceptions are
never cached, and the entire memo is discarded when the call exits.

No projection math, readiness rule, simulation count, provider transport,
sportsbook behavior, persistence behavior, or wagering capability is changed.
"""
from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from datetime import datetime, timezone
import threading
import time
from typing import Any, Callable

from sports_api import wnba_event_lineup_context as event_lineup
from sports_api import wnba_player_event_features as event_features
from sports_api import wnba_rotation_context as rotation
from sports_api import wnba_step12b_live_runtime_assembly as step12b

SOURCE = "Kyre Sports API WNBA Step20B cycle-local observed-context acceleration"
MODEL_VERSION = "wnba_step20b_cycle_local_observed_context_v1"

_ORIGINAL_GAME_ROTATION = rotation.get_game_rotation
_ORIGINAL_EVENT_LINEUP_ROTATION = event_lineup.get_game_rotation
_ORIGINAL_EVENT_SOURCES = event_lineup._sources
_ORIGINAL_PLAYER_EVENT_LINEUPS = event_features.get_game_event_lineups
_ORIGINAL_PLAYER_POSSESSIONS = event_features.get_game_possession_event_context
_UPSTREAM_RUN_STEP12B: Callable[..., Any] | None = None

_LOCK = threading.RLock()
_INSTALLED = False
_CYCLE_COUNT = 0
_LAST_CYCLE: dict[str, Any] | None = None

_ACTIVE_CACHE: ContextVar[dict[str, Any] | None] = ContextVar(
    "wnba_step20b_active_observed_context_cache",
    default=None,
)

_CACHE_NAMES = ("rotation", "sources", "event_lineups", "possessions")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_cache() -> dict[str, Any]:
    return {
        "rotation": {},
        "sources": {},
        "event_lineups": {},
        "possessions": {},
        "stats": {
            name: {"hits": 0, "misses": 0}
            for name in _CACHE_NAMES
        },
    }


def _record(cache: dict[str, Any], name: str, outcome: str) -> None:
    stats = cache["stats"][name]
    stats[outcome] = int(stats.get(outcome, 0)) + 1


def _cached_call(
    *,
    cache_name: str,
    key: tuple[Any, ...],
    upstream: Callable[[], Any],
) -> Any:
    cache = _ACTIVE_CACHE.get()
    if cache is None:
        return upstream()
    bucket = cache[cache_name]
    if key in bucket:
        _record(cache, cache_name, "hits")
        return deepcopy(bucket[key])
    # Exceptions deliberately escape without creating a cache entry.
    value = upstream()
    bucket[key] = deepcopy(value)
    _record(cache, cache_name, "misses")
    return deepcopy(bucket[key])


def get_game_rotation_step20b(
    game_id: str,
    season: int,
    *,
    rotation_stat: str = "PLAYER_PTS",
) -> dict[str, Any]:
    key = (str(game_id), int(season), str(rotation_stat))
    return _cached_call(
        cache_name="rotation",
        key=key,
        upstream=lambda: _ORIGINAL_GAME_ROTATION(
            game_id,
            season,
            rotation_stat=rotation_stat,
        ),
    )


def get_event_sources_step20b(game_id: str, season: int):
    key = (str(game_id), int(season))
    return _cached_call(
        cache_name="sources",
        key=key,
        upstream=lambda: _ORIGINAL_EVENT_SOURCES(game_id, season),
    )


def get_game_event_lineups_step20b(
    game_id: str,
    season: int,
    *,
    event_category: str = "All",
    limit: int = 0,
) -> dict[str, Any]:
    key = (str(game_id), int(season), str(event_category), int(limit))
    return _cached_call(
        cache_name="event_lineups",
        key=key,
        upstream=lambda: _ORIGINAL_PLAYER_EVENT_LINEUPS(
            game_id,
            season,
            event_category=event_category,
            limit=limit,
        ),
    )


def get_game_possession_event_context_step20b(
    game_id: str,
    season: int,
    *,
    limit: int = 0,
) -> dict[str, Any]:
    key = (str(game_id), int(season), int(limit))
    return _cached_call(
        cache_name="possessions",
        key=key,
        upstream=lambda: _ORIGINAL_PLAYER_POSSESSIONS(
            game_id,
            season,
            limit=limit,
        ),
    )


def cache_stats(cache: Mapping[str, Any] | None = None) -> dict[str, Any]:
    source = cache if cache is not None else _ACTIVE_CACHE.get()
    if not isinstance(source, Mapping):
        return {
            "active": False,
            "entries": {name: 0 for name in _CACHE_NAMES},
            "stats": {name: {"hits": 0, "misses": 0} for name in _CACHE_NAMES},
        }
    return {
        "active": True,
        "entries": {
            name: len(source.get(name) or {})
            for name in _CACHE_NAMES
        },
        "stats": deepcopy(dict(source.get("stats") or {})),
    }


@contextmanager
def cycle_local_cache_scope() -> Iterator[dict[str, Any]]:
    """Activate one private cache; nested callers reuse the same exact scope."""
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


def run_step12b_with_observed_context_cache(*args: Any, **kwargs: Any) -> Any:
    upstream = _UPSTREAM_RUN_STEP12B
    if upstream is None:
        raise RuntimeError("Step20B runtime acceleration is not installed.")

    global _CYCLE_COUNT, _LAST_CYCLE
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


def install_step20b_runtime_acceleration() -> dict[str, Any]:
    """Install identity-safe wrappers after Step19N and before Step20B tracing."""
    global _INSTALLED, _UPSTREAM_RUN_STEP12B

    expected = (
        (rotation, "get_game_rotation", _ORIGINAL_GAME_ROTATION, get_game_rotation_step20b),
        (event_lineup, "get_game_rotation", _ORIGINAL_EVENT_LINEUP_ROTATION, get_game_rotation_step20b),
        (event_lineup, "_sources", _ORIGINAL_EVENT_SOURCES, get_event_sources_step20b),
        (event_features, "get_game_event_lineups", _ORIGINAL_PLAYER_EVENT_LINEUPS, get_game_event_lineups_step20b),
        (event_features, "get_game_possession_event_context", _ORIGINAL_PLAYER_POSSESSIONS, get_game_possession_event_context_step20b),
    )
    for module, attr, original, target in expected:
        current = getattr(module, attr)
        if current not in {original, target}:
            raise RuntimeError(f"Step20B refuses unknown override for {module.__name__}.{attr}.")

    current_run = step12b.run_step12b_live_runtime_job
    if current_run is not run_step12b_with_observed_context_cache:
        if _UPSTREAM_RUN_STEP12B is not None and current_run is not _UPSTREAM_RUN_STEP12B:
            raise RuntimeError("Step20B refuses unknown Step12B runtime override.")
        _UPSTREAM_RUN_STEP12B = current_run
        step12b.run_step12b_live_runtime_job = run_step12b_with_observed_context_cache

    for module, attr, _, target in expected:
        setattr(module, attr, target)

    _INSTALLED = True
    return installation_status()


def installation_status() -> dict[str, Any]:
    with _LOCK:
        last_cycle = deepcopy(_LAST_CYCLE)
        cycles = int(_CYCLE_COUNT)
    bindings = {
        "rotation_module": rotation.get_game_rotation is get_game_rotation_step20b,
        "event_lineup_rotation_alias": event_lineup.get_game_rotation is get_game_rotation_step20b,
        "event_lineup_sources": event_lineup._sources is get_event_sources_step20b,
        "player_event_lineups": event_features.get_game_event_lineups is get_game_event_lineups_step20b,
        "player_possessions": event_features.get_game_possession_event_context is get_game_possession_event_context_step20b,
        "step12b_wrapper": step12b.run_step12b_live_runtime_job is run_step12b_with_observed_context_cache,
    }
    return {
        "data_type": "wnba_step20b_runtime_acceleration_status",
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
            "nested_scope_reuses_same_cache": True,
            "cache_cleared_after_every_cycle": True,
            "cached_values_returned_by_deepcopy": True,
            "exceptions_cached": False,
            "projection_math_modified": False,
            "readiness_relaxed": False,
            "monte_carlo_simulation_count_modified": False,
            "monte_carlo_batch_size_modified": False,
            "sportsbook_transport_modified": False,
            "provider_identity_protected_step7g_aliases_modified": False,
            "persistence_modified": False,
            "wagering_enabled": False,
        },
    }


__all__ = [
    "MODEL_VERSION",
    "SOURCE",
    "cache_stats",
    "cycle_local_cache_scope",
    "get_event_sources_step20b",
    "get_game_event_lineups_step20b",
    "get_game_possession_event_context_step20b",
    "get_game_rotation_step20b",
    "install_step20b_runtime_acceleration",
    "installation_status",
    "run_step12b_with_observed_context_cache",
]
