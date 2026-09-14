"""Kyre Sports API adapter for the NFL Spread Streamlit surface.

Transport-only. This module fetches one exact official ESPN NFL event from the
certified Kyre Sports API Spread endpoint and validates the response fail-closed.
It owns no projection, probability, Monte Carlo, grading, staking, or wager
logic.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
import os
import time
from typing import Any

import requests

MODEL_VERSION = "NFL SPREAD KYRE SPORTS API MARKET ADAPTER V1"
DEFAULT_API_BASE_URL = "https://kyre-sports-api.onrender.com"
SCHEMA_VERSION = "nfl_spread_market_v1"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False
WAGER_ACTIONS_ENABLED = False
REQUEST_CONNECT_TIMEOUT_SECONDS = 3.0
REQUEST_READ_TIMEOUT_SECONDS = 10.0
MAX_REQUEST_ATTEMPTS = 2
RETRY_BACKOFF_SECONDS = 0.35
MAX_CAPTURE_AGE_SECONDS = 300
MAX_FUTURE_SKEW_SECONDS = 30
MAX_ABS_NFL_SPREAD = 100.0
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
        number = float(value)
    except (TypeError, ValueError):
        return math.nan
    return number if math.isfinite(number) else math.nan


def _spread(value: Any) -> float | None:
    number = _num(value)
    if not math.isfinite(number) or abs(number) > MAX_ABS_NFL_SPREAD:
        return None
    return float(number)


def _american(value: Any) -> int | None:
    number = _num(value)
    if not math.isfinite(number) or not float(number).is_integer():
        return None
    out = int(number)
    if out == 0 or abs(out) < 100:
        return None
    return out


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
        "market_available": False,
        "reason": _safe(reason, "Kyre Sports API Spread market unavailable"),
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
    """Validate one public Kyre Sports API Spread response fail-closed."""
    event_id = _safe(official_event_id)
    if not event_id.isdigit():
        return _fail("official ESPN event ID is required", event_id=event_id)
    if not isinstance(payload, dict):
        return _fail("Kyre Sports API response is not an object", event_id=event_id)
    if _safe(payload.get("schema_version")) != SCHEMA_VERSION:
        return _fail("Kyre Sports API Spread schema mismatch", event_id=event_id)
    if _safe(payload.get("market")).lower() != "spread":
        return _fail("Kyre Sports API Spread market type mismatch", event_id=event_id)
    if _safe(payload.get("official_event_id")) != event_id:
        return _fail("Kyre Sports API official event identity mismatch", event_id=event_id)

    identity = payload.get("identity") or {}
    semantics = payload.get("market_semantics") or {}
    if not isinstance(identity, dict) or not isinstance(semantics, dict):
        return _fail("Kyre Sports API Spread safety contract missing", event_id=event_id)
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
        return _fail("Kyre Sports API Spread safety contract failed closed", event_id=event_id)

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
        return _fail("Kyre Sports API Spread response is stale", event_id=event_id)

    raw_books = payload.get("books") or []
    if not isinstance(raw_books, list):
        return _fail("Kyre Sports API books payload is invalid", event_id=event_id)

    books: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in raw_books:
        if not isinstance(raw, dict):
            return _fail("Kyre Sports API returned an invalid Spread book row", event_id=event_id)
        sportsbook = _safe(raw.get("sportsbook"))
        key = sportsbook.casefold()
        away_spread = _spread(raw.get("away_spread"))
        home_spread = _spread(raw.get("home_spread"))
        away_price = _american(raw.get("away_price"))
        home_price = _american(raw.get("home_price"))
        updated = _aware_stamp(raw.get("updated_at_utc"))
        if (
            _safe(raw.get("official_event_id")) != event_id
            or not sportsbook
            or key in seen
            or _safe(raw.get("line_status")).lower() != "active"
            or away_spread is None
            or home_spread is None
            or not math.isclose(away_spread + home_spread, 0.0, abs_tol=1e-9)
            or away_price is None
            or home_price is None
            or updated is None
        ):
            return _fail("Kyre Sports API returned an invalid or ambiguous Spread book pair", event_id=event_id)
        age = (now - updated).total_seconds()
        if age < -MAX_FUTURE_SKEW_SECONDS:
            return _fail("Kyre Sports API Spread book timestamp is in the future", event_id=event_id)
        seen.add(key)
        books.append(
            {
                **dict(raw),
                "sportsbook": sportsbook,
                "away_spread": away_spread,
                "home_spread": home_spread,
                "away_price": away_price,
                "home_price": home_price,
                "updated_at_utc": updated.isoformat(),
                "age_seconds": max(0, int(age)),
            }
        )

    if payload.get("market_available") is True and not books:
        return _fail("Kyre Sports API marked Spread available without a certified book pair", event_id=event_id)
    if payload.get("ready") is True and not books:
        return _fail("Kyre Sports API marked Spread ready without a certified book pair", event_id=event_id)

    return {
        "ready": bool(books),
        "market_available": bool(books),
        "reason": "" if books else "Kyre Sports API returned no active Spread book pairs",
        "schema_version": SCHEMA_VERSION,
        "official_event_id": event_id,
        "captured_at_utc": captured.isoformat(),
        "capture_age_seconds": max(0.0, capture_age),
        "identity": dict(identity),
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
    url = f"{_safe(base_url, _api_base_url()).rstrip('/')}/api/v1/nfl/spread/market"

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


def fmt_american(value: Any) -> str:
    price = _american(value)
    if price is None:
        return "—"
    return f"+{price}" if price > 0 else str(price)


def fmt_spread(value: Any) -> str:
    number = _spread(value)
    if number is None:
        return "—"
    return f"+{number:g}" if number > 0 else f"{number:g}"


__all__ = [
    "DEFAULT_API_BASE_URL",
    "MAX_REQUEST_ATTEMPTS",
    "MODEL_VERSION",
    "REQUEST_CONNECT_TIMEOUT_SECONDS",
    "REQUEST_READ_TIMEOUT_SECONDS",
    "SCHEMA_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "WAGER_ACTIONS_ENABLED",
    "fetch_event_market",
    "fmt_american",
    "fmt_spread",
    "validate_event_payload",
]
