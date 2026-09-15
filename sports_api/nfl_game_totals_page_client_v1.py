"""Read-only Streamlit client for the certified NFL Game Totals market API.

The page never guesses identity or market values. Every response must preserve the
exact ESPN event identity, the certified v1 contract, FanDuel provider identity,
0.0 sportsbook projection weight, and disabled wager actions. Any transport or
contract drift fails closed.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from typing import Any, Callable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

DEFAULT_API_BASE_URL = "https://kyre-sports-api.onrender.com"
API_PATH = "/api/v1/nfl/totals/market"
API_BASE_URL_ENV = "NFL_GAME_TOTALS_API_BASE_URL"
REQUEST_TIMEOUT_SECONDS = float(os.getenv("NFL_GAME_TOTALS_PAGE_TIMEOUT_SECONDS", "5"))
MAX_WORKERS = max(1, min(8, int(os.getenv("NFL_GAME_TOTALS_PAGE_MAX_WORKERS", "8"))))


def _fail_closed(event_id: str, reason: str) -> dict[str, Any]:
    return {
        "event_id": str(event_id),
        "provider": "fanduel",
        "provider_event_id": None,
        "captured_at_utc": None,
        "ready": False,
        "market_available": False,
        "markets": [],
        "diagnostics": [str(reason)],
        "contract": "nfl-game-totals-market-v1",
        "identity_mode": "exact_espn_event_id",
        "sportsbook_projection_weight": 0.0,
        "projection_use": "context_only",
        "wager_actions_enabled": False,
    }


def _validate_payload(payload: Any, event_id: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("market API returned a non-object payload")
    if str(payload.get("event_id") or "") != str(event_id):
        raise ValueError("payload event_id did not match requested ESPN event_id")
    if payload.get("contract") != "nfl-game-totals-market-v1":
        raise ValueError("market API contract changed from nfl-game-totals-market-v1")
    if payload.get("identity_mode") != "exact_espn_event_id":
        raise ValueError("identity_mode did not remain exact_espn_event_id")
    if str(payload.get("provider") or "").lower() != "fanduel":
        raise ValueError("market provider changed from fanduel")
    try:
        projection_weight = float(payload.get("sportsbook_projection_weight"))
    except (TypeError, ValueError):
        raise ValueError("sportsbook projection weight was not numeric") from None
    if projection_weight != 0.0:
        raise ValueError("sportsbook projection weight changed from 0.0")
    if payload.get("wager_actions_enabled") is not False:
        raise ValueError("wager actions unexpectedly enabled")

    ready = payload.get("ready") is True
    available = payload.get("market_available") is True
    markets = payload.get("markets")
    if not isinstance(markets, list):
        raise ValueError("markets was not a list")
    if ready or available:
        if not (ready and available and len(markets) == 1):
            raise ValueError("ready market payload did not contain exactly one market")
        market = markets[0]
        if not isinstance(market, dict):
            raise ValueError("market row was not an object")
        if str(market.get("sportsbook") or "").lower() != "fanduel":
            raise ValueError("market sportsbook changed from fanduel")
        if market.get("active") is not True:
            raise ValueError("market was not active")
        for key in ("total", "over_price", "under_price"):
            try:
                float(market.get(key))
            except (TypeError, ValueError):
                raise ValueError(f"market {key} was not numeric") from None
    return payload


def fetch_game_total_market(
    event_id: str,
    *,
    base_url: str | None = None,
    timeout: float | None = None,
    opener: Callable[..., Any] = urlopen,
) -> dict[str, Any]:
    event_id = str(event_id or "").strip()
    if not event_id.isdigit():
        return _fail_closed(event_id, "event_id must be an official numeric ESPN event ID")

    host = str(base_url or os.getenv(API_BASE_URL_ENV) or DEFAULT_API_BASE_URL).rstrip("/")
    query = urlencode({"event_id": event_id})
    request = Request(
        f"{host}{API_PATH}?{query}",
        headers={
            "Accept": "application/json",
            "User-Agent": "kyre-sports-ai/nfl-game-totals-page-v2",
        },
    )
    try:
        with opener(request, timeout=float(timeout or REQUEST_TIMEOUT_SECONDS)) as response:
            payload = json.load(response)
        return _validate_payload(payload, event_id)
    except Exception as exc:
        return _fail_closed(event_id, exc)


def fetch_many_game_total_markets(
    event_ids: list[str] | tuple[str, ...],
    *,
    base_url: str | None = None,
    timeout: float | None = None,
) -> dict[str, dict[str, Any]]:
    """Fetch independent matchup markets concurrently without cross-game guessing."""
    ordered = list(dict.fromkeys(str(value or "").strip() for value in event_ids))
    if not ordered:
        return {}

    output: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=min(MAX_WORKERS, len(ordered))) as pool:
        futures = {
            pool.submit(fetch_game_total_market, event_id, base_url=base_url, timeout=timeout): event_id
            for event_id in ordered
        }
        for future in as_completed(futures):
            event_id = futures[future]
            try:
                output[event_id] = future.result()
            except Exception as exc:  # defensive; fetch_game_total_market already fails closed
                output[event_id] = _fail_closed(event_id, exc)
    return output


__all__ = [
    "API_BASE_URL_ENV",
    "API_PATH",
    "DEFAULT_API_BASE_URL",
    "MAX_WORKERS",
    "REQUEST_TIMEOUT_SECONDS",
    "fetch_game_total_market",
    "fetch_many_game_total_markets",
]
