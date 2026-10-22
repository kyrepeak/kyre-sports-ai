"""Application client for the Kyre Sports API all-QB Passing Yards slate."""
from __future__ import annotations

from datetime import datetime
import os
from typing import Any
import requests

SCHEMA_VERSION = "nfl_passing_yards_simple_qb_grid_v1"
DEFAULT_API_BASE_URL = "https://kyre-sports-api.vercel.app"
CONNECT_TIMEOUT = 3.0
READ_TIMEOUT = 25.0


def _text(value: Any) -> str:
    return str(value or "").strip()


def _fail(reason: str, *, http: int | None = None) -> dict[str, Any]:
    return {"ready": False, "schema_version": SCHEMA_VERSION, "reason": _text(reason) or "Kyre Sports API Passing Yards slate unavailable", "http": http, "quarterbacks": []}


def validate_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return _fail("Kyre Sports API response is not an object")
    if payload.get("schema_version") != SCHEMA_VERSION or payload.get("service") != "kyre-sports-api" or payload.get("gateway") != "Kyre Sports API":
        return _fail("Kyre Sports API Passing Yards slate identity mismatch")
    if payload.get("ready") is not True:
        return _fail(_text(payload.get("reason")) or "Passing Yards slate is not ready")
    routing = payload.get("routing") or {}
    if routing.get("canonical_ids") is not True or routing.get("sportsbook_line_averaging") is not False or routing.get("missing_to_zero") is not False:
        return _fail("Kyre Sports API Passing Yards slate integrity contract failed")
    qbs = payload.get("quarterbacks")
    if not isinstance(qbs, list) or int(payload.get("quarterback_count") or -1) != len(qbs):
        return _fail("Kyre Sports API Passing Yards slate count contract failed")
    for row in qbs:
        if not isinstance(row, dict):
            return _fail("Passing Yards quarterback card is not an object")
        if not _text(row.get("player_id")).startswith("kyre:nfl:player:") or not _text(row.get("game_id")).startswith("kyre:nfl:game:"):
            return _fail("Kyre Sports API canonical identity contract failed")
        if not all(_text(row.get(key)) for key in ("qb_name", "team_abbr", "opponent_abbr", "game_time")):
            return _fail("Passing Yards quarterback identity/game context incomplete")
        market = row.get("market") or {}
        if market.get("status") == "NOT_AVAILABLE":
            if market.get("line") is not None or row.get("over_probability") is not None or row.get("under_probability") is not None:
                return _fail("Passing Yards unavailable market fabricated numeric values")
        elif market.get("status") == "VERIFIED":
            if not _text(market.get("sportsbook")) or market.get("line") is None:
                return _fail("Passing Yards verified market is incomplete")
        else:
            return _fail("Passing Yards market status must be explicit")
    return dict(payload)


def load_passing_yards_slate(target_date: str | None = None) -> dict[str, Any]:
    params: dict[str, str] = {}
    if target_date:
        try:
            params["date"] = datetime.strptime(str(target_date), "%Y-%m-%d").date().isoformat()
        except ValueError:
            return _fail("Invalid Passing Yards slate date")
    base = _text(os.environ.get("KYRE_SPORTS_API_BASE_URL")) or DEFAULT_API_BASE_URL
    url = f"{base.rstrip('/')}/api/v1/nfl/passing-yards/slate"
    try:
        response = requests.get(url, params=params, timeout=(CONNECT_TIMEOUT, READ_TIMEOUT), headers={"Accept": "application/json"})
    except requests.RequestException as exc:
        return _fail(f"Kyre Sports API request unavailable: {type(exc).__name__}")
    if response.status_code != 200:
        return _fail("Kyre Sports API Passing Yards slate request failed", http=response.status_code)
    try:
        return validate_payload(response.json())
    except ValueError:
        return _fail("Kyre Sports API returned invalid JSON", http=response.status_code)
