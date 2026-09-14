"""Kyre Sports API — exact-ID NFL pregame Spread market endpoint.

The endpoint is transport/market context only. It returns fresh sportsbook rows
for one official ESPN NFL event and cannot modify any projection, Monte Carlo,
probability, grading, staking, or wager behavior.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import math
import threading
from time import monotonic
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from sports_api.collectors.nfl_fanduel_spread_v1 import (
    NFLSpreadCollectorError,
    SCHEMA_VERSION,
    collect_fanduel_nfl_spread,
)

router = APIRouter(prefix="/api/v1/nfl/spread/market", tags=["nfl-spread-market"])

MARKET_SNAPSHOT_TTL_SECONDS = 10.0
MAX_ABS_NFL_SPREAD = 100.0
_CACHE_LOCK = threading.RLock()
_MARKET_SNAPSHOT_CACHE: dict[str, tuple[float, int, dict[str, Any]]] = {}
_EVENT_LOCKS: dict[str, threading.Lock] = {}

CONTRACT = {
    "schema_version": SCHEMA_VERSION,
    "service": "Kyre Sports API",
    "sport": "nfl",
    "market": "spread",
    "official_authority": "ESPN",
    "official_event_id_required": True,
    "fuzzy_matching": False,
    "synthetic_event_ids": False,
    "projection_weight": 0.0,
    "market_context_only": True,
    "may_modify_projection": False,
    "model_probability_input": False,
    "multi_book_capable": True,
    "stake_sizing_enabled": False,
    "wager_actions": False,
}


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _american(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number != 0 and abs(number) >= 100 else None


def _spread(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or abs(number) > MAX_ABS_NFL_SPREAD:
        return None
    return number


def _aware_iso(value: Any) -> bool:
    text = _text(value).replace("Z", "+00:00")
    if not text:
        return False
    try:
        stamp = datetime.fromisoformat(text)
    except ValueError:
        return False
    return stamp.tzinfo is not None and stamp.utcoffset() is not None


def _validate_market_payload(payload: dict[str, Any], event_id: str) -> dict[str, Any]:
    """Re-run identity, line, price and 0%-projection contracts for every response."""
    if not isinstance(payload, dict):
        raise HTTPException(status_code=503, detail="NFL Spread market payload is invalid")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise HTTPException(status_code=503, detail="NFL Spread market schema contract mismatch")
    if _text(payload.get("market")).lower() != "spread":
        raise HTTPException(status_code=503, detail="NFL Spread market type mismatch")
    if _text(payload.get("official_event_id")) != event_id:
        raise HTTPException(status_code=503, detail="NFL Spread official event identity mismatch")
    if not _aware_iso(payload.get("captured_at_utc")):
        raise HTTPException(status_code=503, detail="NFL Spread capture timestamp is invalid")

    identity = payload.get("identity") or {}
    semantics = payload.get("market_semantics") or {}
    if (
        not isinstance(identity, dict)
        or not isinstance(semantics, dict)
        or _text(identity.get("official_event_id")) != event_id
        or not _text(identity.get("away_team_id")).isdigit()
        or not _text(identity.get("home_team_id")).isdigit()
        or identity.get("team_name_matching") is not False
        or identity.get("fuzzy_matching") is not False
        or identity.get("synthetic_event_ids") is not False
        or semantics.get("projection_weight") != 0.0
        or semantics.get("market_context_only") is not True
        or semantics.get("may_modify_projection") is not False
        or semantics.get("model_probability_input") is not False
        or semantics.get("multi_book_capable") is not True
        or semantics.get("stake_sizing_enabled") is not False
        or semantics.get("wager_actions") is not False
    ):
        raise HTTPException(status_code=503, detail="NFL Spread market safety contract failed closed")

    books = payload.get("books") or []
    if not isinstance(books, list):
        raise HTTPException(status_code=503, detail="NFL Spread books payload is invalid")
    seen: set[str] = set()
    validated_books: list[dict[str, Any]] = []
    for raw in books:
        if not isinstance(raw, dict):
            raise HTTPException(status_code=503, detail="NFL Spread book row is invalid")
        sportsbook = _text(raw.get("sportsbook"))
        key = sportsbook.casefold()
        away_spread = _spread(raw.get("away_spread"))
        home_spread = _spread(raw.get("home_spread"))
        away_price = _american(raw.get("away_price"))
        home_price = _american(raw.get("home_price"))
        if (
            _text(raw.get("official_event_id")) != event_id
            or not sportsbook
            or key in seen
            or away_spread is None
            or home_spread is None
            or not math.isclose(away_spread + home_spread, 0.0, abs_tol=1e-9)
            or away_price is None
            or home_price is None
            or not _aware_iso(raw.get("updated_at_utc"))
            or _text(raw.get("line_status")).lower() != "active"
        ):
            raise HTTPException(status_code=503, detail="NFL Spread book row contract failed closed")
        seen.add(key)
        row = dict(raw)
        row["away_spread"] = away_spread
        row["home_spread"] = home_spread
        row["away_price"] = away_price
        row["home_price"] = home_price
        validated_books.append(row)

    if payload.get("market_available") is True and not validated_books:
        raise HTTPException(status_code=503, detail="NFL Spread marked available without a valid book pair")
    if payload.get("ready") is True and not validated_books:
        raise HTTPException(status_code=503, detail="NFL Spread marked ready without a valid book pair")

    out = deepcopy(payload)
    out["books"] = validated_books
    out["book_count"] = len(validated_books)
    out["ready"] = bool(validated_books)
    out["market_available"] = bool(validated_books)
    return out


def _collector_identity() -> int:
    return id(collect_fanduel_nfl_spread)


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
            payload = collect_fanduel_nfl_spread(event_id)
        except NFLSpreadCollectorError as exc:
            raise HTTPException(
                status_code=503,
                detail=f"NFL Spread market unavailable: {str(exc)[:240]}",
            ) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail=f"NFL Spread market unavailable: {type(exc).__name__}",
            ) from exc

        validated = _validate_market_payload(payload, event_id)
        _cache_put(event_id, validated)
        return deepcopy(validated)


@router.get("/status")
def spread_market_status():
    return {"status": "ready", **CONTRACT}


@router.get("")
def spread_market(
    event_id: str = Query(
        ...,
        min_length=1,
        max_length=32,
        description="Official ESPN NFL event ID from the verified Streamlit slate.",
    )
):
    event_id = _text(event_id)
    if not event_id.isdigit():
        raise HTTPException(status_code=422, detail="event_id must be an official numeric ESPN NFL event ID")
    return _collect_or_reuse_market(event_id)


__all__ = [
    "CONTRACT",
    "MARKET_SNAPSHOT_TTL_SECONDS",
    "_clear_market_snapshot_cache",
    "_validate_market_payload",
    "router",
]
