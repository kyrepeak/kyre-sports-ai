"""WNBA Step 20B: cycle-local shared Step8A input memoization.

Step20A live certification exposed a post-rollover scalability failure: one
Step12B cycle continued making progress player-by-player but could run longer
than the durable scheduler lease. The expensive Step8A input path repeatedly
reconstructed inputs that are identical for several players in the same live
cycle (historical game pages/rotations/event sources and current game
availability).

This compatibility layer is deliberately semantics preserving. It does not edit
or replace any frozen Step7G public provider seam. Instead, while one Step12B
call is active, it memoizes only lower-level shared helper results and always
returns deep copies. Exceptions are never cached. Every memo is discarded in a
``finally`` block when the Step12B call returns or raises.

No player is skipped, no exact-line requirement is changed, and the certified
5,000,000-simulation / 250,000-batch Step8 Monte Carlo contract is untouched.
"""
from __future__ import annotations

from collections.abc import Callable, Mapping
from contextvars import ContextVar
from copy import deepcopy
from datetime import datetime, timezone
import threading
import time
from typing import Any

from sports_api import wnba_player_event_features as event_features
from sports_api import wnba_projection_input_snapshot as projection_snapshot
from sports_api import wnba_rotation_context as rotation
from sports_api import wnba_step12b_live_runtime_assembly as step12b
from sports_api import wnba_step19n_fanduel_empty_market as step19n
from sports_api import wnba_step7g_first_party_history as first_history

SOURCE = "Kyre Sports API WNBA Step20B cycle-local shared Step8A input cache"
MODEL_VERSION = "wnba_step20b_cycle_local_shared_step8a_inputs_v1"

_ORIGINAL_REQUEST_PAGE_PROPS = first_history._request_page_props
_ORIGINAL_GAME_ROTATION = rotation.get_game_rotation
_ORIGINAL_GAME_SOURCES = event_features._game_sources
_ORIGINAL_GAME_AVAILABILITY = projection_snapshot.get_game_availability_context_dataset

_UPSTREAM_RUN_STEP12B: Callable[..., Any] | None = None
_INSTALLED = False
_LOCK = threading.RLock()

_ACTIVE_CACHE: ContextVar[dict[str, dict[Any, Any]] | None] = ContextVar(
    "wnba_step20b_active_shared_input_cache", default=None
)

_CYCLE_COUNT = 0
_TOTAL_HITS = {
    "page_props": 0,
    "game_rotation": 0,
    "game_sources": 0,
    "game_availability": 0,
}
_TOTAL_MISSES = {
    "page_props": 0,
    "game_rotation": 0,
    "game_sources": 0,
    "game_availability": 0,
}
_LAST_CYCLE: dict[str, Any] | None = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _cache_bucket(name: str) -> dict[Any, Any] | None:
    active = _ACTIVE_CACHE.get()
    if active is None:
        return None
    return active[name]


def _hit(name: str) -> None:
    with _LOCK:
        _TOTAL_HITS[name] += 1


def _miss(name: str) -> None:
    with _LOCK:
        _TOTAL_MISSES[name] += 1


def request_page_props_step20b(
    url: str,
    *,
    ttl_seconds: int,
) -> tuple[dict[str, Any], str, bool, int]:
    """Reuse one exact WNBA.com page payload inside the active Step12B call.

    The page URL is the immutable source locator for the cycle snapshot. A
    second consumer (for example box score vs play-by-play) may request a
    different source TTL; the returned TTL always remains the caller's requested
    TTL while the original retrieval timestamp and page payload are reused.
    """
    cache = _cache_bucket("page_props")
    if cache is None:
        return _ORIGINAL_REQUEST_PAGE_PROPS(url, ttl_seconds=ttl_seconds)

    key = str(url)
    if key in cache:
        _hit("page_props")
        page_props, retrieved_at_utc = cache[key]
        return deepcopy(page_props), str(retrieved_at_utc), True, int(ttl_seconds)

    # Exceptions intentionally escape and are never memoized.
    page_props, retrieved_at_utc, cache_hit, returned_ttl = _ORIGINAL_REQUEST_PAGE_PROPS(
        url,
        ttl_seconds=ttl_seconds,
    )
    if not isinstance(page_props, Mapping):
        return page_props, retrieved_at_utc, cache_hit, returned_ttl
    cache[key] = (deepcopy(dict(page_props)), str(retrieved_at_utc))
    _miss("page_props")
    return deepcopy(dict(page_props)), retrieved_at_utc, cache_hit, returned_ttl


def get_game_rotation_step20b(
    game_id: str,
    season: int,
    *,
    rotation_stat: str = "PLAYER_PTS",
) -> dict[str, Any]:
    """Memoize a full historical game rotation within one Step12B call."""
    cache = _cache_bucket("game_rotation")
    if cache is None:
        return _ORIGINAL_GAME_ROTATION(
            game_id,
            season,
            rotation_stat=rotation_stat,
        )
    key = (str(game_id), int(season), str(rotation_stat))
    if key in cache:
        _hit("game_rotation")
        return deepcopy(cache[key])
    value = _ORIGINAL_GAME_ROTATION(
        game_id,
        season,
        rotation_stat=rotation_stat,
    )
    if not isinstance(value, Mapping):
        return value
    cache[key] = deepcopy(dict(value))
    _miss("game_rotation")
    return deepcopy(cache[key])


def game_sources_step20b(
    game_id: str,
    season: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Memoize Step4T event-lineup + possession sources per historical game."""
    cache = _cache_bucket("game_sources")
    if cache is None:
        return _ORIGINAL_GAME_SOURCES(game_id, season)
    key = (str(game_id), int(season))
    if key in cache:
        _hit("game_sources")
        events, possessions = cache[key]
        return deepcopy(events), deepcopy(possessions)
    value = _ORIGINAL_GAME_SOURCES(game_id, season)
    if (
        not isinstance(value, tuple)
        or len(value) != 2
        or not isinstance(value[0], Mapping)
        or not isinstance(value[1], Mapping)
    ):
        return value
    cache[key] = (deepcopy(dict(value[0])), deepcopy(dict(value[1])))
    _miss("game_sources")
    events, possessions = cache[key]
    return deepcopy(events), deepcopy(possessions)


def get_game_availability_context_dataset_step20b(
    game_id: str,
    target_date: str,
    season: int,
    *,
    last_n_games: int = 5,
    report_url: str | None = None,
    lookback_hours: int = 36,
) -> dict[str, Any]:
    """Memoize the exact two-team current-game availability package per cycle."""
    cache = _cache_bucket("game_availability")
    if cache is None:
        return _ORIGINAL_GAME_AVAILABILITY(
            game_id,
            target_date,
            season,
            last_n_games=last_n_games,
            report_url=report_url,
            lookback_hours=lookback_hours,
        )
    key = (
        str(game_id),
        str(target_date),
        int(season),
        int(last_n_games),
        None if report_url is None else str(report_url),
        int(lookback_hours),
    )
    if key in cache:
        _hit("game_availability")
        return deepcopy(cache[key])
    value = _ORIGINAL_GAME_AVAILABILITY(
        game_id,
        target_date,
        season,
        last_n_games=last_n_games,
        report_url=report_url,
        lookback_hours=lookback_hours,
    )
    if not isinstance(value, Mapping):
        return value
    cache[key] = deepcopy(dict(value))
    _miss("game_availability")
    return deepcopy(cache[key])


def run_step12b_with_shared_input_cache(*args: Any, **kwargs: Any) -> Any:
    """Execute the already-installed Step12B chain with fresh shared-input memos."""
    upstream = _UPSTREAM_RUN_STEP12B
    if upstream is None:
        raise RuntimeError("Step20B shared-input cache is not installed.")

    token = _ACTIVE_CACHE.set(
        {
            "page_props": {},
            "game_rotation": {},
            "game_sources": {},
            "game_availability": {},
        }
    )
    started = time.perf_counter()
    with _LOCK:
        global _CYCLE_COUNT
        _CYCLE_COUNT += 1
        cycle_number = _CYCLE_COUNT
        start_hits = dict(_TOTAL_HITS)
        start_misses = dict(_TOTAL_MISSES)

    status = "returned"
    error_type: str | None = None
    try:
        return upstream(*args, **kwargs)
    except Exception as exc:
        status = "raised"
        error_type = type(exc).__name__
        raise
    finally:
        active = _ACTIVE_CACHE.get() or {}
        elapsed = time.perf_counter() - started
        with _LOCK:
            global _LAST_CYCLE
            cycle_hits = {
                name: _TOTAL_HITS[name] - start_hits[name]
                for name in _TOTAL_HITS
            }
            cycle_misses = {
                name: _TOTAL_MISSES[name] - start_misses[name]
                for name in _TOTAL_MISSES
            }
            _LAST_CYCLE = {
                "cycle_number": cycle_number,
                "finished_at_utc": _now(),
                "status": status,
                "error_type": error_type,
                "elapsed_seconds": round(elapsed, 3),
                "cache_entries": {
                    name: len(active.get(name, {})) for name in _TOTAL_HITS
                },
                "hits": cycle_hits,
                "misses": cycle_misses,
                "total_hits": sum(cycle_hits.values()),
                "total_misses": sum(cycle_misses.values()),
            }
        _ACTIVE_CACHE.reset(token)


def install_step20b_shared_input_cache() -> dict[str, Any]:
    """Install after Step19N so Step20B is the outermost Step12B wrapper."""
    global _INSTALLED, _UPSTREAM_RUN_STEP12B

    helper_seams = (
        (
            "WNBA.com page-props helper",
            first_history,
            "_request_page_props",
            _ORIGINAL_REQUEST_PAGE_PROPS,
            request_page_props_step20b,
        ),
        (
            "full game rotation helper",
            rotation,
            "get_game_rotation",
            _ORIGINAL_GAME_ROTATION,
            get_game_rotation_step20b,
        ),
        (
            "Step4U game sources helper",
            event_features,
            "_game_sources",
            _ORIGINAL_GAME_SOURCES,
            game_sources_step20b,
        ),
        (
            "Step4W game availability helper",
            projection_snapshot,
            "get_game_availability_context_dataset",
            _ORIGINAL_GAME_AVAILABILITY,
            get_game_availability_context_dataset_step20b,
        ),
    )
    for label, module, attribute, original, target in helper_seams:
        current = getattr(module, attribute)
        if current not in {original, target}:
            raise RuntimeError(
                f"Step20B refuses to replace an unknown {label} override."
            )

    current_run = step12b.run_step12b_live_runtime_job
    if current_run is run_step12b_with_shared_input_cache:
        _INSTALLED = True
        return installation_status()
    if current_run is not step19n.run_step12b_fanduel_empty_market_compatible:
        raise RuntimeError(
            "Step20B requires the certified Step19N wrapper to be outermost before installation."
        )
    if _UPSTREAM_RUN_STEP12B is not None and current_run is not _UPSTREAM_RUN_STEP12B:
        raise RuntimeError("Step20B refuses to replace an unknown Step12B runtime override.")

    _UPSTREAM_RUN_STEP12B = current_run
    first_history._request_page_props = request_page_props_step20b
    rotation.get_game_rotation = get_game_rotation_step20b
    event_features._game_sources = game_sources_step20b
    projection_snapshot.get_game_availability_context_dataset = (
        get_game_availability_context_dataset_step20b
    )
    step12b.run_step12b_live_runtime_job = run_step12b_with_shared_input_cache
    _INSTALLED = True
    return installation_status()


def installation_status() -> dict[str, Any]:
    with _LOCK:
        hits = dict(_TOTAL_HITS)
        misses = dict(_TOTAL_MISSES)
        latest = deepcopy(_LAST_CYCLE)
        cycle_count = int(_CYCLE_COUNT)
    return {
        "data_type": "wnba_step20b_shared_input_cache_status",
        "source": SOURCE,
        "model_version": MODEL_VERSION,
        "generated_at_utc": _now(),
        "installed": _INSTALLED,
        "step12b_wrapper_active": (
            step12b.run_step12b_live_runtime_job is run_step12b_with_shared_input_cache
        ),
        "upstream_step19n_preserved": (
            _UPSTREAM_RUN_STEP12B is step19n.run_step12b_fanduel_empty_market_compatible
        ),
        "helper_seams": {
            "page_props": first_history._request_page_props is request_page_props_step20b,
            "game_rotation": rotation.get_game_rotation is get_game_rotation_step20b,
            "game_sources": event_features._game_sources is game_sources_step20b,
            "game_availability": (
                projection_snapshot.get_game_availability_context_dataset
                is get_game_availability_context_dataset_step20b
            ),
        },
        "cycle_count": cycle_count,
        "total_hits": hits,
        "total_misses": misses,
        "last_cycle": latest,
        "guardrails": {
            "cache_scope": "single_step12b_call_only",
            "cache_cleared_after_every_cycle": True,
            "cached_values_returned_by_deepcopy": True,
            "exceptions_cached": False,
            "frozen_step7g_public_provider_seams_modified": False,
            "player_coverage_modified": False,
            "exact_line_matching_modified": False,
            "different_lines_blended": False,
            "monte_carlo_simulation_count_modified": False,
            "monte_carlo_batch_size_modified": False,
            "projection_math_modified": False,
            "readiness_relaxed": False,
            "sportsbook_transport_modified": False,
            "controller_state_modified": False,
            "durable_lease_policy_modified": False,
            "persistence_modified": False,
            "wagering_enabled": False,
        },
    }


__all__ = [
    "MODEL_VERSION",
    "SOURCE",
    "game_sources_step20b",
    "get_game_availability_context_dataset_step20b",
    "get_game_rotation_step20b",
    "install_step20b_shared_input_cache",
    "installation_status",
    "request_page_props_step20b",
    "run_step12b_with_shared_input_cache",
]
