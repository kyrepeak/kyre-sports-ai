"""College Football market-data transport for the Kyre Sports API.

CFB odds integration transport with a self-healing live FanDuel total feed.
Sportsbook/market information is context only and carries 0% projection weight.

The local JSON file is a cache, not the source of truth. On Render redeploys the
cache can disappear; the first read repopulates it from one anonymous FanDuel
NCAAF content-page GET. Stale caches refresh automatically and fail closed if
fresh market data cannot be obtained.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hmac
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query, Request

router = APIRouter(prefix="/api/v1/cfb/markets", tags=["cfb"])

SCHEMA_VERSION = "cfb_market_feed_v1"
FEED_PATH_ENV = "CFB_KYRE_MARKET_FEED_PATH"
INGEST_TOKEN_ENV = "CFB_KYRE_MARKET_INGEST_TOKEN"
AUTO_REFRESH_ENV = "CFB_FANDUEL_AUTO_REFRESH_ENABLED"
MAX_AGE_ENV = "CFB_MARKET_FEED_MAX_AGE_SECONDS"
DEFAULT_FEED_PATH = "/var/lib/kyre-sports-api/cfb_market_feed.json"
DEFAULT_MAX_AGE_SECONDS = 120.0
MAX_MAX_AGE_SECONDS = 3600.0
MAX_FUTURE_CAPTURE_SKEW_SECONDS = 60.0
MAX_FEED_BYTES = 5_000_000
_ALLOWED_LINE_STATUS = {"open", "active", "suspended", "closed", "final", "unknown"}


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _truthy(value: Any, default: bool = False) -> bool:
    text = _clean(value)
    if text is None:
        return default
    return text.casefold() in {"1", "true", "yes", "on", "enabled"}


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


def _auto_refresh_enabled() -> bool:
    return _truthy(os.environ.get(AUTO_REFRESH_ENV), default=True)


def _max_age_seconds() -> float:
    raw = _clean(os.environ.get(MAX_AGE_ENV))
    if raw is None:
        return DEFAULT_MAX_AGE_SECONDS
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{MAX_AGE_ENV} must be numeric") from exc
    if not math.isfinite(value) or value < 15.0 or value > MAX_MAX_AGE_SECONDS:
        raise ValueError(
            f"{MAX_AGE_ENV} must be between 15 and {MAX_MAX_AGE_SECONDS:g} seconds"
        )
    return value


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
        if not math.isfinite(total) or total <= 0 or total > 200:
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
    validated_games = [_validate_game(row) for row in games]
    ids = [row["game_id"] for row in validated_games]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate game_id values are not allowed")
    return {
        "schema_version": SCHEMA_VERSION,
        "captured_at_utc": _aware_iso(payload.get("captured_at_utc"), "captured_at_utc"),
        "source": _clean(payload.get("source")) or "Kyre Sports API",
        "games": validated_games,
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


def _serialize_feed(validated: dict[str, Any]) -> bytes:
    try:
        text = json.dumps(
            validated,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        ) + "\n"
    except (TypeError, ValueError) as exc:
        raise ValueError("feed could not be serialized as strict JSON") from exc
    raw = text.encode("utf-8")
    if len(raw) > MAX_FEED_BYTES:
        raise ValueError("feed is too large")
    return raw


def _store_validated_feed(validated: dict[str, Any]) -> Path:
    # Refuse a materially future-dated snapshot before it can suppress automatic
    # refreshes. A small bounded skew is tolerated for host clock differences.
    _feed_age_seconds(validated)
    target = _feed_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    raw = _serialize_feed(validated)
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{target.name}.",
        suffix=".tmp",
        dir=str(target.parent),
    )
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(raw)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, target)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
    return target


def _read_cached_feed() -> dict[str, Any]:
    path = _feed_path()
    try:
        raw = path.read_bytes()
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="CFB market feed is not populated yet.") from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail="CFB market feed is temporarily unavailable.") from exc
    if len(raw) > MAX_FEED_BYTES:
        raise HTTPException(status_code=500, detail="CFB market feed exceeded its size contract.")
    try:
        payload = json.loads(raw.decode("utf-8"))
        return validate_feed(payload)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=500, detail="CFB market feed failed validation.") from exc


def _feed_age_seconds(feed: dict[str, Any], *, now: datetime | None = None) -> float:
    reference = now or datetime.now(timezone.utc)
    if reference.tzinfo is None or reference.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    captured = datetime.fromisoformat(
        str(feed["captured_at_utc"]).replace("Z", "+00:00")
    )
    age = (
        reference.astimezone(timezone.utc) - captured.astimezone(timezone.utc)
    ).total_seconds()
    if age < -MAX_FUTURE_CAPTURE_SKEW_SECONDS:
        raise ValueError(
            "captured_at_utc is implausibly in the future"
        )
    return max(0.0, age)


def _refresh_from_fanduel() -> dict[str, Any]:
    # Lazy import prevents a provider transport import from affecting app startup.
    from sports_api.collectors.cfb_fanduel_direct import (
        CFBFanDuelCollectorError,
        collect_fanduel_cfb_total_feed,
    )

    try:
        snapshot = collect_fanduel_cfb_total_feed()
        validated = validate_feed(snapshot)
        _store_validated_feed(validated)
        return validated
    except (CFBFanDuelCollectorError, ValueError, OSError) as exc:
        raise HTTPException(
            status_code=503,
            detail="Fresh CFB FanDuel market data is temporarily unavailable.",
        ) from exc


def _load_feed(*, force_refresh: bool = False) -> dict[str, Any]:
    if force_refresh and _auto_refresh_enabled():
        return _refresh_from_fanduel()

    try:
        cached = _read_cached_feed()
    except HTTPException as exc:
        # The cache is disposable. Missing, truncated, oversized, incompatible,
        # or otherwise invalid cache state should self-heal from the live source.
        if exc.status_code in {404, 500} and _auto_refresh_enabled():
            return _refresh_from_fanduel()
        raise

    if not _auto_refresh_enabled():
        return cached

    try:
        max_age = _max_age_seconds()
    except ValueError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    try:
        age = _feed_age_seconds(cached)
    except ValueError:
        # Future-dated or otherwise invalid capture timing is not fresh.
        return _refresh_from_fanduel()
    if age <= max_age:
        return cached
    return _refresh_from_fanduel()


@router.get("/status")
def status():
    try:
        path = _feed_path()
        exists = path.is_file()
    except ValueError:
        path = None
        exists = False

    cache_age = None
    cache_fresh = False
    cached_game_count = None
    cached_source = None
    if exists:
        try:
            cached = _read_cached_feed()
            cache_age = round(_feed_age_seconds(cached), 3)
            cache_fresh = cache_age <= _max_age_seconds()
            cached_game_count = len(cached["games"])
            cached_source = cached["source"]
        except (HTTPException, ValueError):
            cache_fresh = False

    try:
        max_age = _max_age_seconds()
    except ValueError:
        max_age = None

    return {
        "service": "Kyre Sports API",
        "sport": "college_football",
        "schema_version": SCHEMA_VERSION,
        "route_ready": True,
        "feed_configured": bool(path),
        "feed_present": exists,
        "feed_fresh": cache_fresh,
        "feed_age_seconds": cache_age,
        "cached_game_count": cached_game_count,
        "cached_source": cached_source,
        "ingest_configured": bool(_clean(os.environ.get(INGEST_TOKEN_ENV))),
        "auto_refresh_enabled": _auto_refresh_enabled(),
        "cache_max_age_seconds": max_age,
        "live_provider": {
            "provider": "FanDuel",
            "surface": "anonymous public NCAAF content-managed-page",
            "custom_page_id": "ncaaf",
            "secret_required": False,
            "authentication_used": False,
            "cookies_used": False,
            "http_method": "GET",
            "requests_per_refresh": 1,
            "cache_self_heals_after_redeploy": True,
        },
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
def current(
    game_id: str | None = Query(default=None),
):
    # Public callers use the bounded cache policy only. There is intentionally no
    # public cache-bypass switch that can amplify outbound provider requests.
    feed = _load_feed()
    if game_id is None:
        return feed
    matches = [row for row in feed["games"] if row["game_id"] == game_id]
    if not matches:
        raise HTTPException(
            status_code=404,
            detail="CFB game was not found in the current market feed.",
        )
    return {
        "schema_version": feed["schema_version"],
        "captured_at_utc": feed["captured_at_utc"],
        "source": feed["source"],
        "game": matches[0],
        "market_semantics": feed["market_semantics"],
    }


@router.post("/feed")
async def ingest(
    request: Request,
    authorization: str | None = Header(default=None),
):
    # Authenticate before any body read/JSON parse.
    _require_ingest_token(authorization)

    content_length = _clean(request.headers.get("content-length"))
    if content_length is not None:
        try:
            declared = int(content_length)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Content-Length is invalid.") from exc
        if declared < 0 or declared > MAX_FEED_BYTES:
            raise HTTPException(status_code=413, detail="CFB market feed request is too large.")

    chunks: list[bytes] = []
    total_bytes = 0
    async for chunk in request.stream():
        total_bytes += len(chunk)
        if total_bytes > MAX_FEED_BYTES:
            raise HTTPException(status_code=413, detail="CFB market feed request is too large.")
        chunks.append(chunk)

    try:
        payload = json.loads(b"".join(chunks).decode("utf-8"))
        validated = validate_feed(payload)
        _store_validated_feed(validated)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail="CFB market feed must be valid UTF-8 JSON.") from exc
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


__all__ = [
    "AUTO_REFRESH_ENV",
    "DEFAULT_FEED_PATH",
    "DEFAULT_MAX_AGE_SECONDS",
    "FEED_PATH_ENV",
    "INGEST_TOKEN_ENV",
    "MAX_FEED_BYTES",
    "MAX_FUTURE_CAPTURE_SKEW_SECONDS",
    "SCHEMA_VERSION",
    "_feed_path",
    "_load_feed",
    "_store_validated_feed",
    "router",
    "validate_feed",
]
