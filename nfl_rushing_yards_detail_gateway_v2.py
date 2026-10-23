"""Application client for Kyre Sports API NFL Rushing Yards Page 2 detail."""
from __future__ import annotations

import os
from typing import Any

import requests

DEFAULT_API_BASE_URL = "https://kyre-sports-api.vercel.app"
SCHEMA_VERSION = "nfl_rushing_yards_page2_command_center_v2"
REQUEST_TIMEOUT_SECONDS = 12
RETRY_TIMEOUT_SECONDS = 18


def _text(value: Any) -> str:
    return str(value if value is not None else "").strip()


def _fail(reason: str) -> dict[str, Any]:
    return {
        "ready": False,
        "schema_version": SCHEMA_VERSION,
        "service": "kyre-sports-api",
        "gateway": "Kyre Sports API",
        "reason": reason,
        "detail": {},
    }


def validate_payload(payload: Any, *, player_id: str, game_id: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return _fail("Kyre Sports API returned an invalid Page 2 payload")
    if payload.get("ready") is not True:
        return _fail(_text(payload.get("reason")) or "Kyre Sports API Rushing Yards detail is not ready")
    if _text(payload.get("schema_version")) != SCHEMA_VERSION:
        return _fail("Rushing Yards Page 2 schema mismatch")
    if _text(payload.get("service")) != "kyre-sports-api" or _text(payload.get("gateway")) != "Kyre Sports API":
        return _fail("Application gateway ownership mismatch")
    if _text(payload.get("player_id")) != _text(player_id) or _text(payload.get("game_id")) != _text(game_id):
        return _fail("Canonical player/game detail identity mismatch")
    if not _text(player_id).startswith("kyre:nfl:player:") or not _text(game_id).startswith("kyre:nfl:game:"):
        return _fail("Canonical Kyre identity required")
    if not isinstance(payload.get("detail"), dict):
        return _fail("Rushing Yards Page 2 detail block missing")
    return dict(payload)


def load_rushing_yards_detail(*, player_id: str, game_id: str, target_date: str | None = None) -> dict[str, Any]:
    base = _text(os.getenv("KYRE_SPORTS_API_BASE_URL")) or DEFAULT_API_BASE_URL
    url = base.rstrip("/") + "/api/v1/nfl/rushing-yards/detail"
    params: dict[str, str] = {"player_id": player_id, "game_id": game_id}
    if target_date:
        params["date"] = str(target_date)[:10]
    last_error = ""
    for timeout in (REQUEST_TIMEOUT_SECONDS, RETRY_TIMEOUT_SECONDS):
        try:
            response = requests.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            return validate_payload(response.json(), player_id=player_id, game_id=game_id)
        except requests.exceptions.ReadTimeout as exc:
            last_error = f"ReadTimeout:{exc}"
            continue
        except Exception as exc:
            return _fail(f"Kyre Sports API Page 2 request failed: {type(exc).__name__}")
    return _fail(f"Kyre Sports API Page 2 request timed out after one bounded retry: {last_error}")


__all__ = ["DEFAULT_API_BASE_URL", "SCHEMA_VERSION", "load_rushing_yards_detail", "validate_payload"]
