"""Kyre Sports API client for NFL Passing Yards Step 10.

This client is deliberately post-model. It accepts only a fresh, exact-ID market
payload from the Kyre Sports API and never supplies projection inputs. Missing,
stale, malformed, ambiguous, or identity-mismatched data fails closed.

Permanent contract:
- exact official ESPN event ID;
- exact official ESPN athlete ID;
- no player-name matching or fuzzy identity;
- no synthetic event/player IDs;
- market context only;
- sportsbook projection influence = 0.0%;
- stake sizing OFF.
"""
from __future__ import annotations

from datetime import datetime, timezone
import math
import os
import time
from typing import Any

import requests

MODEL_VERSION = "NFL PASSING YARDS KYRE SPORTS API CLIENT V1"
DEFAULT_API_BASE_URL = "https://kyre-sports-api.onrender.com"
SCHEMA_VERSION = "nfl_passing_yards_market_v1"
MAX_MARKET_AGE_SECONDS = 300
MAX_FUTURE_SKEW_SECONDS = 30

# Step 10 transport policy. One bounded retry is allowed only for transient
# connection/read failures against the exact same official event endpoint.
# HTTP/schema/identity/freshness/market validation still fails closed without
# a retry that could turn invalid data into accepted market context.
REQUEST_CONNECT_TIMEOUT_SECONDS = 3.0
REQUEST_READ_TIMEOUT_SECONDS = 8.0
MAX_REQUEST_ATTEMPTS = 2
RETRY_BACKOFF_SECONDS = 0.35
_TRANSIENT_REQUEST_EXCEPTIONS = (
    requests.exceptions.ConnectTimeout,
    requests.exceptions.ReadTimeout,
    requests.exceptions.ConnectionError,
)


def _safe(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _num(value: Any):
    try:
        out = float(value)
        return out if math.isfinite(out) else math.nan
    except Exception:
        return math.nan


def _finite(value: Any) -> bool:
    return math.isfinite(_num(value))


def _api_base_url() -> str:
    return _safe(os.environ.get("KYRE_SPORTS_API_BASE_URL"), DEFAULT_API_BASE_URL).rstrip("/")


def _captured_at(value: Any) -> datetime | None:
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


def _american_ok(value: Any) -> bool:
    number = _num(value)
    return _finite(number) and float(number).is_integer() and abs(number) >= 100


def _line_ok(value: Any) -> bool:
    number = _num(value)
    return _finite(number) and 0 < number <= 700


def _fail(reason: str, *, event_id: str = "", athlete_id: str = "", http: int | None = None) -> dict:
    return {
        "ready": False,
        "reason": _safe(reason, "Kyre Sports API market unavailable"),
        "official_event_id": _safe(event_id),
        "official_athlete_id": _safe(athlete_id),
        "http": http,
        "projection_weight": 0.0,
        "market_context_only": True,
        "stake_sizing_enabled": False,
    }


def validate_event_payload(
    payload: Any,
    official_event_id: str,
    *,
    now_utc: datetime | None = None,
) -> dict:
    event_id = _safe(official_event_id)
    if not event_id.isdigit():
        return _fail("official ESPN event ID is required", event_id=event_id)
    if not isinstance(payload, dict):
        return _fail("Kyre Sports API response is not an object", event_id=event_id)
    if _safe(payload.get("schema_version")) != SCHEMA_VERSION:
        return _fail("Kyre Sports API schema mismatch", event_id=event_id)
    if _safe(payload.get("official_event_id")) != event_id:
        return _fail("Kyre Sports API official event identity mismatch", event_id=event_id)

    identity = payload.get("identity") or {}
    semantics = payload.get("market_semantics") or {}
    if not isinstance(identity, dict) or not isinstance(semantics, dict):
        return _fail("Kyre Sports API safety contract missing", event_id=event_id)
    if (
        identity.get("fuzzy_matching") is not False
        or identity.get("player_name_matching") is not False
        or identity.get("synthetic_event_ids") is not False
        or identity.get("synthetic_player_ids") is not False
        or semantics.get("projection_weight") != 0.0
        or semantics.get("market_context_only") is not True
        or semantics.get("may_modify_projection") is not False
        or semantics.get("stake_sizing_enabled") is not False
    ):
        return _fail("Kyre Sports API permanent safety contract failed closed", event_id=event_id)

    stamp = _captured_at(payload.get("captured_at_utc"))
    if stamp is None:
        return _fail("Kyre Sports API market timestamp missing or invalid", event_id=event_id)
    now = now_utc or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        now = now.replace(tzinfo=timezone.utc)
    now = now.astimezone(timezone.utc)
    age = (now - stamp).total_seconds()
    if age < -MAX_FUTURE_SKEW_SECONDS:
        return _fail("Kyre Sports API market timestamp is in the future", event_id=event_id)
    if age > MAX_MARKET_AGE_SECONDS:
        return _fail("Kyre Sports API market price is stale", event_id=event_id)

    rows = payload.get("props") or []
    if not isinstance(rows, list):
        return _fail("Kyre Sports API props payload is invalid", event_id=event_id)

    props: list[dict] = []
    seen: set[str] = set()
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        athlete_id = _safe(raw.get("official_athlete_id"))
        team_id = _safe(raw.get("official_team_id"))
        if (
            _safe(raw.get("official_event_id")) != event_id
            or not athlete_id.isdigit()
            or not team_id.isdigit()
            or _safe(raw.get("market_type")).lower() != "passing_yards"
            or _safe(raw.get("sportsbook")).lower() != "fanduel"
            or _safe(raw.get("line_status")).lower() != "active"
            or not _line_ok(raw.get("line"))
            or not _american_ok(raw.get("over_odds"))
            or not _american_ok(raw.get("under_odds"))
        ):
            continue
        if athlete_id in seen:
            return _fail("Kyre Sports API returned ambiguous duplicate athlete markets", event_id=event_id)
        seen.add(athlete_id)
        props.append(dict(raw))

    if payload.get("market_available") is True and not props:
        return _fail("Kyre Sports API marked market available but no certified prop survived validation", event_id=event_id)

    return {
        "ready": True,
        "reason": "",
        "schema_version": SCHEMA_VERSION,
        "official_event_id": event_id,
        "sportsbook": "FanDuel",
        "captured_at_utc": stamp.isoformat(),
        "age_seconds": max(0.0, age),
        "market_available": bool(props),
        "props": props,
        "projection_weight": 0.0,
        "market_context_only": True,
        "stake_sizing_enabled": False,
    }


def fetch_event_market(
    official_event_id: str,
    *,
    now_utc: datetime | None = None,
    base_url: str | None = None,
) -> dict:
    event_id = _safe(official_event_id)
    if not event_id.isdigit():
        return _fail("official ESPN event ID is required", event_id=event_id)
    url = f"{_safe(base_url, _api_base_url()).rstrip('/')}/api/v1/nfl/passing-yards"

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
            # Unknown/non-transient request failures remain one-shot and fail closed.
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


def market_for_athlete(event_market: dict, official_athlete_id: str) -> dict:
    athlete_id = _safe(official_athlete_id)
    event_id = _safe((event_market or {}).get("official_event_id"))
    if not athlete_id.isdigit():
        return _fail("official ESPN athlete ID is required", event_id=event_id, athlete_id=athlete_id)
    if not (event_market or {}).get("ready"):
        return _fail(_safe((event_market or {}).get("reason"), "Kyre Sports API event market unavailable"), event_id=event_id, athlete_id=athlete_id, http=(event_market or {}).get("http"))
    matches = [
        row for row in (event_market.get("props") or [])
        if _safe((row or {}).get("official_athlete_id")) == athlete_id
    ]
    if len(matches) != 1:
        return _fail(
            "fresh exact-ID Passing Yards market unavailable for this quarterback" if not matches else "ambiguous exact-ID Passing Yards markets for this quarterback",
            event_id=event_id,
            athlete_id=athlete_id,
            http=event_market.get("http"),
        )
    row = dict(matches[0])
    row.update({
        "ready": True,
        "reason": "",
        "captured_at_utc": event_market.get("captured_at_utc"),
        "age_seconds": event_market.get("age_seconds"),
        "projection_weight": 0.0,
        "market_context_only": True,
        "stake_sizing_enabled": False,
    })
    return row


__all__ = [
    "DEFAULT_API_BASE_URL",
    "MAX_MARKET_AGE_SECONDS",
    "MAX_REQUEST_ATTEMPTS",
    "MODEL_VERSION",
    "REQUEST_CONNECT_TIMEOUT_SECONDS",
    "REQUEST_READ_TIMEOUT_SECONDS",
    "RETRY_BACKOFF_SECONDS",
    "fetch_event_market",
    "market_for_athlete",
    "validate_event_payload",
]
