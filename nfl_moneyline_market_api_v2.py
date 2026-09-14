"""NFL Moneyline market adapter V2 — additive hot-cache reliability over V1.

V2 changes transport cadence only. Certified ``nfl_moneyline_market_api_v1``
still owns the Kyre Sports API request, exact ESPN event identity validation,
response safety contract, and conversion into the frozen V5 market snapshot.
Frozen ``nfl_moneyline_market_v1`` still owns freshness, usable-book, no-vig,
best-price and market-quality math.

The speed layer keeps only already-validated successful snapshots. Immediate
Streamlit reruns reuse that success instead of issuing another HTTP request.
After the hot window expires, V1 is asked for fresh data. If that refresh fails,
the last validated success may be reused only while at least one real sportsbook
row remains non-stale under the existing frozen freshness rules. Cached quote
ages are recomputed from their original timestamps on every reuse.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import threading
from time import monotonic
from typing import Any

import pandas as pd

import nfl_moneyline_market_api_v1 as frozen

MODEL_VERSION = "NFL MONEYLINE KYRE SPORTS API MARKET ADAPTER V2 • HOT CACHE"
FROZEN_ADAPTER = "nfl_moneyline_market_api_v1"
FROZEN_MARKET_OWNER = frozen.FROZEN_MARKET_OWNER
HOT_CACHE_TTL_SECONDS = 45.0
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False

_CACHE_LOCK = threading.RLock()
_HOT_CACHE: dict[tuple[str, str], tuple[float, dict[str, Any]]] = {}
_LAST_GOOD: dict[tuple[str, str], dict[str, Any]] = {}


def _safe(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _canonical_base_url(base_url: str | None = None) -> str:
    return _safe(base_url, frozen._api_base_url()).rstrip("/")


def _cache_key(event_id: str, base_url: str | None = None) -> tuple[str, str]:
    return (_canonical_base_url(base_url), _safe(event_id))


def _age_validated_success(
    payload: dict[str, Any] | None,
    event_id: str,
    *,
    now_utc: datetime | None = None,
) -> dict[str, Any] | None:
    """Return a re-aged copy only while frozen freshness rules still allow use."""
    if not isinstance(payload, dict) or payload.get("ready") is not True:
        return None
    if _safe(payload.get("official_event_id")) != _safe(event_id):
        return None
    if (
        payload.get("projection_weight") != 0.0
        or payload.get("market_context_only") is not True
        or payload.get("may_modify_projection") is not False
        or payload.get("model_probability_input") is not False
        or payload.get("stake_sizing_enabled") is not False
        or payload.get("wager_actions") is not False
    ):
        return None

    now = now_utc or _utc_now()
    if now.tzinfo is None or now.utcoffset() is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)

    captured = frozen._aware_stamp(payload.get("captured_at_utc"))
    if captured is None:
        return None
    capture_age = (now - captured).total_seconds()
    if capture_age < -frozen.MAX_FUTURE_SKEW_SECONDS:
        return None
    if capture_age > frozen.MAX_CAPTURE_AGE_SECONDS:
        return None

    out = deepcopy(payload)
    books = out.get("books") or []
    if not isinstance(books, list) or not books:
        return None

    usable_books = 0
    for row in books:
        if not isinstance(row, dict):
            return None
        updated = frozen._aware_stamp(row.get("updated_at_utc"))
        if updated is None:
            return None
        age = (now - updated).total_seconds()
        if age < -frozen.MAX_FUTURE_SKEW_SECONDS:
            return None
        row["age_seconds"] = max(0, int(age))
        if row["age_seconds"] <= frozen.STALE_SECONDS:
            usable_books += 1

    if usable_books <= 0:
        return None

    out["capture_age_seconds"] = max(0.0, capture_age)
    out["transport_cache_usable_books"] = usable_books
    return out


def _cache_get_hot(
    key: tuple[str, str],
    event_id: str,
    *,
    now_utc: datetime | None = None,
) -> dict[str, Any] | None:
    stamp = monotonic()
    with _CACHE_LOCK:
        entry = _HOT_CACHE.get(key)
        if entry is None:
            return None
        expires_at, payload = entry
        if expires_at <= stamp:
            _HOT_CACHE.pop(key, None)
            return None
        aged = _age_validated_success(payload, event_id, now_utc=now_utc)
        if aged is None:
            _HOT_CACHE.pop(key, None)
            return None
        return aged


def _cache_put_success(key: tuple[str, str], payload: dict[str, Any]) -> None:
    if payload.get("ready") is not True:
        return
    with _CACHE_LOCK:
        copy = deepcopy(payload)
        _HOT_CACHE[key] = (monotonic() + HOT_CACHE_TTL_SECONDS, copy)
        _LAST_GOOD[key] = deepcopy(copy)


def _last_good_get(
    key: tuple[str, str],
    event_id: str,
    *,
    now_utc: datetime | None = None,
) -> dict[str, Any] | None:
    with _CACHE_LOCK:
        payload = deepcopy(_LAST_GOOD.get(key))
    if payload is None:
        return None
    aged = _age_validated_success(payload, event_id, now_utc=now_utc)
    if aged is not None:
        return aged
    with _CACHE_LOCK:
        _LAST_GOOD.pop(key, None)
    return None


def _clear_transport_cache() -> None:
    with _CACHE_LOCK:
        _HOT_CACHE.clear()
        _LAST_GOOD.clear()


def fetch_event_market(
    official_event_id: str,
    *,
    now_utc: datetime | None = None,
    base_url: str | None = None,
) -> dict[str, Any]:
    """Fetch one event with hot success reuse and freshness-safe fallback.

    Explicit ``now_utc`` calls bypass V2 caches so deterministic V1 validation
    tests keep their original semantics.
    """
    event_id = _safe(official_event_id)
    if now_utc is not None:
        return frozen.fetch_event_market(event_id, now_utc=now_utc, base_url=base_url)

    key = _cache_key(event_id, base_url)
    hot = _cache_get_hot(key, event_id)
    if hot is not None:
        hot["transport_cache_source"] = "hot"
        hot["transport_http_avoided"] = True
        hot["stale_safe_reuse"] = False
        return hot

    fresh = frozen.fetch_event_market(event_id, base_url=base_url)
    if fresh.get("ready") is True:
        aged = _age_validated_success(fresh, event_id)
        if aged is not None:
            _cache_put_success(key, fresh)
        fresh = deepcopy(fresh)
        fresh["transport_cache_source"] = "fresh"
        fresh["transport_http_avoided"] = False
        fresh["stale_safe_reuse"] = False
        return fresh

    fallback = _last_good_get(key, event_id)
    if fallback is not None:
        fallback["transport_cache_source"] = "last_good"
        fallback["transport_http_avoided"] = False
        fallback["stale_safe_reuse"] = True
        fallback["refresh_failure_reason"] = _safe(fresh.get("reason"))
        fallback["refresh_http"] = fresh.get("http")
        fallback["refresh_request_attempts"] = fresh.get("request_attempts")
        return fallback

    fresh = deepcopy(fresh)
    fresh["transport_cache_source"] = "fresh_failure"
    fresh["transport_http_avoided"] = False
    fresh["stale_safe_reuse"] = False
    return fresh


def connection_state() -> dict[str, Any]:
    return frozen.connection_state()


def fetch_nfl_moneyline_markets(pregame: pd.DataFrame, day_str: str):
    """Preserve V1 snapshot/math ownership while routing event fetches through V2."""
    snapshots: dict[str, dict[str, Any]] = {}
    diag: dict[str, Any] = {
        "sgo_connected": True,
        "fallback_connected": False,
        "sgo_error": "",
        "fallback_error": "",
        "games_requested": int(len(pregame)) if pregame is not None else 0,
        "games_with_market": 0,
        "transport": "Kyre Sports API",
        "api_base_url": frozen._api_base_url(),
        "api_errors": [],
        "hot_cache_hits": 0,
        "last_good_reuses": 0,
        "fresh_fetches": 0,
    }
    if pregame is None or pregame.empty:
        return snapshots, diag

    for _, src in pregame.iterrows():
        game = src.to_dict()
        gid = _safe(game.get("game_id")) or f"{_safe(game.get('away_abbr')).upper()}@{_safe(game.get('home_abbr')).upper()}"
        event_market = fetch_event_market(gid)
        source = _safe(event_market.get("transport_cache_source"))
        if source == "hot":
            diag["hot_cache_hits"] += 1
        elif source == "last_good":
            diag["last_good_reuses"] += 1
        else:
            diag["fresh_fetches"] += 1
        if not event_market.get("ready"):
            diag["api_errors"].append({
                "game_id": gid,
                "reason": _safe(event_market.get("reason")),
                "http": event_market.get("http"),
            })
        snapshots[gid] = frozen._snapshot_from_event(game, event_market)

    diag["games_with_market"] = sum(1 for snap in snapshots.values() if snap.get("ready"))
    if diag["api_errors"]:
        first = diag["api_errors"][0]
        diag["sgo_error"] = f"Kyre Sports API: {first.get('reason') or 'market unavailable'}"
    return snapshots, diag


# Display formatting and all frozen market thresholds remain V1-owned.
fmt_american = frozen.fmt_american
fmt_pct = frozen.fmt_pct
fmt_age = frozen.fmt_age
freshness_label = frozen.freshness_label
FRESH_SECONDS = frozen.FRESH_SECONDS
STALE_SECONDS = frozen.STALE_SECONDS


__all__ = [
    "FRESH_SECONDS",
    "FROZEN_ADAPTER",
    "FROZEN_MARKET_OWNER",
    "HOT_CACHE_TTL_SECONDS",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "STALE_SECONDS",
    "_clear_transport_cache",
    "connection_state",
    "fetch_event_market",
    "fetch_nfl_moneyline_markets",
    "fmt_age",
    "fmt_american",
    "fmt_pct",
    "freshness_label",
]
