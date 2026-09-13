"""Kyre Sports API — NFL Rushing Yards verified post-projection market endpoint.

The endpoint exposes only fresh exact-ID sportsbook context. It does not
calculate or modify projections, probabilities, fair odds, EV, grades, stake
sizes, rankings, recommendations, or wager actions.

A very short exact-event in-process snapshot avoids rebuilding the same active
FanDuel market repeatedly across cold Streamlit sessions. The provider capture
timestamp is preserved and the full market safety/identity contract is re-run
on every cache hit. The downstream client keeps the independent 300-second
absolute market-freshness firewall.
"""
from __future__ import annotations

from copy import deepcopy
import threading
from time import monotonic
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from sports_api.collectors.nfl_fanduel_rushing_yards_v2 import (
    NFLRushingYardsCollectorError,
    SCHEMA_VERSION,
    collect_fanduel_nfl_rushing_yards_hosted,
)

router = APIRouter(prefix="/api/v1/nfl/rushing-yards/market", tags=["nfl-rushing-yards-market"])

MARKET_SNAPSHOT_TTL_SECONDS = 10.0
_CACHE_LOCK = threading.RLock()
_MARKET_SNAPSHOT_CACHE: dict[str, tuple[float, int, dict[str, Any]]] = {}
_EVENT_LOCKS: dict[str, threading.Lock] = {}

CONTRACT = {
    "schema_version": SCHEMA_VERSION,
    "provider": "FanDuel",
    "transport": "anonymous_public_get_only",
    "official_authority": "ESPN",
    "official_event_id_required": True,
    "official_athlete_id_required": True,
    "official_team_id_required": True,
    "player_name_display_only": True,
    "player_name_matching": False,
    "fuzzy_matching": False,
    "synthetic_event_ids": False,
    "synthetic_player_ids": False,
    "projection_weight": 0.0,
    "market_context_only": True,
    "may_modify_projection": False,
    "probability_enabled": False,
    "fair_odds_enabled": False,
    "ev_enabled": False,
    "grading_enabled": False,
    "stake_sizing_enabled": False,
    "wager_actions": False,
}


def _validate_market_payload(payload: dict[str, Any], event_id: str) -> dict[str, Any]:
    """Re-run the frozen market identity/safety contract for every response."""
    if not isinstance(payload, dict):
        raise HTTPException(status_code=503, detail="NFL Rushing Yards market payload is invalid")

    identity = payload.get("identity") or {}
    semantics = payload.get("market_semantics") or {}
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise HTTPException(status_code=503, detail="NFL Rushing Yards market schema contract mismatch")
    if str(payload.get("official_event_id") or "") != event_id:
        raise HTTPException(status_code=503, detail="NFL Rushing Yards market official event identity mismatch")
    if (
        identity.get("player_name_matching") is not False
        or identity.get("fuzzy_matching") is not False
        or identity.get("synthetic_event_ids") is not False
        or identity.get("synthetic_player_ids") is not False
        or semantics.get("projection_weight") != 0.0
        or semantics.get("market_context_only") is not True
        or semantics.get("may_modify_projection") is not False
        or semantics.get("probability_enabled") is not False
        or semantics.get("fair_odds_enabled") is not False
        or semantics.get("ev_enabled") is not False
        or semantics.get("grading_enabled") is not False
        or semantics.get("stake_sizing_enabled") is not False
        or semantics.get("wager_actions") is not False
    ):
        raise HTTPException(status_code=503, detail="NFL Rushing Yards Step 4 market safety contract failed closed")

    seen_athletes: set[str] = set()
    for row in payload.get("props") or []:
        if not isinstance(row, dict):
            raise HTTPException(status_code=503, detail="NFL Rushing Yards market row identity contract failed closed")
        athlete_id = str(row.get("official_athlete_id") or "").strip()
        team_id = str(row.get("official_team_id") or "").strip()
        row_event_id = str(row.get("official_event_id") or "").strip()
        if (
            row_event_id != event_id
            or not athlete_id.isdigit()
            or not team_id.isdigit()
            or athlete_id in seen_athletes
            or str(row.get("market_type") or "").strip().lower() != "rushing_yards"
            or str(row.get("sportsbook") or "").strip().lower() != "fanduel"
            or str(row.get("line_status") or "").strip().lower() != "active"
        ):
            raise HTTPException(status_code=503, detail="NFL Rushing Yards market row identity contract failed closed")
        seen_athletes.add(athlete_id)
    return payload


def _collector_identity() -> int:
    return id(collect_fanduel_nfl_rushing_yards_hosted)


def _cache_get(event_id: str, now: float | None = None) -> dict[str, Any] | None:
    stamp = monotonic() if now is None else float(now)
    collector_id = _collector_identity()
    with _CACHE_LOCK:
        entry = _MARKET_SNAPSHOT_CACHE.get(event_id)
        if entry is None:
            return None
        expires_at, stored_collector_id, payload = entry
        if expires_at <= stamp or stored_collector_id != collector_id:
            _MARKET_SNAPSHOT_CACHE.pop(event_id, None)
            return None
        return deepcopy(payload)


def _cache_put(event_id: str, payload: dict[str, Any], now: float | None = None) -> None:
    # Cache active canonical markets only. A currently unavailable market is
    # deliberately retried on the very next request so a newly posted line is
    # never hidden behind the speed layer.
    if payload.get("ready") is not True or payload.get("market_available") is not True:
        return
    stamp = monotonic() if now is None else float(now)
    with _CACHE_LOCK:
        _MARKET_SNAPSHOT_CACHE[event_id] = (
            stamp + MARKET_SNAPSHOT_TTL_SECONDS,
            _collector_identity(),
            deepcopy(payload),
        )


def _event_lock(event_id: str) -> threading.Lock:
    with _CACHE_LOCK:
        lock = _EVENT_LOCKS.get(event_id)
        if lock is None:
            lock = threading.Lock()
            _EVENT_LOCKS[event_id] = lock
        return lock


def _clear_market_snapshot_cache() -> None:
    with _CACHE_LOCK:
        _MARKET_SNAPSHOT_CACHE.clear()
        _EVENT_LOCKS.clear()


def _collect_or_reuse_market(event_id: str) -> dict[str, Any]:
    cached = _cache_get(event_id)
    if cached is not None:
        return _validate_market_payload(cached, event_id)

    with _event_lock(event_id):
        cached = _cache_get(event_id)
        if cached is not None:
            return _validate_market_payload(cached, event_id)

        try:
            payload = collect_fanduel_nfl_rushing_yards_hosted(event_id)
        except NFLRushingYardsCollectorError as exc:
            raise HTTPException(
                status_code=503,
                detail=f"NFL Rushing Yards market unavailable: {str(exc)[:240]}",
            ) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail=f"NFL Rushing Yards market unavailable: {type(exc).__name__}",
            ) from exc

        validated = _validate_market_payload(payload, event_id)
        _cache_put(event_id, validated)
        return deepcopy(validated)


@router.get("/status")
def rushing_yards_market_status():
    return {"status": "ready", "service": "kyre-sports-api", **CONTRACT}


@router.get("")
def rushing_yards_market(
    event_id: str = Query(
        ...,
        min_length=1,
        max_length=32,
        description="Official ESPN NFL event ID from the verified Streamlit slate.",
    )
):
    event_id = str(event_id or "").strip()
    if not event_id.isdigit():
        raise HTTPException(status_code=422, detail="event_id must be an official numeric ESPN NFL event ID")
    return _collect_or_reuse_market(event_id)


__all__ = [
    "CONTRACT",
    "MARKET_SNAPSHOT_TTL_SECONDS",
    "_clear_market_snapshot_cache",
    "router",
]
