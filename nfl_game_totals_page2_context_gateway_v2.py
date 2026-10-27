"""Fail-closed Streamlit client for Kyre Sports API NFL Game Totals Page 2 context."""
from __future__ import annotations

import os
from typing import Any, Mapping

import requests

SCHEMA_VERSION = "nfl_game_totals_page2_context_v2"
GATEWAY = "KYRE_SPORTS_API"
ENDPOINT_PATH = "/api/v1/nfl/game-totals/page2-context"
DEFAULT_API_BASE_URL = "https://kyre-sports-api.onrender.com"
CONNECT_TIMEOUT_SECONDS = 3.0
READ_TIMEOUT_SECONDS = 15.0


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _empty_history(reason: str) -> dict[str, Any]:
    return {"ready": False, "reason": reason, "source": "Kyre Sports API", "display_only": True, "model_influence": 0.0, "games": 0, "overs": 0, "unders": 0, "pushes": 0, "line_verified_games": 0, "average_combined_score": None, "meetings": []}


def _empty_availability(reason: str) -> dict[str, Any]:
    return {"ready": False, "reason": reason, "source": "Kyre Sports API", "display_only": True, "model_influence": 0.0, "impact": "UNAVAILABLE", "away": [], "home": []}


def _fail(reason: str) -> dict[str, Any]:
    return {"ready": False, "reason": reason, "history": _empty_history(reason), "availability": _empty_availability(reason), "gateway": GATEWAY, "sportsbook_projection_influence": 0.0, "stake_sizing_enabled": False, "wager_actions": False}


def validate_page2_context_payload(payload: Any, *, away_abbr: str, home_abbr: str) -> dict[str, Any]:
    away = _text(away_abbr).upper(); home = _text(home_abbr).upper()
    if not isinstance(payload, Mapping):
        return _fail("Kyre Sports API Page 2 context response is invalid.")
    if _text(payload.get("schema_version")) != SCHEMA_VERSION or _text(payload.get("gateway")) != GATEWAY:
        return _fail("Kyre Sports API Page 2 context schema mismatch.")
    identity = payload.get("identity") if isinstance(payload.get("identity"), Mapping) else {}
    if _text(identity.get("away_abbr")).upper() != away or _text(identity.get("home_abbr")).upper() != home:
        return _fail("Kyre Sports API Page 2 context identity mismatch.")
    semantics = payload.get("semantics") if isinstance(payload.get("semantics"), Mapping) else {}
    if (
        semantics.get("history_model_influence") != 0.0
        or semantics.get("availability_model_influence") != 0.0
        or semantics.get("sportsbook_projection_influence") != 0.0
        or semantics.get("stake_sizing_enabled") is not False
        or semantics.get("wager_actions") is not False
    ):
        return _fail("Kyre Sports API Page 2 safety contract failed closed.")
    history = dict(payload.get("history")) if isinstance(payload.get("history"), Mapping) else _empty_history("History context unavailable.")
    availability = dict(payload.get("availability")) if isinstance(payload.get("availability"), Mapping) else _empty_availability("Availability context unavailable.")
    if history.get("model_influence") != 0.0 or history.get("display_only") is not True:
        history = _empty_history("History safety contract failed closed.")
    if availability.get("model_influence") != 0.0 or availability.get("display_only") is not True:
        availability = _empty_availability("Availability safety contract failed closed.")
    return {"ready": history.get("ready") is True or availability.get("ready") is True, "reason": _text(payload.get("reason")), "history": history, "availability": availability, "gateway": GATEWAY, "sportsbook_projection_influence": 0.0, "stake_sizing_enabled": False, "wager_actions": False}


def load_game_total_page2_context(*, away_abbr: str, home_abbr: str, history_limit: int = 3, availability_limit: int = 2) -> dict[str, Any]:
    away = _text(away_abbr).upper(); home = _text(home_abbr).upper()
    if not away or not home or away == home:
        return _fail("Exact NFL team identity is required.")
    base = _text(os.environ.get("KYRE_SPORTS_API_BASE_URL")) or DEFAULT_API_BASE_URL
    try:
        response = requests.get(
            base.rstrip("/") + ENDPOINT_PATH,
            params={"away": away, "home": home, "history_limit": int(history_limit), "availability_limit": int(availability_limit)},
            timeout=(CONNECT_TIMEOUT_SECONDS, READ_TIMEOUT_SECONDS),
            headers={"Accept": "application/json", "User-Agent": "KyreSportsAI-GameTotals-Page2/2.0"},
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        return _fail(f"Kyre Sports API Page 2 context unavailable ({type(exc).__name__}).")
    return validate_page2_context_payload(payload, away_abbr=away, home_abbr=home)


__all__ = ["ENDPOINT_PATH", "GATEWAY", "SCHEMA_VERSION", "load_game_total_page2_context", "validate_page2_context_payload"]
