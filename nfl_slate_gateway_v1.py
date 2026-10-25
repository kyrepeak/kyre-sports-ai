"""Application client for the canonical Kyre Sports API NFL Slate route."""
from __future__ import annotations

from datetime import datetime
import os
from typing import Any

import requests


SCHEMA_VERSION = "nfl_slate_v1"
DEFAULT_API_BASE_URL = "https://kyre-sports-api.vercel.app"
CONNECT_TIMEOUT = 3.0
COLD_READ_TIMEOUT = 8.0
RETRY_READ_TIMEOUT = 12.0


def _text(value: Any) -> str:
    return str(value or "").strip()


def _fail(reason: str, *, http: int | None = None) -> dict[str, Any]:
    return {
        "ready": False,
        "schema_version": SCHEMA_VERSION,
        "reason": _text(reason) or "Kyre Sports API NFL slate unavailable",
        "http": http,
        "games": [],
        "game_count": 0,
    }


def validate_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return _fail("Kyre Sports API response is not an object")
    if payload.get("schema_version") != SCHEMA_VERSION:
        return _fail("Kyre Sports API NFL slate schema mismatch")
    if payload.get("service") != "kyre-sports-api" or payload.get("gateway") != "Kyre Sports API":
        return _fail("Kyre Sports API NFL slate identity mismatch")
    routing = payload.get("routing") or {}
    if routing.get("canonical_ids") is not True or routing.get("missing_to_zero") is not False:
        return _fail("Kyre Sports API NFL slate integrity contract failed")
    if payload.get("ready") is not True:
        return _fail(_text(payload.get("reason")) or "NFL slate is not ready")
    games = payload.get("games")
    if not isinstance(games, list) or int(payload.get("game_count") or -1) != len(games):
        return _fail("Kyre Sports API NFL slate count contract failed")
    for game in games:
        if not isinstance(game, dict):
            return _fail("NFL slate game is not an object")
        if not _text(game.get("game_id")).startswith("kyre:nfl:game:"):
            return _fail("NFL slate canonical game identity contract failed")
        if not all(_text(game.get(key)) for key in ("away", "home", "date", "kickoff")):
            return _fail("NFL slate game identity or kickoff context incomplete")
    return dict(payload)


def load_nfl_slate(target_date: str | None = None) -> dict[str, Any]:
    params: dict[str, str] = {}
    if target_date:
        try:
            params["date"] = datetime.strptime(str(target_date), "%Y-%m-%d").date().isoformat()
        except ValueError:
            return _fail("Invalid NFL slate date")
    base = _text(os.environ.get("KYRE_SPORTS_API_BASE_URL")) or DEFAULT_API_BASE_URL
    url = f"{base.rstrip('/')}/api/v1/nfl/slate"
    response = None
    for attempt, read_timeout in enumerate((COLD_READ_TIMEOUT, RETRY_READ_TIMEOUT)):
        try:
            response = requests.get(
                url,
                params=params,
                timeout=(CONNECT_TIMEOUT, read_timeout),
                headers={"Accept": "application/json"},
            )
            break
        except requests.ReadTimeout as exc:
            if attempt == 0:
                continue
            return _fail(f"Kyre Sports API request unavailable: {type(exc).__name__}")
        except requests.RequestException as exc:
            return _fail(f"Kyre Sports API request unavailable: {type(exc).__name__}")
    if response is None:
        return _fail("Kyre Sports API request unavailable")
    if response.status_code != 200:
        return _fail("Kyre Sports API NFL slate request failed", http=response.status_code)
    try:
        return validate_payload(response.json())
    except ValueError:
        return _fail("Kyre Sports API returned invalid JSON", http=response.status_code)


__all__ = ["SCHEMA_VERSION", "load_nfl_slate", "validate_payload"]
