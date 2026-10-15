"""NBA Spread provider-resilience Step 1 R1.

Additive transport repair for the frozen NBA Spread schedule engine.
The schedule ownership and quorum remain unchanged: NBA Official + ESPN NBA.
This wrapper repairs two provider-transport incompatibilities without modifying
frozen schedule logic:

1. NBA Official CDN receives the browser/WAF header contract it currently
   requires instead of the old thin bot-like request metadata.
2. ESPN date-range requests are fanned out to supported single-day scoreboard
   requests, then merged back into the exact payload shape expected by the
   frozen parser.

Provider disagreement still fails closed. No fallback provider is activated in
Step 1 and no model/projection/probability behavior changes.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

import requests

import nba_spread_schedule_v1 as frozen_schedule

MODEL_VERSION = "NBA_SPREAD_PROVIDER_RESILIENCE_STEP1_R1"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_SOURCE_OWNERSHIP = False
NETWORK_PROVIDER_COUNT_ADDED = 0
MAX_ESPN_RANGE_DAYS = 14

# Current NBA CDN browser request contract. The old schedule module deliberately
# remains frozen; this wrapper only repairs transport metadata for cdn.nba.com.
NBA_CDN_HEADERS: dict[str, str] = {
    "sec-ch-ua": '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Encoding": "gzip, deflate, br",
    "Origin": "https://www.nba.com",
    "Sec-Fetch-Site": "same-site",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Dest": "empty",
    "Referer": "https://www.nba.com/",
    "Accept-Language": "en-US,en;q=0.9",
}


class _MergedJsonResponse:
    """Minimal requests.Response-compatible wrapper for merged ESPN payloads."""

    status_code = 200

    def __init__(self, payload: dict[str, Any]):
        self._payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._payload


def _espn_range_days(raw_dates: Any) -> tuple[str, ...] | None:
    """Expand ESPN YYYYMMDD-YYYYMMDD range syntax into supported single dates."""
    text = str(raw_dates or "").strip()
    if "-" not in text:
        return None
    start_text, end_text = text.split("-", 1)
    if len(start_text) != 8 or len(end_text) != 8:
        return None
    try:
        start = datetime.strptime(start_text, "%Y%m%d").date()
        end = datetime.strptime(end_text, "%Y%m%d").date()
    except ValueError:
        return None
    if end < start:
        return None
    span = (end - start).days + 1
    if span < 1 or span > MAX_ESPN_RANGE_DAYS:
        return None
    return tuple((start + timedelta(days=offset)).strftime("%Y%m%d") for offset in range(span))


class _NbaProviderTransportRepairSession:
    """Delegate HTTP while repairing only NBA Official and ESPN transport."""

    def __init__(self, delegate: Any):
        self._delegate = delegate

    def _get_espn_range(self, url: str, *, days: tuple[str, ...], args: tuple[Any, ...], kwargs: dict[str, Any]):
        original_params = dict(kwargs.get("params") or {})
        merged_payload: dict[str, Any] = {}
        merged_events: list[dict[str, Any]] = []
        seen_event_ids: set[str] = set()

        for day in days:
            call_kwargs = dict(kwargs)
            params = dict(original_params)
            params["dates"] = day
            call_kwargs["params"] = params
            response = self._delegate.get(url, *args, **call_kwargs)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("ESPN scoreboard returned non-object JSON")
            if not merged_payload:
                merged_payload = dict(payload)
            for event in payload.get("events") or []:
                if not isinstance(event, dict):
                    continue
                event_id = str(event.get("id") or "").strip()
                dedupe_key = event_id or repr(event)
                if dedupe_key in seen_event_ids:
                    continue
                seen_event_ids.add(dedupe_key)
                merged_events.append(event)

        merged_payload["events"] = merged_events
        return _MergedJsonResponse(merged_payload)

    def get(self, url: str, *args: Any, **kwargs: Any):
        headers = dict(kwargs.pop("headers", {}) or {})
        normalized_url = str(url)

        if normalized_url.startswith("https://cdn.nba.com/"):
            headers.update(NBA_CDN_HEADERS)
            return self._delegate.get(url, *args, headers=headers, **kwargs)

        if normalized_url.startswith(frozen_schedule.ESPN_SCOREBOARD_URL):
            params = dict(kwargs.get("params") or {})
            range_days = _espn_range_days(params.get("dates"))
            if range_days:
                kwargs["headers"] = headers
                return self._get_espn_range(url, days=range_days, args=args, kwargs=kwargs)

        return self._delegate.get(url, *args, headers=headers, **kwargs)


def load_verified_nba_schedule(
    *,
    now_utc: datetime | None = None,
    days: int = frozen_schedule.ROLLING_DAYS,
    session: Any | None = None,
    timeout: float = 8.0,
) -> dict[str, Any]:
    """Run the frozen verifier with repaired provider transport semantics."""
    delegate = session if session is not None else requests.Session()
    repaired = _NbaProviderTransportRepairSession(delegate)
    return frozen_schedule.load_verified_nba_schedule(
        now_utc=now_utc,
        days=days,
        session=repaired,
        timeout=timeout,
    )


__all__ = [
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_SOURCE_OWNERSHIP",
    "NETWORK_PROVIDER_COUNT_ADDED",
    "MAX_ESPN_RANGE_DAYS",
    "NBA_CDN_HEADERS",
    "load_verified_nba_schedule",
]
