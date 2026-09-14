"""Hosted-runtime FanDuel NCAAF transport adapter.

This module changes transport only. It intentionally reuses the frozen CFB
FanDuel parser/normalizer and does not alter event identity, market selection,
cache freshness, or projection semantics.

The shared Render host already uses urllib successfully for the MLB FanDuel
collector. This adapter applies that same one-GET standard-library transport to
the CFB NCAAF content page while preserving the Step 1/2 response contract.
"""
from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from sports_api.collectors.cfb_fanduel_direct import (
    CFBFanDuelCollectorError,
    DEFAULT_TIMEOUT_SECONDS,
    FANDUEL_BASE_URL,
    FANDUEL_HEADERS,
    FANDUEL_PUBLIC_WEB_KEY,
    MAX_RESPONSE_BYTES,
    NCAAF_PAGE_ID,
)

TRANSPORT_VERSION = "CFB FANDUEL HOSTED TRANSPORT V1"


def fetch_fanduel_ncaaf_page_hosted(
    *,
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    """Fetch the same anonymous FanDuel NCAAF page with one urllib GET."""
    params = {
        "_ak": FANDUEL_PUBLIC_WEB_KEY,
        "page": "CUSTOM",
        "customPageId": NCAAF_PAGE_ID,
        "timezone": "America/New_York",
    }
    query = urlencode({str(key): str(value) for key, value in params.items()})
    url = f"{FANDUEL_BASE_URL}/sbapi/content-managed-page"
    request = Request(
        f"{url}?{query}",
        headers=dict(FANDUEL_HEADERS),
        method="GET",
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            status = int(getattr(response, "status", 0) or 0)
            if status != 200:
                raise CFBFanDuelCollectorError(
                    f"Hosted FanDuel CFB GET returned HTTP {status}"
                )
            raw = response.read(MAX_RESPONSE_BYTES + 1)
    except CFBFanDuelCollectorError:
        raise
    except (HTTPError, URLError, OSError) as exc:
        raise CFBFanDuelCollectorError(
            f"Hosted FanDuel CFB GET failed: {type(exc).__name__}"
        ) from exc

    if len(raw) > MAX_RESPONSE_BYTES:
        raise CFBFanDuelCollectorError(
            f"FanDuel response exceeded {MAX_RESPONSE_BYTES} bytes"
        )

    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CFBFanDuelCollectorError(
            "Hosted FanDuel CFB response was not valid UTF-8 JSON"
        ) from exc
    if not isinstance(payload, dict):
        raise CFBFanDuelCollectorError(
            "Hosted FanDuel CFB response was not a JSON object"
        )
    return payload


__all__ = [
    "TRANSPORT_VERSION",
    "fetch_fanduel_ncaaf_page_hosted",
]
