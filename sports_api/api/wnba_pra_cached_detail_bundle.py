"""WNBA PRA Speed V3 Step 4 — server-side finished-bundle cache.

This layer wraps the frozen Step-3 PRA detail bundle without changing it.
Only complete Step-3 bundles are cached. Cache keys are player + season.
"""
from __future__ import annotations

from collections import OrderedDict
from copy import deepcopy
from threading import Lock
from time import monotonic, perf_counter
from typing import Any, Mapping

from fastapi import APIRouter, Query

from sports_api.api.wnba_pra_detail_bundle import (
    DEFAULT_SEASON,
    DATA_TYPE as STEP3_DATA_TYPE,
    SCHEMA_VERSION as STEP3_SCHEMA_VERSION,
    build_pra_detail_bundle,
)


DATA_TYPE = "wnba_pra_speed_v3_step4_cached_detail_bundle"
SCHEMA_VERSION = "wnba_pra_speed_v3_step4_cached_detail_bundle_v1"
CACHE_TTL_SECONDS = 60
CACHE_MAX_ENTRIES = 256

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


def _complete(bundle: Mapping[str, Any] | None, pid: int, season: int) -> bool:
    if not isinstance(bundle, Mapping):
        return False
    return (
        bundle.get("data_type") == STEP3_DATA_TYPE
        and bundle.get("schema_version") == STEP3_SCHEMA_VERSION
        and int(bundle.get("player_id") or 0) == int(pid)
        and int(bundle.get("season") or 0) == int(season)
        and isinstance(bundle.get("consumer"), Mapping)
        and isinstance(bundle.get("history"), Mapping)
        and not str(bundle.get("consumer_error") or "")
        and not str(bundle.get("history_error") or "")
    )


def _cache_get(key: tuple[int, int]) -> dict[str, Any] | None:
    now = monotonic()
    with _STATE_LOCK:
        item = _CACHE.get(key)
        if not item:
            return None
        if float(item.get("expires_at") or 0.0) <= now:
            _CACHE.pop(key, None)
            return None
        _CACHE.move_to_end(key)
        return deepcopy(item["bundle"])


def _cache_put(key: tuple[int, int], bundle: Mapping[str, Any]) -> None:
    now = monotonic()
    with _STATE_LOCK:
        expired = [
            current
            for current, item in _CACHE.items()
            if float(item.get("expires_at") or 0.0) <= now
        ]
        for current in expired:
            _CACHE.pop(current, None)
        _CACHE[key] = {
            "bundle": deepcopy(dict(bundle)),
            "expires_at": now + CACHE_TTL_SECONDS,
        }
        _CACHE.move_to_end(key)
        while len(_CACHE) > CACHE_MAX_ENTRIES:
            _CACHE.popitem(last=False)


def _key_lock(key: tuple[int, int]) -> Lock:
    with _STATE_LOCK:
        lock = _KEY_LOCKS.get(key)
        if lock is None:
            lock = Lock()
            _KEY_LOCKS[key] = lock
        return lock


def _response(
    *,
    bundle: Mapping[str, Any],
    cache_hit: bool,
    generation_ms: float,
) -> dict[str, Any]:
    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "player_id": int(bundle.get("player_id") or 0),
        "season": int(bundle.get("season") or 0),
        "bundle": deepcopy(dict(bundle)),
        "cache": {
            "hit": bool(cache_hit),
            "ttl_seconds": CACHE_TTL_SECONDS,
            "max_entries": CACHE_MAX_ENTRIES,
            "generation_ms": round(float(generation_ms), 3),
            "single_flight": True,
        },
        "semantics": {
            "frozen_step3_bundle_changed": False,
            "finished_bundle_cached_server_side": True,
            "projection_run_added": False,
            "sportsbook_network_called": False,
            "qualification_run_added": False,
            "ranking_run_added": False,
            "monte_carlo_run_added": False,
            "wager_action_performed": False,
        },
    }


def get_cached_pra_detail_bundle(
    player_id: int,
    season: int = DEFAULT_SEASON,
) -> dict[str, Any]:
    key = _key(player_id, season)
    pid, year = key

    cached = _cache_get(key)
    if cached is not None:
        return _response(bundle=cached, cache_hit=True, generation_ms=0.0)

    # Single-flight identical cold misses. Recheck after taking the per-key lock.
    with _key_lock(key):
        cached = _cache_get(key)
        if cached is not None:
            return _response(bundle=cached, cache_hit=True, generation_ms=0.0)

        started = perf_counter()
        bundle = build_pra_detail_bundle(pid, year)
        generation_ms = (perf_counter() - started) * 1000.0

        if _complete(bundle, pid, year):
            _cache_put(key, bundle)

        return _response(
            bundle=bundle,
            cache_hit=False,
            generation_ms=generation_ms,
        )


@router.get("/players/{player_id}/pra-detail-cached")
def wnba_pra_cached_detail_bundle(
    player_id: int,
    season: int = Query(default=DEFAULT_SEASON, description="WNBA season"),
):
    return get_cached_pra_detail_bundle(player_id, season)


__all__ = [
    "CACHE_MAX_ENTRIES",
    "CACHE_TTL_SECONDS",
    "DATA_TYPE",
    "SCHEMA_VERSION",
    "get_cached_pra_detail_bundle",
    "router",
]
