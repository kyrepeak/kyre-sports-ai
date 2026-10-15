"""NBA Spread provider-resilience Step 1 R1.

Additive transport repair for the frozen NBA Spread schedule engine.
The schedule ownership and quorum remain unchanged: NBA Official + ESPN NBA.
Only requests to cdn.nba.com receive the current browser/WAF header contract.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

import requests

import nba_spread_schedule_v1 as frozen_schedule

MODEL_VERSION = "NBA_SPREAD_PROVIDER_RESILIENCE_STEP1_R1"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_SOURCE_OWNERSHIP = False
NETWORK_CALLS_ADDED = 0

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


class _NbaCdnHeaderRepairSession:
    """Delegate HTTP while repairing only NBA Official CDN request headers."""

    def __init__(self, delegate: Any):
        self._delegate = delegate

    def get(self, url: str, *args: Any, **kwargs: Any):
        headers = dict(kwargs.pop("headers", {}) or {})
        if str(url).startswith("https://cdn.nba.com/"):
            headers.update(NBA_CDN_HEADERS)
        return self._delegate.get(url, *args, headers=headers, **kwargs)


def load_verified_nba_schedule(
    *,
    now_utc: datetime | None = None,
    days: int = frozen_schedule.ROLLING_DAYS,
    session: Any | None = None,
    timeout: float = 8.0,
) -> dict[str, Any]:
    """Run the frozen verifier with repaired NBA-CDN transport metadata."""
    delegate = session if session is not None else requests.Session()
    repaired = _NbaCdnHeaderRepairSession(delegate)
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
    "NETWORK_CALLS_ADDED",
    "NBA_CDN_HEADERS",
    "load_verified_nba_schedule",
]
