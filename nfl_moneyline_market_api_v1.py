"""Kyre Sports API adapter for frozen NFL Moneyline V5 market transport.

This module intentionally matches the small interface consumed by
``nfl_moneyline_hub_v5`` while sourcing raw sportsbook pairs from the Kyre
Sports API. Frozen ``nfl_moneyline_market_v1`` still owns implied probability,
no-vig math, quote freshness, stale exclusion, best-price selection, market
quality, and display formatting.

The adapter is transport-only. It cannot modify the Moneyline model P(win),
Monte Carlo, edge/EV formulas, grading, stake sizing, or wager behavior.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
import os
import time
from typing import Any

import pandas as pd
import requests

import nfl_moneyline_market_v1 as frozen

MODEL_VERSION = "NFL MONEYLINE KYRE SPORTS API MARKET ADAPTER V1"
FROZEN_MARKET_OWNER = "nfl_moneyline_market_v1"
DEFAULT_API_BASE_URL = "https://kyre-sports-api.onrender.com"
SCHEMA_VERSION = "nfl_moneyline_market_v1"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False
REQUEST_CONNECT_TIMEOUT_SECONDS = 3.0
REQUEST_READ_TIMEOUT_SECONDS = 10.0
MAX_REQUEST_ATTEMPTS = 2
RETRY_BACKOFF_SECONDS = 0.35
MAX_CAPTURE_AGE_SECONDS = 300
MAX_FUTURE_SKEW_SECONDS = 30
_TRANSIENT_REQUEST_EXCEPTIONS = (
    requests.exceptions.ConnectTimeout,
    requests.exceptions.ReadTimeout,
    requests.exceptions.ConnectionError,
)


def _safe(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _num(value: Any) -> float:
    try:
        out = float(value)
        return out if math.isfinite(out) else math.nan
    except Exception:
        return math.nan


def _american_ok(value: Any) -> bool:
    number = _num(value)
    return math.isfinite(number) and float(number).is_integer() and number != 0 and abs(number) >= 100


def _aware_stamp(value: Any) -> datetime | None:
    text = _safe(value).replace("Z", "+00:00")
    if not text:
        return None
    try:
        stamp = datetime.fromisoformat(text)
    except ValueError:
        return None
    if stamp.tzinfo is None or stamp.utcoffset() is None:
        return None
    return stamp.astimezone(timezone.utc)


def _api_base_url() -> str:
    return _safe(os.environ.get("KYRE_SPORTS_API_BASE_URL"), DEFAULT_API_BASE_URL).rstrip("/")


def _fail(reason: str, *, event_id: str = "", http: int | None = None) -> dict[str, Any]:
    return {
        "ready": False,
        "reason": _safe(reason, "Kyre Sports API Moneyline market unavailable"),
        "official_event_id": _safe(event_id),
        "http": http,
        "books": [],
        "projection_weight": 0.0,
        "market_context_only": True,
        "may_modify_projection": False,
        "model_probability_input": False,
        "stake_sizing_enabled": False,
        "wager_actions": False,
    }


def validate_event_payload(
    payload: Any,
    official_event_id: str,
    *,
    now_utc: datetime | None = None,
) -> dict[str, Any]:
    """Validate one public Kyre Sports API Moneyline response fail-closed."""
    event_id = _safe(official_event_id)
    if not event_id.isdigit():
        return _fail("official ESPN event ID is required", event_id=event_id)
    if not isinstance(payload, dict):
        return _fail("Kyre Sports API response is not an object", event_id=event_id)
    if _safe(payload.get("schema_version")) != SCHEMA_VERSION:
        return _fail("Kyre Sports API Moneyline schema mismatch", event_id=event_id)
    if _safe(payload.get("official_event_id")) != event_id:
        return _fail("Kyre Sports API official event identity mismatch", event_id=event_id)

    identity = payload.get("identity") or {}
    semantics = payload.get("market_semantics") or {}
    if not isinstance(identity, dict) or not isinstance(semantics, dict):
        return _fail("Kyre Sports API Moneyline safety contract missing", event_id=event_id)
    if (
        _safe(identity.get("official_event_id")) != event_id
        or not _safe(identity.get("away_team_id")).isdigit()
        or not _safe(identity.get("home_team_id")).isdigit()
        or identity.get("team_name_matching") is not False
        or identity.get("fuzzy_matching") is not False
        or identity.get("synthetic_event_ids") is not False
        or semantics.get("projection_weight") != 0.0
        or semantics.get("market_context_only") is not True
        or semantics.get("may_modify_projection") is not False
        or semantics.get("model_probability_input") is not False
        or semantics.get("stake_sizing_enabled") is not False
        or semantics.get("wager_actions") is not False
    ):
        return _fail("Kyre Sports API Moneyline safety contract failed closed", event_id=event_id)

    captured = _aware_stamp(payload.get("captured_at_utc"))
    if captured is None:
        return _fail("Kyre Sports API capture timestamp missing or invalid", event_id=event_id)
    now = now_utc or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    capture_age = (now - captured).total_seconds()
    if capture_age < -MAX_FUTURE_SKEW_SECONDS:
        return _fail("Kyre Sports API capture timestamp is in the future", event_id=event_id)
    if capture_age > MAX_CAPTURE_AGE_SECONDS:
        return _fail("Kyre Sports API Moneyline response is stale", event_id=event_id)

    raw_books = payload.get("books") or []
    if not isinstance(raw_books, list):
        return _fail("Kyre Sports API books payload is invalid", event_id=event_id)

    books: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in raw_books:
        if not isinstance(raw, dict):
            continue
        sportsbook = _safe(raw.get("sportsbook"))
        key = sportsbook.casefold()
        updated = _aware_stamp(raw.get("updated_at_utc"))
        if (
            _safe(raw.get("official_event_id")) != event_id
            or not sportsbook
            or key in seen
            or _safe(raw.get("line_status")).lower() != "active"
            or not _american_ok(raw.get("away_ml"))
            or not _american_ok(raw.get("home_ml"))
            or updated is None
        ):
            return _fail("Kyre Sports API returned an invalid or ambiguous Moneyline book pair", event_id=event_id)
        seen.add(key)
        age = (now - updated).total_seconds()
        if age < -MAX_FUTURE_SKEW_SECONDS:
            return _fail("Kyre Sports API Moneyline book timestamp is in the future", event_id=event_id)
        books.append({
            **dict(raw),
            "sportsbook": sportsbook,
            "away_ml": int(float(raw.get("away_ml"))),
            "home_ml": int(float(raw.get("home_ml"))),
            "updated_at_utc": updated.isoformat(),
            "age_seconds": max(0, int(age)),
        })

    if payload.get("market_available") is True and not books:
        return _fail("Kyre Sports API marked market available without a certified book pair", event_id=event_id)
    if payload.get("ready") is True and not books:
        return _fail("Kyre Sports API marked market ready without a certified book pair", event_id=event_id)

    return {
        "ready": bool(books),
        "reason": "" if books else "Kyre Sports API returned no active Moneyline book pairs",
        "schema_version": SCHEMA_VERSION,
        "official_event_id": event_id,
        "captured_at_utc": captured.isoformat(),
        "capture_age_seconds": max(0.0, capture_age),
        "market_available": bool(books),
        "books": books,
        "projection_weight": 0.0,
        "market_context_only": True,
        "may_modify_projection": False,
        "model_probability_input": False,
        "stake_sizing_enabled": False,
        "wager_actions": False,
    }


def fetch_event_market(
    official_event_id: str,
    *,
    now_utc: datetime | None = None,
    base_url: str | None = None,
) -> dict[str, Any]:
    event_id = _safe(official_event_id)
    if not event_id.isdigit():
        return _fail("official ESPN event ID is required", event_id=event_id)
    url = f"{_safe(base_url, _api_base_url()).rstrip('/')}/api/v1/nfl/moneyline/market"

    response = None
    request_error: Exception | None = None
    request_attempts = 0
    for attempt in range(1, MAX_REQUEST_ATTEMPTS + 1):
        request_attempts = attempt
        try:
            response = requests.get(
                url,
                params={"event_id": event_id},
                timeout=(REQUEST_CONNECT_TIMEOUT_SECONDS, REQUEST_READ_TIMEOUT_SECONDS),
                headers={"Accept": "application/json", "User-Agent": "KyreSportsAI-Streamlit/1.0"},
            )
        except _TRANSIENT_REQUEST_EXCEPTIONS as exc:
            request_error = exc
            if attempt < MAX_REQUEST_ATTEMPTS:
                time.sleep(RETRY_BACKOFF_SECONDS)
                continue
        except Exception as exc:
            request_error = exc
        break

    if response is None:
        out = _fail(
            f"Kyre Sports API request failed: {type(request_error).__name__ if request_error else 'UnknownError'}",
            event_id=event_id,
        )
        out["request_attempts"] = request_attempts
        return out

    status = int(getattr(response, "status_code", 0) or 0)
    if status != 200:
        out = _fail(f"Kyre Sports API returned HTTP {status}", event_id=event_id, http=status)
        out["request_attempts"] = request_attempts
        return out
    try:
        payload = response.json()
    except Exception:
        out = _fail("Kyre Sports API returned invalid JSON", event_id=event_id, http=status)
        out["request_attempts"] = request_attempts
        return out

    out = validate_event_payload(payload, event_id, now_utc=now_utc)
    out["http"] = status
    out["api_url"] = url
    out["request_attempts"] = request_attempts
    return out


def connection_state() -> dict[str, Any]:
    """Compatibility shape consumed by frozen V5's provider gate.

    Frozen V5 only understands ``sgo``/``legacy`` booleans. ``sgo=True`` here
    means the primary market transport is connected; it does *not* claim that
    SportsGameOdds is the source. V9 clears V5's legacy provider labels before
    rendering the certified matchup cards.
    """
    return {
        "sgo": True,
        "legacy": False,
        "sgo_books": "kyre-sports-api",
        "legacy_books": "",
        "kyre_api": True,
        "base_url": _api_base_url(),
    }


def _snapshot_from_event(game: dict[str, Any], event_market: dict[str, Any]) -> dict[str, Any]:
    gid = _safe(game.get("game_id"))
    rows: list[dict[str, Any]] = []
    if event_market.get("ready"):
        for book in event_market.get("books") or []:
            row = {
                "game_id": gid,
                "book": _safe(book.get("sportsbook")),
                "away_ml": book.get("away_ml"),
                "home_ml": book.get("home_ml"),
                "updated_at": book.get("updated_at_utc"),
                "age_seconds": book.get("age_seconds"),
                "provider": _safe(book.get("provider"), "Kyre Sports API"),
            }
            rows.append(frozen._enrich(row))
    snap = {
        "game": dict(game),
        "rows": rows,
        "primary_matched": bool(rows),
        "fallback_used": False,
        "transport": "Kyre Sports API",
        "api_reason": _safe(event_market.get("reason")),
        "api_http": event_market.get("http"),
    }
    snap.update(frozen._summary(rows))
    return snap


def fetch_nfl_moneyline_markets(pregame: pd.DataFrame, day_str: str):
    """Return the exact snapshot/diagnostic contract consumed by frozen V5."""
    snapshots: dict[str, dict[str, Any]] = {}
    diag: dict[str, Any] = {
        "sgo_connected": True,
        "fallback_connected": False,
        "sgo_error": "",
        "fallback_error": "",
        "games_requested": int(len(pregame)) if pregame is not None else 0,
        "games_with_market": 0,
        "transport": "Kyre Sports API",
        "api_base_url": _api_base_url(),
        "api_errors": [],
    }
    if pregame is None or pregame.empty:
        return snapshots, diag

    for _, src in pregame.iterrows():
        game = src.to_dict()
        gid = _safe(game.get("game_id")) or f"{_safe(game.get('away_abbr')).upper()}@{_safe(game.get('home_abbr')).upper()}"
        event_market = fetch_event_market(gid)
        if not event_market.get("ready"):
            diag["api_errors"].append({
                "game_id": gid,
                "reason": _safe(event_market.get("reason")),
                "http": event_market.get("http"),
            })
        snapshots[gid] = _snapshot_from_event(game, event_market)

    diag["games_with_market"] = sum(1 for snap in snapshots.values() if snap.get("ready"))
    if diag["api_errors"]:
        first = diag["api_errors"][0]
        diag["sgo_error"] = f"Kyre Sports API: {first.get('reason') or 'market unavailable'}"
    return snapshots, diag


# V5 display formatting remains owned by the frozen market module.
fmt_american = frozen.fmt_american
fmt_pct = frozen.fmt_pct
fmt_age = frozen.fmt_age
freshness_label = frozen.freshness_label
FRESH_SECONDS = frozen.FRESH_SECONDS
STALE_SECONDS = frozen.STALE_SECONDS


__all__ = [
    "DEFAULT_API_BASE_URL",
    "FRESH_SECONDS",
    "FROZEN_MARKET_OWNER",
    "MAX_REQUEST_ATTEMPTS",
    "MODEL_VERSION",
    "REQUEST_CONNECT_TIMEOUT_SECONDS",
    "REQUEST_READ_TIMEOUT_SECONDS",
    "SCHEMA_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "STALE_SECONDS",
    "connection_state",
    "fetch_event_market",
    "fetch_nfl_moneyline_markets",
    "fmt_age",
    "fmt_american",
    "fmt_pct",
    "freshness_label",
    "validate_event_payload",
]
