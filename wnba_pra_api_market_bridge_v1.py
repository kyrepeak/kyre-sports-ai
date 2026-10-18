"""WNBA PRA API market bridge freshness + bounded refresh successor.

The Streamlit product remains API-owned: it reads persisted WNBA prop snapshots
from Kyre Sports API and never contacts a sportsbook directly.  Only an exact
same-slate snapshot inside the strict freshness window may become current market
truth.  When that current FanDuel snapshot is missing, this bridge may request
one existing Kyre Sports API FanDuel collection cycle and then re-read durable
snapshot state exactly once.
"""
from __future__ import annotations

from datetime import datetime, timezone
import time
from typing import Any, Callable, Mapping

import pandas as pd
import requests

import wnba_pra_api_market_bridge_legacy_v1 as previous
from wnba_pra_api_market_bridge_legacy_v1 import *  # noqa: F401,F403

MODEL_VERSION = "WNBA PRA API MARKET BRIDGE V2.2 • FANDUEL BOUNDED REFRESH"
API_SOURCE = previous.API_SOURCE
SNAPSHOT_PATH = "/api/v1/wnba/markets/player-props/collection-store/snapshots"
REFRESH_PATH = "/api/v1/wnba/markets/player-props/collect/failover/line-board"
CACHE_TTL_SECONDS = previous.CACHE_TTL_SECONDS
SNAPSHOT_MAX_AGE_SECONDS = 600.0
REFRESH_TIMEOUT_SECONDS = 45.0
KyreWNBAAPIClient = previous.KyreWNBAAPIClient
KyreWNBAAPIError = previous.KyreWNBAAPIError
SUPPORTED_SEASON = previous.SUPPORTED_SEASON
_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


def _aware(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        stamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(timezone.utc)


def _current_time(now: datetime | None) -> datetime:
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)


def _offers(raw: Mapping[str, Any]) -> list[dict[str, Any]]:
    normalized = raw.get("normalized_input_feed")
    values = normalized.get("offers") if isinstance(normalized, Mapping) else None
    return [dict(row) for row in values if isinstance(row, Mapping)] if isinstance(values, list) else []


def _snapshot_stamp(raw: Mapping[str, Any]) -> tuple[datetime | None, bool]:
    for key in ("collected_at_utc", "stored_at_utc"):
        stamp = _aware(raw.get(key))
        if stamp is not None:
            return stamp, True
    stamps = [_aware(row.get("market_captured_at_utc")) for row in _offers(raw)]
    stamps = [stamp for stamp in stamps if stamp is not None]
    return (max(stamps), False) if stamps else (None, False)


def _snapshot_offers(
    payload: Mapping[str, Any],
    day_str: str,
    *,
    now: datetime | None = None,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    snapshots = payload.get("snapshots")
    if not isinstance(snapshots, list):
        return None, []
    candidates: list[tuple[datetime, dict[str, Any], list[dict[str, Any]]]] = []
    for raw in snapshots:
        if not isinstance(raw, Mapping) or str(raw.get("date") or "").strip() != day_str:
            continue
        offers = _offers(raw)
        if not offers:
            continue
        stamp, durable_stamp = _snapshot_stamp(raw)
        if stamp is None:
            continue
        enforce_age = durable_stamp or now is not None
        age = max(0.0, (_current_time(now) - stamp).total_seconds())
        if enforce_age and age > SNAPSHOT_MAX_AGE_SECONDS:
            continue
        candidates.append((stamp, dict(raw), offers))
    if not candidates:
        return None, []
    candidates.sort(key=lambda item: item[0], reverse=True)
    _, selected, offers = candidates[0]
    return selected, offers


def _metadata(raw: Mapping[str, Any] | None, *, now: datetime | None, current: bool) -> dict[str, Any]:
    obj = raw if isinstance(raw, Mapping) else {}
    stamp, _ = _snapshot_stamp(obj)
    age = max(0.0, (_current_time(now) - stamp).total_seconds()) if stamp else None
    return {
        "snapshot_date": str(obj.get("date") or "").strip() or None,
        "collected_at_utc": str(
            obj.get("collected_at_utc")
            or obj.get("stored_at_utc")
            or (stamp.isoformat() if stamp else "")
        ).strip() or None,
        "snapshot_age_seconds": age,
        "freshness_state": "CURRENT" if current else ("STALE" if obj else "UNAVAILABLE"),
    }


def _latest_snapshot(payload: Mapping[str, Any]) -> dict[str, Any] | None:
    snapshots = payload.get("snapshots")
    rows = [dict(row) for row in snapshots if isinstance(row, Mapping)] if isinstance(snapshots, list) else []
    if not rows:
        return None

    def key(row):
        stamp, _ = _snapshot_stamp(row)
        return stamp or datetime.min.replace(tzinfo=timezone.utc)

    return max(rows, key=key)


def _build_snapshot(
    day: Any,
    schedule_payload: Mapping[str, Any],
    snapshot_payload: Mapping[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    day_str = pd.to_datetime(day).strftime("%Y-%m-%d")
    lookup, _ = previous._game_lookup(schedule_payload)
    if not lookup:
        out = previous._build_snapshot(day_str, schedule_payload, snapshot_payload, now=now)
        out.update(_metadata(None, now=now, current=False))
        out["fanduel_offer_count"] = 0
        return out

    selected, offers = _snapshot_offers(snapshot_payload, day_str, now=now)
    if selected is None:
        stale = _latest_snapshot(snapshot_payload)
        state = "STALE_STORED_MARKETS" if stale is not None else "NO_STORED_MARKETS"
        out = previous._empty(day_str, state)
        out["schedule_games"] = len(lookup)
        out.update(_metadata(stale, now=now, current=False))
        out["fanduel_offer_count"] = 0
        return out

    sanitized = {"snapshots": [{**selected, "normalized_input_feed": {"offers": offers}}]}
    out = previous._build_snapshot(day_str, schedule_payload, sanitized, now=now)
    out.update(_metadata(selected, now=now, current=True))
    out["fanduel_offer_count"] = sum(
        str(row.get("sportsbook") or "").strip().casefold() == "fanduel" for row in offers
    )
    return out


def _snapshot_params(day_str: str) -> dict[str, Any]:
    return {
        "date": day_str,
        "season": SUPPORTED_SEASON,
        "limit": 20,
        "include_payload": "true",
    }


def _refresh_fanduel_snapshot(api: Any, day_str: str) -> dict[str, Any]:
    """Ask Kyre Sports API for one FanDuel collection/persistence attempt."""
    url = str(api.base_url).rstrip("/") + REFRESH_PATH
    params = {
        "provider_ids": "fanduel",
        "date": day_str,
        "season": SUPPORTED_SEASON,
        "minimum_normalized_lines": 0,
        "require_persistent_store": "true",
    }
    try:
        response = requests.post(
            url,
            params=params,
            headers={
                "accept": "application/json",
                "user-agent": "kyre-sports-ai-streamlit-wnba-pra-refresh/1",
            },
            timeout=REFRESH_TIMEOUT_SECONDS,
            allow_redirects=True,
        )
        status = int(response.status_code)
        error = None if 200 <= status < 300 else f"KYRE_API_REFRESH_HTTP_{status}"
        return {"attempted": True, "status_code": status, "error": error}
    except requests.RequestException as exc:
        return {
            "attempted": True,
            "status_code": None,
            "error": f"KYRE_API_REFRESH_{type(exc).__name__}",
        }


def _needs_fanduel_refresh(result: Mapping[str, Any]) -> bool:
    if int(result.get("schedule_games") or 0) <= 0:
        return False
    state = str(result.get("state") or "")
    if state in {"NO_STORED_MARKETS", "STALE_STORED_MARKETS", "MATCH_FAILURE"}:
        return True
    return int(result.get("fanduel_offer_count") or 0) <= 0


def _apply_refresh_metadata(result: dict[str, Any], meta: Mapping[str, Any] | None) -> dict[str, Any]:
    values = dict(meta or {})
    result["refresh_attempted"] = bool(values.get("attempted"))
    result["refresh_status_code"] = values.get("status_code")
    result["refresh_error"] = values.get("error")
    return result


def _read_api_snapshot(
    day_str: str,
    *,
    api_client: Any | None = None,
    refresher: Callable[[Any, str], Mapping[str, Any] | None] | None = None,
) -> dict[str, Any]:
    api = api_client or KyreWNBAAPIClient()
    refresh = refresher or _refresh_fanduel_snapshot
    schedule = api.games_for_date(day_str, SUPPORTED_SEASON)
    snapshots = api.get_json(SNAPSHOT_PATH, params=_snapshot_params(day_str))
    result = _build_snapshot(day_str, schedule, snapshots)
    if not _needs_fanduel_refresh(result):
        return _apply_refresh_metadata(result, {"attempted": False})

    try:
        refresh_meta = refresh(api, day_str)
    except Exception as exc:
        refresh_meta = {
            "attempted": True,
            "status_code": None,
            "error": f"KYRE_API_REFRESH_{type(exc).__name__}",
        }

    # Re-read durable API state exactly once even when downstream normalization
    # returned an error: persistence can succeed before later line-board work.
    try:
        reread = api.get_json(SNAPSHOT_PATH, params=_snapshot_params(day_str))
        result = _build_snapshot(day_str, schedule, reread)
    except Exception as exc:
        values = dict(refresh_meta or {})
        values["error"] = values.get("error") or f"KYRE_API_REREAD_{type(exc).__name__}"
        refresh_meta = values
    return _apply_refresh_metadata(result, refresh_meta)


def market_snapshot(day: Any) -> dict[str, Any]:
    day_str = pd.to_datetime(day).strftime("%Y-%m-%d")
    cached = _CACHE.get(day_str)
    now_mono = time.monotonic()
    if cached and now_mono - cached[0] <= CACHE_TTL_SECONDS:
        return cached[1]
    try:
        result = _read_api_snapshot(day_str)
    except Exception as exc:
        result = previous._empty(day_str, "API_ERROR", error=f"{type(exc).__name__}: {exc}")
        result.update(_metadata(None, now=None, current=False))
        result["fanduel_offer_count"] = 0
        _apply_refresh_metadata(result, {"attempted": False})
    _CACHE[day_str] = (now_mono, result)
    return result


def clear_cache() -> None:
    _CACHE.clear()


previous.market_snapshot = market_snapshot
previous.clear_cache = clear_cache
render_market_panel = previous.render_market_panel


def install() -> dict[str, Any]:
    previous.market_snapshot = market_snapshot
    previous.clear_cache = clear_cache
    previous.render_market_panel = render_market_panel
    result = dict(previous.install())
    result["model_version"] = MODEL_VERSION
    result["snapshot_max_age_seconds"] = SNAPSHOT_MAX_AGE_SECONDS
    result["refresh_path"] = REFRESH_PATH
    return result


def __getattr__(name):
    return getattr(previous, name)


__all__ = [
    "MODEL_VERSION", "API_SOURCE", "SNAPSHOT_PATH", "REFRESH_PATH",
    "CACHE_TTL_SECONDS", "SNAPSHOT_MAX_AGE_SECONDS", "market_snapshot",
    "clear_cache", "render_market_panel", "install",
]
