"""WNBA PRA Speed V3 Step 6 — smarter/longer player-history cache.

This layer wraps the frozen Step-5 fast-history transport. It does not change
the Step-3 ESPN history parser or any model/projection/market behavior.

Policy:
- key = (player_id, season)
- active/current season TTL = 10 minutes
- historical season TTL = 6 hours
- bounded LRU with per-key single-flight
- cache only complete, identity-valid history payloads
- caller receives deep copies of cached history
"""
from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from threading import Lock
from time import monotonic, perf_counter
from typing import Any, Mapping

from fastapi import APIRouter, Query

from sports_api.api.wnba_pra_detail_bundle import DEFAULT_SEASON
from sports_api.api.wnba_pra_speed_v3_step5_fast_history import (
    DATA_TYPE as STEP5_DATA_TYPE,
    SCHEMA_VERSION as STEP5_SCHEMA_VERSION,
    get_fast_pra_history,
)

DATA_TYPE = "wnba_pra_speed_v3_step6_history_cache"
SCHEMA_VERSION = "wnba_pra_speed_v3_step6_history_cache_v1"

ACTIVE_SEASON_TTL_SECONDS = 600
HISTORICAL_SEASON_TTL_SECONDS = 21600
CACHE_MAX_ENTRIES = 512

router = APIRouter(prefix="/api/v1/wnba", tags=["wnba-pra-speed-v3"])

_CACHE: "OrderedDict[tuple[int, int], dict[str, Any]]" = OrderedDict()
_KEY_LOCKS: dict[tuple[int, int], Lock] = {}
_STATE_LOCK = Lock()


def _key(player_id: int, season: int) -> tuple[int, int]:
    pid = int(player_id)
    year = int(season)
    if pid <= 0:
        raise ValueError("player_id must be positive.")
    if year < 1997 or year > 2100:
        raise ValueError("season is outside the supported WNBA range.")
    return pid, year


def _ttl_for_season(season: int) -> int:
    year = int(season)
    if year < int(DEFAULT_SEASON):
        return HISTORICAL_SEASON_TTL_SECONDS
    return ACTIVE_SEASON_TTL_SECONDS


def _valid_history(history: Any, *, player_id: int, season: int) -> bool:
    if not isinstance(history, Mapping):
        return False
    try:
        payload_pid = int(history.get("player_id") or 0)
        payload_season = int(history.get("season") or 0)
    except (TypeError, ValueError):
        return False
    games = history.get("games")
    return (
        payload_pid == int(player_id)
        and payload_season == int(season)
        and isinstance(games, list)
    )


def _valid_step5_source(payload: Any, *, player_id: int, season: int) -> bool:
    if not isinstance(payload, Mapping):
        return False
    try:
        pid = int(payload.get("player_id") or 0)
        year = int(payload.get("season") or 0)
    except (TypeError, ValueError):
        return False
    return (
        payload.get("data_type") == STEP5_DATA_TYPE
        and payload.get("schema_version") == STEP5_SCHEMA_VERSION
        and pid == int(player_id)
        and year == int(season)
        and _valid_history(
            payload.get("history"),
            player_id=player_id,
            season=season,
        )
    )


def _key_lock(key: tuple[int, int]) -> Lock:
    with _STATE_LOCK:
        lock = _KEY_LOCKS.get(key)
        if lock is None:
            lock = Lock()
            _KEY_LOCKS[key] = lock
        return lock


def _prune(now: float) -> None:
    expired = [
        key
        for key, item in _CACHE.items()
        if float(item.get("expires_at") or 0.0) <= now
    ]
    for key in expired:
        _CACHE.pop(key, None)
    while len(_CACHE) > CACHE_MAX_ENTRIES:
        _CACHE.popitem(last=False)


def _cache_get(
    key: tuple[int, int],
) -> tuple[dict[str, Any], float, int] | None:
    now = monotonic()
    with _STATE_LOCK:
        _prune(now)
        item = _CACHE.get(key)
        if not item:
            return None
        expires_at = float(item.get("expires_at") or 0.0)
        if expires_at <= now:
            _CACHE.pop(key, None)
            return None
        _CACHE.move_to_end(key)
        inserted_at = float(item.get("inserted_at") or now)
        ttl = int(item.get("ttl_seconds") or _ttl_for_season(key[1]))
        age_ms = max(0.0, (now - inserted_at) * 1000.0)
        return deepcopy(item["history"]), age_ms, ttl


def _cache_put(
    key: tuple[int, int],
    history: Mapping[str, Any],
) -> int:
    now = monotonic()
    ttl = _ttl_for_season(key[1])
    with _STATE_LOCK:
        _prune(now)
        _CACHE[key] = {
            "history": deepcopy(dict(history)),
            "inserted_at": now,
            "expires_at": now + ttl,
            "ttl_seconds": ttl,
        }
        _CACHE.move_to_end(key)
        _prune(now)
    return ttl


def _response(
    *,
    player_id: int,
    season: int,
    history: Mapping[str, Any],
    cache_hit: bool,
    cache_age_ms: float,
    ttl_seconds: int,
    generation_ms: float,
) -> dict[str, Any]:
    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "player_id": int(player_id),
        "season": int(season),
        "history": deepcopy(dict(history)),
        "cache": {
            "hit": bool(cache_hit),
            "age_ms": round(float(cache_age_ms), 3),
            "ttl_seconds": int(ttl_seconds),
            "max_entries": CACHE_MAX_ENTRIES,
            "single_flight": True,
            "generation_ms": round(float(generation_ms), 3),
        },
        "semantics": {
            "consumer_snapshot_read": False,
            "frozen_step5_history_transport_reused": True,
            "frozen_step3_history_transport_reused": True,
            "step6_longer_history_cache": True,
            "projection_run": False,
            "sportsbook_network_called": False,
            "qualification_run": False,
            "ranking_run": False,
            "monte_carlo_run": False,
            "wager_action_performed": False,
        },
    }


def get_cached_pra_history(
    player_id: int,
    season: int = DEFAULT_SEASON,
) -> dict[str, Any]:
    key = _key(player_id, season)
    pid, year = key

    cached = _cache_get(key)
    if cached is not None:
        history, age_ms, ttl = cached
        return _response(
            player_id=pid,
            season=year,
            history=history,
            cache_hit=True,
            cache_age_ms=age_ms,
            ttl_seconds=ttl,
            generation_ms=0.0,
        )

    with _key_lock(key):
        cached = _cache_get(key)
        if cached is not None:
            history, age_ms, ttl = cached
            return _response(
                player_id=pid,
                season=year,
                history=history,
                cache_hit=True,
                cache_age_ms=age_ms,
                ttl_seconds=ttl,
                generation_ms=0.0,
            )

        started = perf_counter()
        source = get_fast_pra_history(pid, year)
        generation_ms = (perf_counter() - started) * 1000.0

        if not _valid_step5_source(source, player_id=pid, season=year):
            raise ValueError("Frozen Step-5 fast-history source returned an invalid payload.")

        history = source["history"]
        ttl = _cache_put(key, history)
        return _response(
            player_id=pid,
            season=year,
            history=history,
            cache_hit=False,
            cache_age_ms=0.0,
            ttl_seconds=ttl,
            generation_ms=generation_ms,
        )


@router.get("/players/{player_id}/pra-history-cached")
def wnba_pra_speed_v3_step6_history_cache(
    player_id: int,
    season: int = Query(default=DEFAULT_SEASON, description="WNBA season"),
):
    return get_cached_pra_history(player_id, season)


__all__ = [
    "ACTIVE_SEASON_TTL_SECONDS",
    "CACHE_MAX_ENTRIES",
    "DATA_TYPE",
    "HISTORICAL_SEASON_TTL_SECONDS",
    "SCHEMA_VERSION",
    "get_cached_pra_history",
    "router",
]
