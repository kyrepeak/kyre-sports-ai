"""Render-only CFB FanDuel refresh overlay.

The frozen CFB market cache, parser/normalizer, identity layer, and projection
semantics remain unchanged. This module swaps only the outbound provider fetch
used by the shared Render host so the existing cache refresh boundary can reuse
the urllib transport already proven by the hosted MLB FanDuel collector.
"""
from __future__ import annotations

from fastapi import HTTPException

from sports_api.api import cfb_markets as frozen_markets
from sports_api.collectors.cfb_fanduel_direct import (
    CFBFanDuelCollectorError,
    collect_fanduel_cfb_total_feed,
)
from sports_api.collectors.cfb_fanduel_hosted_transport_v1 import (
    fetch_fanduel_ncaaf_page_hosted,
)

MODEL_VERSION = "CFB RENDER FANDUEL TRANSPORT V1"
PROJECTION_WEIGHT = 0.0
MAY_MODIFY_PROJECTION = False


def _refresh_from_fanduel_hosted() -> dict:
    try:
        snapshot = collect_fanduel_cfb_total_feed(
            page_fetcher=fetch_fanduel_ncaaf_page_hosted,
        )
        validated = frozen_markets.validate_feed(snapshot)
        frozen_markets._store_validated_feed(validated)
        return validated
    except (CFBFanDuelCollectorError, ValueError, OSError) as exc:
        raise HTTPException(
            status_code=503,
            detail="Fresh CFB FanDuel market data is temporarily unavailable.",
        ) from exc


def install_hosted_transport() -> None:
    """Install the hosted fetch at the existing refresh seam only."""
    frozen_markets._refresh_from_fanduel = _refresh_from_fanduel_hosted


__all__ = [
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "PROJECTION_WEIGHT",
    "install_hosted_transport",
]
