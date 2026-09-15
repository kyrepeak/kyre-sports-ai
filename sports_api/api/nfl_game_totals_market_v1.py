"""Kyre Sports API — exact-ID NFL pregame Game Totals market endpoint V1.

The sportsbook total is transport/market context only. It cannot modify any
football-only projection, Monte Carlo input, probability, grade, stake sizing,
or wager action. This router remains isolated from the shared hosted route table
until the later shared-host attachment certification step.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import math
import threading
from time import monotonic
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from sports_api.collectors.nfl_fanduel_totals_v1 import (
    MAX_NFL_TOTAL,
    NFLGameTotalsCollectorError,
    SCHEMA_VERSION,
    collect_fanduel_nfl_game_total,
)

router = APIRouter(
    prefix="/api/v1/nfl/game-totals/market",
    tags=["nfl-game-totals-market"],
)

MARKET_SNAPSHOT_TTL_SECONDS = 10.0
MAX_SNAPSHOT_AGE_SECONDS = 120.0
MAX_FUTURE_SKEW_SECONDS = 30.0
_CACHE_LOCK = threading.RLock()
_MARKET_SNAPSHOT_CACHE: dict[str, tuple[float, int, dict[str, Any]]] = {}
_EVENT_LOCKS: dict[str, threading.Lock] = {}

CONTRACT = {
    "schema_version": SCHEMA_VERSION,
    "service": "Kyre Sports API",
    "sport": "nfl",
    "market": "game_total",
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

RESPONSE_REQUIRED_FIELDS = (
    "schema_version",
    "service",
    "sport",
    "market",
    "official_event_id",
    "captured_at_utc",
    "ready",
    "market_available",
    "identity",
    "books",
    "market_semantics",
)

IDENTITY_REQUIRED_FIELDS = (
    "official_authority",
    "official_event_id",
    "provider_event_id",
    "away_team_id",
    "home_team_id",
    "away_abbr",
    "home_abbr",
    "kickoff_delta_seconds",
    "team_name_matching",
    "fuzzy_matching",
    "synthetic_event_ids",
)

BOOK_REQUIRED_FIELDS = (
    "official_event_id",
    "sportsbook",
    "provider",
    "provider_event_id",
    "market_id",
    "total",
    "over_price",
    "under_price",
    "updated_at_utc",
    "line_status",
)


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


def _market_total(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number <= 0 or number > MAX_NFL_TOTAL:
        return None
    return number


def _aware_timestamp(value: Any, field: str) -> datetime:
    text = _text(value).replace("Z", "+00:00")
    if not text:
        raise HTTPException(status_code=503, detail=f"NFL Game Totals {field} timestamp is missing")
    try:
        stamp = datetime.fromisoformat(text)
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=f"NFL Game Totals {field} timestamp is invalid") from exc
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        raise HTTPException(status_code=503, detail=f"NFL Game Totals {field} timestamp is not timezone-aware")
    return stamp.astimezone(timezone.utc)


def _validate_freshness(stamp: datetime, now_utc: datetime, field: str) -> None:
    age_seconds = (now_utc - stamp).total_seconds()
    if age_seconds > MAX_SNAPSHOT_AGE_SECONDS:
        raise HTTPException(status_code=503, detail=f"NFL Game Totals {field} is stale")
    if age_seconds < -MAX_FUTURE_SKEW_SECONDS:
        raise HTTPException(status_code=503, detail=f"NFL Game Totals {field} is from the future")


def _validate_market_payload(
    payload: dict[str, Any],
    event_id: str,
    *,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    """Re-prove identity, freshness, total, price and safety contracts."""
    if not isinstance(payload, dict):
        raise HTTPException(status_code=503, detail="NFL Game Totals market payload is invalid")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise HTTPException(status_code=503, detail="NFL Game Totals market schema contract mismatch")
    if _text(payload.get("market")).lower() != "game_total":
        raise HTTPException(status_code=503, detail="NFL Game Totals market type mismatch")
    if _text(payload.get("official_event_id")) != event_id:
        raise HTTPException(status_code=503, detail="NFL Game Totals official event identity mismatch")

    now = now_utc or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now_utc must be timezone-aware")
    now = now.astimezone(timezone.utc)
    captured = _aware_timestamp(payload.get("captured_at_utc"), "capture")
    _validate_freshness(captured, now, "capture")

    identity = payload.get("identity") or {}
    semantics = payload.get("market_semantics") or {}
    if (
        not isinstance(identity, dict)
        or not isinstance(semantics, dict)
        or _text(identity.get("official_authority")) != "ESPN"
        or _text(identity.get("official_event_id")) != event_id
        or not _text(identity.get("provider_event_id"))
        or not _text(identity.get("away_team_id")).isdigit()
        or not _text(identity.get("home_team_id")).isdigit()
        or not _text(identity.get("away_abbr"))
        or not _text(identity.get("home_abbr"))
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
        raise HTTPException(status_code=503, detail="NFL Game Totals market safety contract failed closed")

    books = payload.get("books") or []
    if not isinstance(books, list):
        raise HTTPException(status_code=503, detail="NFL Game Totals books payload is invalid")
    seen: set[str] = set()
    validated_books: list[dict[str, Any]] = []
    for raw in books:
        if not isinstance(raw, dict):
            raise HTTPException(status_code=503, detail="NFL Game Totals book row is invalid")
        sportsbook = _text(raw.get("sportsbook"))
        key = sportsbook.casefold()
        total = _market_total(raw.get("total"))
        over_price = _american(raw.get("over_price"))
        under_price = _american(raw.get("under_price"))
        updated = _aware_timestamp(raw.get("updated_at_utc"), "book update")
        _validate_freshness(updated, now, "book update")
        if (
            _text(raw.get("official_event_id")) != event_id
            or not sportsbook
            or key in seen
            or not _text(raw.get("provider_event_id"))
            or not _text(raw.get("market_id"))
            or total is None
            or over_price is None
            or under_price is None
            or _text(raw.get("line_status")).lower() != "active"
        ):
            raise HTTPException(status_code=503, detail="NFL Game Totals book row contract failed closed")
        seen.add(key)
        row = dict(raw)
        row["total"] = total
        row["over_price"] = over_price
        row["under_price"] = under_price
        validated_books.append(row)

    if payload.get("market_available") is True and not validated_books:
        raise HTTPException(status_code=503, detail="NFL Game Totals marked available without a valid book")
    if payload.get("ready") is True and not validated_books:
        raise HTTPException(status_code=503, detail="NFL Game Totals marked ready without a valid book")
    if payload.get("ready") is not True or payload.get("market_available") is not True:
        raise HTTPException(status_code=503, detail="NFL Game Totals market is not ready")

    out = deepcopy(payload)
    out["books"] = validated_books
    out["book_count"] = len(validated_books)
    out["ready"] = True
    out["market_available"] = True
    out["freshness"] = {
        "snapshot_ttl_seconds": MARKET_SNAPSHOT_TTL_SECONDS,
        "max_snapshot_age_seconds": MAX_SNAPSHOT_AGE_SECONDS,
        "max_future_skew_seconds": MAX_FUTURE_SKEW_SECONDS,
    }
    return out


def _collector_identity() -> int:
    return id(collect_fanduel_nfl_game_total)


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
            payload = collect_fanduel_nfl_game_total(event_id)
        except NFLGameTotalsCollectorError as exc:
            raise HTTPException(
                status_code=503,
                detail=f"NFL Game Totals market unavailable: {str(exc)[:240]}",
            ) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail=f"NFL Game Totals market unavailable: {type(exc).__name__}",
            ) from exc

        validated = _validate_market_payload(payload, event_id)
        _cache_put(event_id, validated)
        return deepcopy(validated)


@router.get("/status")
def game_totals_market_status():
    return {
        "status": "collector_ready",
        "endpoint": "/api/v1/nfl/game-totals/market",
        "live_market_route_ready": True,
        "shared_host_attached": False,
        "snapshot_ttl_seconds": MARKET_SNAPSHOT_TTL_SECONDS,
        "max_snapshot_age_seconds": MAX_SNAPSHOT_AGE_SECONDS,
        **CONTRACT,
    }


@router.get("")
def game_totals_market(
    event_id: str = Query(
        ...,
        min_length=1,
        max_length=32,
        description="Official ESPN NFL event ID from the verified Game Totals slate.",
    )
):
    event_id = _text(event_id)
    if not event_id.isdigit():
        raise HTTPException(status_code=422, detail="event_id must be an official numeric ESPN NFL event ID")
    return _collect_or_reuse_market(event_id)


__all__ = [
    "BOOK_REQUIRED_FIELDS",
    "CONTRACT",
    "IDENTITY_REQUIRED_FIELDS",
    "MARKET_SNAPSHOT_TTL_SECONDS",
    "MAX_FUTURE_SKEW_SECONDS",
    "MAX_SNAPSHOT_AGE_SECONDS",
    "RESPONSE_REQUIRED_FIELDS",
    "SCHEMA_VERSION",
    "_clear_market_snapshot_cache",
    "_validate_market_payload",
    "game_totals_market_status",
    "router",
]
