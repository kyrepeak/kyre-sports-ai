"""Application-side client for the Kyre Sports API Passing Yards page bundle."""
from __future__ import annotations

from datetime import datetime
import os
from typing import Any

import requests

SCHEMA_VERSION = "nfl_passing_yards_professional_v1"
DEFAULT_API_BASE_URL = "https://kyre-sports-api.onrender.com"
CONNECT_TIMEOUT = 3.0
READ_TIMEOUT = 18.0


def _safe(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


def _api_base() -> str:
    return _safe(os.environ.get("KYRE_SPORTS_API_BASE_URL"), DEFAULT_API_BASE_URL).rstrip("/")


def _fail(reason: str, *, http: int | None = None) -> dict[str, Any]:
    return {"ready":False,"schema_version":SCHEMA_VERSION,"reason":_safe(reason,"Kyre Sports API Passing Yards unavailable"),"http":http,"players":[]}


def validate_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return _fail("Kyre Sports API response is not an object")
    if _safe(payload.get("schema_version")) != SCHEMA_VERSION:
        return _fail("Kyre Sports API Passing Yards schema mismatch")
    if _safe(payload.get("service"), "kyre-sports-api") != "kyre-sports-api":
        return _fail("Kyre Sports API service identity mismatch")
    if payload.get("ready") is not True:
        return _fail(_safe(payload.get("reason"), "Passing Yards bundle is not ready"))
    game = payload.get("game")
    players = payload.get("players")
    routing = payload.get("routing")
    if not isinstance(game, dict) or not isinstance(players, list) or not isinstance(routing, dict):
        return _fail("Kyre Sports API Passing Yards bundle is incomplete")
    if routing.get("gateway") != "Kyre Sports API" or routing.get("canonical_ids") is not True:
        return _fail("Kyre Sports API routing contract failed")
    if routing.get("sportsbook_line_averaging") is not False or routing.get("missing_to_zero") is not False:
        return _fail("Kyre Sports API data-integrity contract failed")
    if routing.get("sportsbook_projection_influence") != 0.0:
        return _fail("Kyre Sports API model-independence contract failed")
    for row in players:
        if not isinstance(row, dict) or not _safe(row.get("player_id")) or not _safe(row.get("qb_name")):
            return _fail("Kyre Sports API canonical player identity failed")
        defense = row.get("pass_defense") or {}
        history = row.get("qb_vs_team_history") or {}
        if defense.get("rank") is None and defense.get("grade") != "CHECK":
            return _fail("Kyre Sports API defense-rank missing-data contract failed")
        if history.get("available") is False and history.get("avg_passing_yards") is not None:
            return _fail("Kyre Sports API history missing-data contract failed")
    out = dict(payload)
    out["ready"] = True
    return out


def load_passing_yards_page(target_date: str | None = None) -> dict[str, Any]:
    params: dict[str, str] = {}
    if target_date:
        try:
            params["date"] = datetime.strptime(str(target_date), "%Y-%m-%d").date().isoformat()
        except ValueError:
            return _fail("Invalid Passing Yards date")
    url = f"{_api_base()}/api/v1/nfl/passing-yards/page"
    try:
        response = requests.get(url, params=params, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT), headers={"Accept":"application/json"})
    except requests.RequestException as exc:
        return _fail(f"Kyre Sports API request unavailable: {type(exc).__name__}")
    if response.status_code != 200:
        return _fail("Kyre Sports API Passing Yards request failed", http=response.status_code)
    try:
        payload = response.json()
    except ValueError:
        return _fail("Kyre Sports API returned invalid JSON", http=response.status_code)
    result = validate_payload(payload)
    result["http"] = response.status_code
    return result


__all__ = ["SCHEMA_VERSION","load_passing_yards_page","validate_payload"]
