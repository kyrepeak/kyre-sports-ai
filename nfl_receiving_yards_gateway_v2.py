"""Application client for the Kyre Sports API Receiving Yards slate V2."""
from __future__ import annotations

import os
from typing import Any

import requests

DATA_GATEWAY = "kyre_sports_api"
SCHEMA_VERSION = "nfl_receiving_yards_slate_v2"
DEFAULT_API_BASE_URL = "https://kyre-sports-api.vercel.app"
SLATE_PATH = "/api/v1/nfl/receiving-yards/slate-v2"
CONNECT_TIMEOUT = 3.0
READ_TIMEOUT = 12.0


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _fail(reason: str, *, http: int | None = None) -> dict[str, Any]:
    return {
        "ready": False,
        "reason": _text(reason) or "Kyre Sports API Receiving Yards unavailable",
        "schema_version": SCHEMA_VERSION,
        "games": [],
        "game_count": 0,
        "http": http,
    }


def validate_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return _fail("Kyre Sports API response is not an object")
    if payload.get("schema_version") != SCHEMA_VERSION:
        return _fail("Kyre Sports API Receiving Yards schema mismatch")
    if payload.get("service") != "kyre-sports-api" or payload.get("gateway") != "Kyre Sports API":
        return _fail("Kyre Sports API identity mismatch")
    if payload.get("ready") is not True:
        return _fail(_text(payload.get("reason")) or "Receiving Yards slate is not ready")
    games = payload.get("games")
    if not isinstance(games, list) or int(payload.get("game_count") or 0) != len(games):
        return _fail("Receiving Yards game-count contract failed")
    if payload.get("sportsbook_projection_influence") != 0.0:
        return _fail("Receiving Yards market isolation contract failed")
    routing = payload.get("routing") or {}
    if games and (
        routing.get("application_gateway") != "KYRE_SPORTS_API"
        or routing.get("player_name_matching") is not False
        or routing.get("fuzzy_matching") is not False
        or routing.get("missing_to_zero") is not False
        or routing.get("semantic_empty_states") is not True
        or routing.get("sportsbook_projection_influence") != 0.0
    ):
        return _fail("Receiving Yards routing integrity contract failed")
    for game in games:
        if not isinstance(game, dict):
            return _fail("Receiving Yards game payload is invalid")
        if not _text(game.get("canonical_game_id")).startswith("kyre:nfl:game:"):
            return _fail("Receiving Yards canonical game identity failed")
        teams = game.get("teams")
        if not isinstance(teams, list) or len(teams) != 2:
            return _fail("Receiving Yards game must contain two teams")
    return dict(payload)


def load_receiving_yards_slate(target_date: str | None = None) -> dict[str, Any]:
    base = _text(os.environ.get("KYRE_SPORTS_API_BASE_URL")) or DEFAULT_API_BASE_URL
    params = {"date": str(target_date)} if target_date else {}
    try:
        response = requests.get(
            f"{base.rstrip('/')}{SLATE_PATH}",
            params=params,
            timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
            headers={"Accept": "application/json"},
        )
    except requests.RequestException as exc:
        return _fail(f"Kyre Sports API request unavailable: {type(exc).__name__}")
    if response.status_code != 200:
        return _fail("Kyre Sports API Receiving Yards request failed", http=response.status_code)
    try:
        return validate_payload(response.json())
    except ValueError:
        return _fail("Kyre Sports API returned invalid JSON", http=response.status_code)


__all__ = [
    "DATA_GATEWAY", "SCHEMA_VERSION", "SLATE_PATH", "load_receiving_yards_slate", "validate_payload",
]
