"""Kyre Sports API client V2 for NFL Passing Yards Step 10 transport reliability.

Additive transport/cache wrapper over the certified V1 market contract. V2 does
not loosen identity, freshness, market, sportsbook, or model-safety validation.
It reuses an HTTP session, keeps a small in-process payload cache so Streamlit
reruns do not repeatedly hit the same event endpoint, and permits exactly one
bounded retry for transient connection/read failures against the same exact
event endpoint. A cached payload may rescue a transient request failure
only when V1 re-validates that exact payload as still fresh (<= 300 seconds).

Permanent contract remains unchanged:
- exact official ESPN event ID;
- exact official ESPN athlete ID;
- no player-name/fuzzy/synthetic identity;
- FanDuel Passing Yards market context only;
- sportsbook projection influence = 0.0%;
- stake sizing OFF;
- malformed/stale/unsafe data fails closed.
"""
from __future__ import annotations

from copy import deepcopy
from threading import RLock
import time
from typing import Any

import requests

import nfl_passing_yards_market_api_v1 as prior

MODEL_VERSION = "NFL PASSING YARDS KYRE SPORTS API CLIENT V2 • BOUNDED TRANSPORT + FRESH CACHE"
FROZEN_VALIDATION_OWNER = "nfl_passing_yards_market_api_v1"
DEFAULT_API_BASE_URL = prior.DEFAULT_API_BASE_URL
SCHEMA_VERSION = prior.SCHEMA_VERSION
MAX_MARKET_AGE_SECONDS = prior.MAX_MARKET_AGE_SECONDS
REQUEST_CONNECT_TIMEOUT_SECONDS = 3.0
REQUEST_READ_TIMEOUT_SECONDS = 15.0
MAX_REQUEST_ATTEMPTS = 2
RETRY_BACKOFF_SECONDS = 0.35
HOT_CACHE_TTL_SECONDS = 20.0
MAX_CACHE_ENTRIES = 24
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False

_SESSION = requests.Session()
_CACHE_LOCK = RLock()
# event_id -> {payload, stored_monotonic}
_PAYLOAD_CACHE: dict[str, dict[str, Any]] = {}
_TRANSIENT_REQUEST_EXCEPTIONS = (
    requests.exceptions.ConnectTimeout,
    requests.exceptions.ReadTimeout,
    requests.exceptions.ConnectionError,
)


def _safe(value: Any, default: str = "") -> str:
    return prior._safe(value, default)


def _fail(reason: str, *, event_id: str = "", http: int | None = None) -> dict:
    return prior._fail(reason, event_id=event_id, http=http)


def _cache_put(event_id: str, payload: dict) -> None:
    with _CACHE_LOCK:
        if len(_PAYLOAD_CACHE) >= MAX_CACHE_ENTRIES and event_id not in _PAYLOAD_CACHE:
            oldest_key = min(
                _PAYLOAD_CACHE,
                key=lambda key: float((_PAYLOAD_CACHE.get(key) or {}).get("stored_monotonic") or 0.0),
            )
            _PAYLOAD_CACHE.pop(oldest_key, None)
        _PAYLOAD_CACHE[event_id] = {
            "payload": deepcopy(payload),
            "stored_monotonic": time.monotonic(),
        }


def _cached_validated(event_id: str, *, now_utc=None, hot_only: bool = False) -> dict | None:
    with _CACHE_LOCK:
        entry = deepcopy(_PAYLOAD_CACHE.get(event_id) or {})
    if not entry:
        return None
    if hot_only:
        stored = float(entry.get("stored_monotonic") or 0.0)
        if stored <= 0.0 or (time.monotonic() - stored) > HOT_CACHE_TTL_SECONDS:
            return None
    payload = entry.get("payload")
    validated = prior.validate_event_payload(payload, event_id, now_utc=now_utc)
    if not validated.get("ready"):
        return None
    return validated


def _with_transport_meta(
    result: dict,
    *,
    source: str,
    url: str,
    request_attempts: int,
    http: int | None = None,
    warning: str = "",
) -> dict:
    out = dict(result or {})
    out["transport_source"] = source
    out["api_url"] = url
    out["request_attempts"] = int(request_attempts)
    if http is not None:
        out["http"] = int(http)
    if warning:
        out["transport_warning"] = warning
    out["projection_weight"] = 0.0
    out["market_context_only"] = True
    out["stake_sizing_enabled"] = False
    return out


def reset_transport_cache() -> None:
    """Deterministic test/admin helper; no market semantics are changed."""
    with _CACHE_LOCK:
        _PAYLOAD_CACHE.clear()


def fetch_event_market(
    official_event_id: str,
    *,
    now_utc=None,
    base_url: str | None = None,
) -> dict:
    event_id = _safe(official_event_id)
    if not event_id.isdigit():
        return _fail("official ESPN event ID is required", event_id=event_id)

    url = f"{_safe(base_url, prior._api_base_url()).rstrip('/')}/api/v1/nfl/passing-yards"

    # Streamlit reruns commonly request the same event seconds apart. Reuse only
    # a payload that still passes the complete frozen V1 validation contract.
    hot = _cached_validated(event_id, now_utc=now_utc, hot_only=True)
    if hot is not None:
        return _with_transport_meta(
            hot,
            source="hot-cache",
            url=url,
            request_attempts=0,
            http=200,
        )

    response = None
    request_attempts = 0
    for attempt in range(1, MAX_REQUEST_ATTEMPTS + 1):
        request_attempts = attempt
        try:
            response = _SESSION.get(
                url,
                params={"event_id": event_id},
                timeout=(REQUEST_CONNECT_TIMEOUT_SECONDS, REQUEST_READ_TIMEOUT_SECONDS),
                headers={"Accept": "application/json", "User-Agent": "KyreSportsAI-Streamlit/2.0"},
            )
            break
        except _TRANSIENT_REQUEST_EXCEPTIONS as exc:
            warning = f"Kyre Sports API request failed: {type(exc).__name__}"
            cached = _cached_validated(event_id, now_utc=now_utc, hot_only=False)
            if cached is not None:
                return _with_transport_meta(
                    cached,
                    source="fresh-cache-after-transient-error",
                    url=url,
                    request_attempts=attempt,
                    http=200,
                    warning=warning,
                )
            if attempt < MAX_REQUEST_ATTEMPTS:
                time.sleep(RETRY_BACKOFF_SECONDS)
                continue
            out = _fail(warning, event_id=event_id)
            return _with_transport_meta(
                out,
                source="network-failed-closed",
                url=url,
                request_attempts=attempt,
            )
        except Exception as exc:
            out = _fail(f"Kyre Sports API request failed: {type(exc).__name__}", event_id=event_id)
            return _with_transport_meta(
                out,
                source="network-failed-closed",
                url=url,
                request_attempts=attempt,
            )

    status = int(getattr(response, "status_code", 0) or 0)
    if status != 200:
        out = _fail(f"Kyre Sports API returned HTTP {status}", event_id=event_id, http=status)
        return _with_transport_meta(out, source="network-http-failed-closed", url=url, request_attempts=request_attempts, http=status)
    try:
        payload = response.json()
    except Exception:
        out = _fail("Kyre Sports API returned invalid JSON", event_id=event_id, http=status)
        return _with_transport_meta(out, source="network-json-failed-closed", url=url, request_attempts=request_attempts, http=status)

    validated = prior.validate_event_payload(payload, event_id, now_utc=now_utc)
    if validated.get("ready"):
        _cache_put(event_id, payload)
    return _with_transport_meta(
        validated,
        source="network",
        url=url,
        request_attempts=request_attempts,
        http=status,
    )


def market_for_athlete(event_market: dict, official_athlete_id: str) -> dict:
    return prior.market_for_athlete(event_market, official_athlete_id)


def validate_event_payload(payload: Any, official_event_id: str, *, now_utc=None) -> dict:
    return prior.validate_event_payload(payload, official_event_id, now_utc=now_utc)


__all__ = [
    "DEFAULT_API_BASE_URL",
    "FROZEN_VALIDATION_OWNER",
    "HOT_CACHE_TTL_SECONDS",
    "MAX_MARKET_AGE_SECONDS",
    "MAX_REQUEST_ATTEMPTS",
    "MODEL_VERSION",
    "REQUEST_CONNECT_TIMEOUT_SECONDS",
    "REQUEST_READ_TIMEOUT_SECONDS",
    "RETRY_BACKOFF_SECONDS",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "fetch_event_market",
    "market_for_athlete",
    "reset_transport_cache",
    "validate_event_payload",
]
