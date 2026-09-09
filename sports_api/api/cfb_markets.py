"""College Football market-data transport for the Kyre Sports API.

Step 1 of the CFB O/U odds integration. This module is intentionally isolated
from projection code: sportsbook/market information is context only and carries
0% projection weight.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hmac
import json
import os
from pathlib import Path
import tempfile
from typing import Any

from fastapi import APIRouter, Body, Header, HTTPException, Query

router = APIRouter(prefix="/api/v1/cfb/markets", tags=["cfb"])

SCHEMA_VERSION = "cfb_market_feed_v1"
FEED_PATH_ENV = "CFB_KYRE_MARKET_FEED_PATH"
INGEST_TOKEN_ENV = "CFB_KYRE_MARKET_INGEST_TOKEN"
DEFAULT_FEED_PATH = "/var/lib/kyre-sports-api/cfb_market_feed.json"
MAX_FEED_BYTES = 5_000_000
_ALLOWED_LINE_STATUS = {"open", "active", "suspended", "closed", "final", "unknown"}


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _aware_iso(value: Any, field: str) -> str:
    text = _clean(value)
    if not text:
        raise ValueError(f"{field} is required")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat()


def _feed_path() -> Path:
    path = Path(os.environ.get(FEED_PATH_ENV, DEFAULT_FEED_PATH)).expanduser()
    if not path.is_absolute():
        raise ValueError(f"{FEED_PATH_ENV} must be an absolute path")
    return path


def _validate_game(row: Any) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise ValueError("every game must be a JSON object")
    game_id = _clean(row.get("game_id"))
    home_team = _clean(row.get("home_team"))
    away_team = _clean(row.get("away_team"))
    sportsbook = _clean(row.get("sportsbook")) or "kyre"
    line_status = (_clean(row.get("line_status")) or "unknown").casefold()
    if not game_id or not home_team or not away_team:
        raise ValueError("game_id, home_team, and away_team are required")
    if line_status not in _ALLOWED_LINE_STATUS:
        raise ValueError("line_status is invalid")
    total = row.get("total")
    if total is not None:
        try:
            total = float(total)
        except (TypeError, ValueError) as exc:
            raise ValueError("total must be numeric or null") from exc
        if total <= 0 or total > 200:
            raise ValueError("total is outside the supported range")
    return {
        "game_id": game_id,
        "home_team": home_team,
        "away_team": away_team,
        "start_time_utc": _aware_iso(row.get("start_time_utc"), "start_time_utc"),
        "total": total,
        "sportsbook": sportsbook,
        "updated_at_utc": _aware_iso(row.get("updated_at_utc"), "updated_at_utc"),
        "line_status": line_status,
    }


def validate_feed(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("feed must be a JSON object")
    if _clean(payload.get("schema_version")) != SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {SCHEMA_VERSION}")
    games = payload.get("games")
    if not isinstance(games, list):
        raise ValueError("games must be a list")
    return {
        "schema_version": SCHEMA_VERSION,
        "captured_at_utc": _aware_iso(payload.get("captured_at_utc"), "captured_at_utc"),
        "source": _clean(payload.get("source")) or "Kyre Sports API",
        "games": [_validate_game(row) for row in games],
        "market_semantics": {
            "projection_weight": 0.0,
            "market_context_only": True,
            "may_modify_projection": False,
        },
    }


def _require_ingest_token(authorization: str | None) -> None:
    expected = _clean(os.environ.get(INGEST_TOKEN_ENV))
    if not expected:
        raise HTTPException(status_code=503, detail="CFB market ingestion is not configured.")
    header = _clean(authorization)
    if not header or not header.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="A valid bearer token is required.")
    supplied = header[7:].strip()
    if not supplied or not hmac.compare_digest(supplied.encode(), expected.encode()):
        raise HTTPException(status_code=401, detail="A valid bearer token is required.")


def _load_feed() -> dict[str, Any]:
    path = _feed_path()
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="CFB market feed is not populated yet.") from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail="CFB market feed is temporarily unavailable.") from exc
    try:
        return validate_feed(json.loads(raw))
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=500, detail="CFB market feed failed validation.") from exc


@router.get("/status")
def status():
    try:
        path = _feed_path()
        exists = path.is_file()
    except ValueError:
        path = None
        exists = False
    return {
        "service": "Kyre Sports API",
        "sport": "college_football",
        "schema_version": SCHEMA_VERSION,
        "route_ready": True,
        "feed_configured": bool(path),
        "feed_present": exists,
        "ingest_configured": bool(_clean(os.environ.get(INGEST_TOKEN_ENV))),
        "market_semantics": {
            "projection_weight": 0.0,
            "market_context_only": True,
            "may_modify_projection": False,
        },
        "endpoints": {
            "current": "/api/v1/cfb/markets/current",
            "ingest": "/api/v1/cfb/markets/feed",
            "status": "/api/v1/cfb/markets/status",
        },
    }


@router.get("/current")
def current(game_id: str | None = Query(default=None)):
    feed = _load_feed()
    if game_id is None:
        return feed
    matches = [row for row in feed["games"] if row["game_id"] == game_id]
    if not matches:
        raise HTTPException(status_code=404, detail="CFB game was not found in the current market feed.")
    return {
        "schema_version": feed["schema_version"],
        "captured_at_utc": feed["captured_at_utc"],
        "source": feed["source"],
        "game": matches[0],
        "market_semantics": feed["market_semantics"],
    }


@router.post("/feed")
def ingest(
    payload: dict[str, Any] = Body(...),
    authorization: str | None = Header(default=None),
):
    _require_ingest_token(authorization)
    try:
        validated = validate_feed(payload)
        target = _feed_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(validated, indent=2, sort_keys=True) + "\n"
        if len(text.encode("utf-8")) > MAX_FEED_BYTES:
            raise ValueError("feed is too large")
        fd, tmp_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=str(target.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(text)
            os.replace(tmp_name, target)
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail="CFB market feed could not be stored.") from exc
    return {
        "stored": True,
        "game_count": len(validated["games"]),
        "schema_version": SCHEMA_VERSION,
        "authorization_token_returned": False,
        "market_semantics": validated["market_semantics"],
    }
