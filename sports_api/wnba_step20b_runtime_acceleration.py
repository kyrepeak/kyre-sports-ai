"""WNBA Step20B: cycle-local reuse and bounded cold-path acceleration.

Step20B diagnostics proved two separate costs inside the first Step4V player
opportunity build:

1. Step4R fetched each recent historical game rotation serially. A single direct
   Stats transport timeout therefore multiplied across the five-game window
   before the first projection could advance.
2. Step4U then walked the same historical window serially for event/floor
   features, and first-party fallback could request the same WNBA game page once
   for box-score data and again immediately for play-by-play because those
   surfaces use different cache TTLs.

This compatibility layer keeps the frozen functions authoritative. It performs
bounded (maximum three-worker) best-effort prefetches only inside one active
Step12B call, stores only successful exact outputs, and then invokes the original
Step4R/Step4U functions unchanged. The originals therefore preserve validation,
row ordering, missing-game behavior, aggregation, and exception semantics while
reading the exact prefetched values from the cycle-local cache. Worker threads
receive a copy of the active ContextVar so the cache remains cycle-local.

A freshly fetched WNBA.com page may also be shared across TTL surfaces only while
its age satisfies the *requesting* surface's TTL. An older upstream cache hit is
never promoted across TTLs. Every stored value and cache hit is deep-copied,
exceptions are never cached, and the entire memo is discarded when Step12B exits.

No projection math, readiness rule, simulation count, upstream timeout value,
sportsbook behavior, persistence behavior, or wagering capability is changed.
"""
from __future__ import annotations

from collections.abc import Iterator, Mapping
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from contextvars import ContextVar, copy_context
from copy import deepcopy
from datetime import datetime, timezone
import threading
import time
from typing import Any, Callable

from sports_api import wnba_event_lineup_context as event_lineup
from sports_api import wnba_player_event_features as event_features
from sports_api import wnba_player_opportunity_context as opportunity
from sports_api import wnba_rotation_context as rotation
from sports_api import wnba_step7g_first_party_history as first_party
from sports_api import wnba_step12b_live_runtime_assembly as step12b

SOURCE = "Kyre Sports API WNBA Step20B bounded cold-path + cycle-local observed-context acceleration"
MODEL_VERSION = "wnba_step20b_bounded_cold_path_observed_context_v2"
PREFETCH_MAX_WORKERS = 3

_ORIGINAL_GAME_ROTATION = rotation.get_game_rotation
_ORIGINAL_EVENT_LINEUP_ROTATION = event_lineup.get_game_rotation
_ORIGINAL_EVENT_SOURCES = event_lineup._sources
_ORIGINAL_PLAYER_EVENT_LINEUPS = event_features.get_game_event_lineups
_ORIGINAL_PLAYER_POSSESSIONS = event_features.get_game_possession_event_context
_ORIGINAL_GAME_PLAYER_EVENT_FEATURES = event_features.get_game_player_event_features
_ORIGINAL_RECENT_ROTATION = rotation.get_player_recent_rotation_context
_ORIGINAL_OPPORTUNITY_RECENT_ROTATION = opportunity.get_player_recent_rotation_context
_ORIGINAL_RECENT_EVENT_FEATURES = event_features.get_player_recent_event_feature_context
_ORIGINAL_OPPORTUNITY_RECENT_EVENT_FEATURES = opportunity.get_player_recent_event_feature_context
_ORIGINAL_FIRST_PARTY_PAGE_PROPS = first_party._request_page_props
_UPSTREAM_RUN_STEP12B: Callable[..., Any] | None = None

_LOCK = threading.RLock()
_INSTALLED = False
_CYCLE_COUNT = 0
_LAST_CYCLE: dict[str, Any] | None = None

_ACTIVE_CACHE: ContextVar[dict[str, Any] | None] = ContextVar(
    "wnba_step20b_active_observed_context_cache",
    default=None,
)

_CACHE_NAMES = (
    "rotation",
    "sources",
    "event_lineups",
    "possessions",
    "game_player_event_features",
    "first_party_page_props",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_cache() -> dict[str, Any]:
    return {
        **{name: {} for name in _CACHE_NAMES},
        "stats": {
            name: {"hits": 0, "misses": 0}
            for name in _CACHE_NAMES
        },
        "prefetch": {
            "rotation_batches": 0,
            "rotation_games_submitted": 0,
            "event_feature_batches": 0,
            "event_feature_games_submitted": 0,
            "max_workers": PREFETCH_MAX_WORKERS,
        },
    }


def _record(cache: dict[str, Any], name: str, outcome: str) -> None:
    stats = cache["stats"][name]
    stats[outcome] = int(stats.get(outcome, 0)) + 1


def _record_prefetch(cache: dict[str, Any], batch_key: str, games_key: str, count: int) -> None:
    with _LOCK:
        prefetch = cache["prefetch"]
        prefetch[batch_key] = int(prefetch.get(batch_key, 0)) + 1
        prefetch[games_key] = int(prefetch.get(games_key, 0)) + int(count)


def _cached_call(
    *,
    cache_name: str,
    key: tuple[Any, ...],
    upstream: Callable[[], Any],
) -> Any:
    cache = _ACTIVE_CACHE.get()
    if cache is None:
        return upstream()

    # The cache object is intentionally shared with copied worker Contexts. Keep
    # read/write/stat mutations synchronized, but never hold the lock across an
    # upstream network call so independent historical games can run in parallel.
    with _LOCK:
        bucket = cache[cache_name]
        if key in bucket:
            _record(cache, cache_name, "hits")
            return deepcopy(bucket[key])

    # Exceptions deliberately escape without creating a cache entry.
    value = upstream()
    stored = deepcopy(value)
    with _LOCK:
        bucket = cache[cache_name]
        if key not in bucket:
            bucket[key] = stored
            _record(cache, cache_name, "misses")
        else:
            # A same-key race is not expected for the unique recent-game fanout,
            # but if it occurs, keep the first successful exact value.
            _record(cache, cache_name, "hits")
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


def get_game_player_event_features_step20b(
    game_id: str,
    season: int,
    *,
    player_id: int | None = None,
) -> dict[str, Any]:
    player_key = None if player_id is None else int(player_id)
    key = (str(game_id), int(season), player_key)
    return _cached_call(
        cache_name="game_player_event_features",
        key=key,
        upstream=lambda: _ORIGINAL_GAME_PLAYER_EVENT_FEATURES(
            game_id,
            season,
            player_id=player_id,
        ),
    )


def request_first_party_page_props_step20b(
    url: str,
    *,
    ttl_seconds: int,
) -> tuple[dict[str, Any], str, bool, int]:
    """Reuse only a fresh page whose age satisfies this caller's own TTL."""
    cache = _ACTIVE_CACHE.get()
    if cache is None:
        return _ORIGINAL_FIRST_PARTY_PAGE_PROPS(url, ttl_seconds=ttl_seconds)

    requested_ttl = int(ttl_seconds)
    now = time.monotonic()
    with _LOCK:
        item = cache["first_party_page_props"].get(str(url))
        if item is not None:
            age = max(0.0, now - float(item["stored_at_monotonic"]))
            if age <= requested_ttl:
                _record(cache, "first_party_page_props", "hits")
                return (
                    deepcopy(item["page_props"]),
                    str(item["retrieved_at_utc"]),
                    True,
                    requested_ttl,
                )

    # Let the frozen Step7G cache/transport decide whether this is an exact-TTL
    # cache hit or a fresh network fetch. Do not cache exceptions.
    result = _ORIGINAL_FIRST_PARTY_PAGE_PROPS(url, ttl_seconds=requested_ttl)
    page_props, retrieved_at_utc, upstream_cache_hit, _ = result

    with _LOCK:
        _record(cache, "first_party_page_props", "misses")
        # A pre-existing Step7G cache hit may already be older than a stricter
        # TTL requested later, so never promote it across TTL surfaces. Only a
        # newly fetched page is safe to share, timestamped at this completion.
        if upstream_cache_hit is False:
            cache["first_party_page_props"][str(url)] = {
                "page_props": deepcopy(page_props),
                "retrieved_at_utc": str(retrieved_at_utc),
                "stored_at_monotonic": time.monotonic(),
            }

    return deepcopy(page_props), str(retrieved_at_utc), bool(upstream_cache_hit), requested_ttl


def _history_game_ids_for_rotation(
    player_id: int,
    season: int,
    *,
    season_type: str,
    last_n_games: int,
    rotation_stat: str,
) -> tuple[list[str], int, str, int, str]:
    """Best-effort copy of only the frozen selector inputs; final logic stays upstream."""
    pid = rotation._player_id(player_id)
    normalized_type = rotation._choice(
        season_type,
        rotation.ALLOWED_SEASON_TYPES,
        "season_type",
    )
    normalized_n = rotation._recent_game_count(last_n_games)
    normalized_stat = rotation._choice(
        rotation_stat,
        rotation.ALLOWED_ROTATION_STATS,
        "rotation_stat",
    )
    history = rotation.get_player_game_log_dataset(
        pid,
        season,
        season_type=normalized_type,
    )
    games = history.get("games")
    if not isinstance(games, list):
        return [], pid, normalized_type, normalized_n, normalized_stat
    ids: list[str] = []
    for row in games[:normalized_n]:
        if not isinstance(row, Mapping):
            continue
        gid = rotation._clean(row.get("game_id"))
        if gid:
            ids.append(gid)
    return ids, pid, normalized_type, normalized_n, normalized_stat


def _history_game_ids_for_event_features(
    player_id: int,
    season: int,
    *,
    season_type: str,
    last_n_games: int,
) -> tuple[list[str], int, str, int]:
    pid = event_features._positive_player_id(player_id)
    normalized_type = event_features._choice(
        season_type,
        event_features.ALLOWED_SEASON_TYPES,
        "season_type",
    )
    normalized_n = event_features._last_n(last_n_games)
    history = event_features.get_player_game_log_dataset(
        pid,
        season,
        season_type=normalized_type,
    )
    games = history.get("games")
    if not isinstance(games, list):
        return [], pid, normalized_type, normalized_n
    ids: list[str] = []
    for row in games[:normalized_n]:
        if not isinstance(row, Mapping):
            continue
        gid = event_features._clean(row.get("game_id"))
        if gid and len(gid) == 10 and gid.isdigit():
            ids.append(gid)
    return ids, pid, normalized_type, normalized_n


def _bounded_prefetch(
    calls: list[tuple[Callable[..., Any], tuple[Any, ...], dict[str, Any]]],
) -> None:
    """Run independent reads concurrently; final frozen caller remains authoritative."""
    if not calls:
        return
    workers = min(PREFETCH_MAX_WORKERS, len(calls))
    futures = []
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="wnba-step20b-prefetch") as pool:
        for function, args, kwargs in calls:
            # ContextVar values are not inherited by new threads. A distinct copy
            # per worker keeps the one cycle-local cache visible without entering
            # the same Context concurrently.
            ctx = copy_context()
            futures.append(pool.submit(ctx.run, function, *args, **kwargs))
        # Consume in original selected-game order. Prefetch failures are never
        # authoritative and are deliberately not cached; the frozen caller below
        # repeats that exact game and owns the real exception semantics.
        for future in futures:
            try:
                future.result()
            except Exception:
                pass


def get_player_recent_rotation_context_step20b(
    player_id: int,
    season: int,
    *,
    season_type: str = "Regular Season",
    last_n_games: int = 5,
    rotation_stat: str = "PLAYER_PTS",
) -> dict[str, Any]:
    cache = _ACTIVE_CACHE.get()
    if cache is not None:
        try:
            ids, _, normalized_type, normalized_n, normalized_stat = _history_game_ids_for_rotation(
                player_id,
                season,
                season_type=season_type,
                last_n_games=last_n_games,
                rotation_stat=rotation_stat,
            )
            if ids:
                _record_prefetch(
                    cache,
                    "rotation_batches",
                    "rotation_games_submitted",
                    len(ids),
                )
                _bounded_prefetch([
                    (
                        rotation.get_game_rotation,
                        (gid, season),
                        {"rotation_stat": normalized_stat},
                    )
                    for gid in ids
                ])
        except Exception:
            # Prefetch is an optimization only. Validation, malformed history,
            # upstream errors and NotFound outcomes are all re-evaluated by the
            # frozen function below exactly as before.
            pass

    return _ORIGINAL_RECENT_ROTATION(
        player_id,
        season,
        season_type=season_type,
        last_n_games=last_n_games,
        rotation_stat=rotation_stat,
    )


def get_player_recent_event_feature_context_step20b(
    player_id: int,
    season: int,
    *,
    season_type: str = "Regular Season",
    last_n_games: int = 5,
) -> dict[str, Any]:
    cache = _ACTIVE_CACHE.get()
    if cache is not None:
        try:
            ids, pid, _, _ = _history_game_ids_for_event_features(
                player_id,
                season,
                season_type=season_type,
                last_n_games=last_n_games,
            )
            if ids:
                _record_prefetch(
                    cache,
                    "event_feature_batches",
                    "event_feature_games_submitted",
                    len(ids),
                )
                _bounded_prefetch([
                    (
                        event_features.get_game_player_event_features,
                        (gid, season),
                        {"player_id": pid},
                    )
                    for gid in ids
                ])
        except Exception:
            pass

    return _ORIGINAL_RECENT_EVENT_FEATURES(
        player_id,
        season,
        season_type=season_type,
        last_n_games=last_n_games,
    )


def cache_stats(cache: Mapping[str, Any] | None = None) -> dict[str, Any]:
    source = cache if cache is not None else _ACTIVE_CACHE.get()
    if not isinstance(source, Mapping):
        return {
            "active": False,
            "entries": {name: 0 for name in _CACHE_NAMES},
            "stats": {name: {"hits": 0, "misses": 0} for name in _CACHE_NAMES},
            "prefetch": {
                "rotation_batches": 0,
                "rotation_games_submitted": 0,
                "event_feature_batches": 0,
                "event_feature_games_submitted": 0,
                "max_workers": PREFETCH_MAX_WORKERS,
            },
        }
    with _LOCK:
        return {
            "active": True,
            "entries": {
                name: len(source.get(name) or {})
                for name in _CACHE_NAMES
            },
            "stats": deepcopy(dict(source.get("stats") or {})),
            "prefetch": deepcopy(dict(source.get("prefetch") or {})),
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
        (event_features, "get_game_player_event_features", _ORIGINAL_GAME_PLAYER_EVENT_FEATURES, get_game_player_event_features_step20b),
        (rotation, "get_player_recent_rotation_context", _ORIGINAL_RECENT_ROTATION, get_player_recent_rotation_context_step20b),
        (opportunity, "get_player_recent_rotation_context", _ORIGINAL_OPPORTUNITY_RECENT_ROTATION, get_player_recent_rotation_context_step20b),
        (event_features, "get_player_recent_event_feature_context", _ORIGINAL_RECENT_EVENT_FEATURES, get_player_recent_event_feature_context_step20b),
        (opportunity, "get_player_recent_event_feature_context", _ORIGINAL_OPPORTUNITY_RECENT_EVENT_FEATURES, get_player_recent_event_feature_context_step20b),
        (first_party, "_request_page_props", _ORIGINAL_FIRST_PARTY_PAGE_PROPS, request_first_party_page_props_step20b),
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
        "game_player_event_features": event_features.get_game_player_event_features is get_game_player_event_features_step20b,
        "recent_rotation_module": rotation.get_player_recent_rotation_context is get_player_recent_rotation_context_step20b,
        "recent_rotation_opportunity_alias": opportunity.get_player_recent_rotation_context is get_player_recent_rotation_context_step20b,
        "recent_event_feature_module": event_features.get_player_recent_event_feature_context is get_player_recent_event_feature_context_step20b,
        "recent_event_feature_opportunity_alias": opportunity.get_player_recent_event_feature_context is get_player_recent_event_feature_context_step20b,
        "first_party_page_props": first_party._request_page_props is request_first_party_page_props_step20b,
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
            "bounded_historical_prefetch": True,
            "historical_prefetch_max_workers": PREFETCH_MAX_WORKERS,
            "frozen_recent_context_functions_remain_authoritative": True,
            "first_party_cross_ttl_reuse_requires_fresh_fetch": True,
            "requesting_surface_ttl_is_respected": True,
            "upstream_timeout_values_modified": False,
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
    "PREFETCH_MAX_WORKERS",
    "SOURCE",
    "cache_stats",
    "cycle_local_cache_scope",
    "get_event_sources_step20b",
    "get_game_event_lineups_step20b",
    "get_game_player_event_features_step20b",
    "get_game_possession_event_context_step20b",
    "get_game_rotation_step20b",
    "get_player_recent_event_feature_context_step20b",
    "get_player_recent_rotation_context_step20b",
    "install_step20b_runtime_acceleration",
    "installation_status",
    "request_first_party_page_props_step20b",
    "run_step12b_with_observed_context_cache",
]
