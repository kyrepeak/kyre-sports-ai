"""Application client for the Kyre Sports API NFL Rushing Yards slate."""
from __future__ import annotations

import os
from typing import Any

import requests

DEFAULT_API_BASE_URL = "https://kyre-sports-api.vercel.app"
SCHEMA_VERSION = "nfl_rushing_yards_simple_rb_grid_v1"
REQUEST_TIMEOUT_SECONDS = 10
RETRY_TIMEOUT_SECONDS = 15
ALLOWED_MARKET_STATES = {"VERIFIED", "MARKET_NOT_POSTED", "LINE_CURRENTLY_OFF_BOARD", "DATA_UNAVAILABLE"}
ALLOWED_ROLES = {"RB1", "RB2"}


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _fail(reason: str) -> dict[str, Any]:
    return {"ready": False, "schema_version": SCHEMA_VERSION, "service": "kyre-sports-api", "gateway": "Kyre Sports API", "reason": reason, "running_backs": [], "running_back_count": 0}


def validate_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return _fail("Kyre Sports API returned an invalid payload")
    if payload.get("ready") is not True:
        return _fail(_text(payload.get("reason")) or "Kyre Sports API Rushing Yards slate is not ready")
    if _text(payload.get("schema_version")) != SCHEMA_VERSION:
        return _fail("Rushing Yards slate schema mismatch")
    if _text(payload.get("service")) != "kyre-sports-api" or _text(payload.get("gateway")) != "Kyre Sports API":
        return _fail("Application gateway ownership mismatch")
    routing = payload.get("routing") or {}
    if not isinstance(routing, dict):
        return _fail("Routing contract missing")
    if routing.get("canonical_ids") is not True or routing.get("sportsbook_line_averaging") is not False or routing.get("missing_to_zero") is not False:
        return _fail("Rushing Yards routing safety contract failed")
    if _text(routing.get("application_gateway")) != "Kyre Sports API":
        return _fail("Frontend gateway contract failed")
    cards = payload.get("running_backs") or []
    if not isinstance(cards, list):
        return _fail("Running back card collection is invalid")
    for card in cards:
        if not isinstance(card, dict):
            return _fail("Running back card is invalid")
        if not _text(card.get("player_id")).startswith("kyre:nfl:player:"):
            return _fail("Canonical player identity missing")
        if not _text(card.get("game_id")).startswith("kyre:nfl:game:"):
            return _fail("Canonical game identity missing")
        if _text(card.get("role")) not in ALLOWED_ROLES:
            return _fail("Running back role contract failed")
        market = card.get("market") or {}
        if not isinstance(market, dict) or _text(market.get("status")) not in ALLOWED_MARKET_STATES:
            return _fail("Market semantic state missing")
        if market.get("status") != "VERIFIED" and any(market.get(key) is not None for key in ("line", "over_odds", "under_odds")):
            return _fail("Unverified market may not contain fabricated numeric values")
    normalized = dict(payload)
    normalized["running_back_count"] = len(cards)
    return normalized


def load_rushing_yards_slate(target_date: str | None = None) -> dict[str, Any]:
    base = _text(os.getenv("KYRE_SPORTS_API_BASE_URL")) or DEFAULT_API_BASE_URL
    url = base.rstrip("/") + "/api/v1/nfl/rushing-yards/slate"
    params = {"date": str(target_date)[:10]} if target_date else None
    last_error = ""
    for timeout in (REQUEST_TIMEOUT_SECONDS, RETRY_TIMEOUT_SECONDS):
        try:
            response = requests.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            return validate_payload(response.json())
        except requests.exceptions.ReadTimeout as exc:
            last_error = f"ReadTimeout:{exc}"
            continue
        except Exception as exc:
            return _fail(f"Kyre Sports API request failed: {type(exc).__name__}")
    return _fail(f"Kyre Sports API request timed out after one bounded retry: {last_error}")


__all__ = ["DEFAULT_API_BASE_URL", "SCHEMA_VERSION", "load_rushing_yards_slate", "validate_payload"]
