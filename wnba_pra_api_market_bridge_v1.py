"""WNBA PRA API market bridge freshness successor.

Only same-slate persisted market snapshots can be exposed as current WNBA market
truth. Same-slate offers remain usable for the slate instead of disappearing
merely because collection occurred more than ten minutes ago; wrong-date
snapshots still fail closed.
"""
from __future__ import annotations
from datetime import datetime, timezone
import time
from typing import Any, Mapping
import pandas as pd
import wnba_pra_api_market_bridge_legacy_v1 as previous
from wnba_pra_api_market_bridge_legacy_v1 import *  # noqa: F401,F403

MODEL_VERSION = "WNBA PRA API MARKET BRIDGE V2.1 • SAME-SLATE AVAILABILITY"
API_SOURCE = previous.API_SOURCE
SNAPSHOT_PATH = "/api/v1/wnba/markets/player-props/collection-store/snapshots"
CACHE_TTL_SECONDS = previous.CACHE_TTL_SECONDS
KyreWNBAAPIClient = previous.KyreWNBAAPIClient
KyreWNBAAPIError = previous.KyreWNBAAPIError
SUPPORTED_SEASON = previous.SUPPORTED_SEASON
_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}


def _aware(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text: return None
    try: stamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError: return None
    if stamp.tzinfo is None: stamp = stamp.replace(tzinfo=timezone.utc)
    return stamp.astimezone(timezone.utc)


def _current_time(now=None):
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None: current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc)


def _offers(raw):
    normalized = raw.get("normalized_input_feed")
    values = normalized.get("offers") if isinstance(normalized, Mapping) else None
    return [dict(row) for row in values if isinstance(row, Mapping)] if isinstance(values, list) else []


def _snapshot_stamp(raw):
    for key in ("collected_at_utc", "stored_at_utc"):
        stamp = _aware(raw.get(key))
        if stamp is not None: return stamp
    stamps = [_aware(row.get("market_captured_at_utc")) for row in _offers(raw)]
    stamps = [stamp for stamp in stamps if stamp is not None]
    return max(stamps) if stamps else None


def _snapshot_offers(payload, day_str, *, now=None):
    snapshots = payload.get("snapshots")
    if not isinstance(snapshots, list): return None, []
    candidates = []
    for raw in snapshots:
        if not isinstance(raw, Mapping) or str(raw.get("date") or "").strip() != day_str: continue
        offers = _offers(raw)
        stamp = _snapshot_stamp(raw)
        if not offers or stamp is None: continue
        candidates.append((stamp, dict(raw), offers))
    if not candidates: return None, []
    candidates.sort(key=lambda item: item[0], reverse=True)
    _, selected, offers = candidates[0]
    return selected, offers


def _metadata(raw, *, now, current):
    obj = raw if isinstance(raw, Mapping) else {}
    stamp = _snapshot_stamp(obj)
    age = max(0.0, (_current_time(now) - stamp).total_seconds()) if stamp else None
    return {"snapshot_date": str(obj.get("date") or "").strip() or None, "collected_at_utc": str(obj.get("collected_at_utc") or obj.get("stored_at_utc") or (stamp.isoformat() if stamp else "")).strip() or None, "snapshot_age_seconds": age, "freshness_state": "CURRENT_SLATE" if current else ("STALE" if obj else "UNAVAILABLE")}


def _latest_snapshot(payload):
    snapshots = payload.get("snapshots")
    rows = [dict(row) for row in snapshots if isinstance(row, Mapping)] if isinstance(snapshots, list) else []
    if not rows: return None
    return max(rows, key=lambda row: _snapshot_stamp(row) or datetime.min.replace(tzinfo=timezone.utc))


def _build_snapshot(day, schedule_payload, snapshot_payload, *, now=None):
    day_str = pd.to_datetime(day).strftime("%Y-%m-%d")
    lookup, _ = previous._game_lookup(schedule_payload)
    if not lookup:
        out = previous._build_snapshot(day_str, schedule_payload, snapshot_payload, now=now)
        out.update(_metadata(None, now=now, current=False)); out["fanduel_offer_count"] = 0
        return out
    selected, offers = _snapshot_offers(snapshot_payload, day_str, now=now)
    if selected is None:
        stale = _latest_snapshot(snapshot_payload)
        state = "STALE_STORED_MARKETS" if stale is not None else "NO_STORED_MARKETS"
        out = previous._empty(day_str, state); out["schedule_games"] = len(lookup)
        out.update(_metadata(stale, now=now, current=False)); out["fanduel_offer_count"] = 0
        return out
    sanitized = {"snapshots": [{**selected, "normalized_input_feed": {"offers": offers}}]}
    out = previous._build_snapshot(day_str, schedule_payload, sanitized, now=now)
    out.update(_metadata(selected, now=now, current=True))
    out["fanduel_offer_count"] = sum(str(row.get("sportsbook") or "").strip().casefold() == "fanduel" for row in offers)
    return out


def _read_api_snapshot(day_str):
    api = KyreWNBAAPIClient(); schedule = api.games_for_date(day_str, SUPPORTED_SEASON)
    snapshots = api.get_json(SNAPSHOT_PATH, params={"date": day_str, "season": SUPPORTED_SEASON, "limit": 20, "include_payload": "true"})
    return _build_snapshot(day_str, schedule, snapshots)


def market_snapshot(day):
    day_str = pd.to_datetime(day).strftime("%Y-%m-%d"); cached = _CACHE.get(day_str); now_mono = time.monotonic()
    if cached and now_mono - cached[0] <= CACHE_TTL_SECONDS: return cached[1]
    try: result = _read_api_snapshot(day_str)
    except Exception as exc:
        result = previous._empty(day_str, "API_ERROR", error=f"{type(exc).__name__}: {exc}"); result.update(_metadata(None, now=None, current=False)); result["fanduel_offer_count"] = 0
    _CACHE[day_str] = (now_mono, result); return result


def clear_cache(): _CACHE.clear()
previous.market_snapshot = market_snapshot
previous.clear_cache = clear_cache
render_market_panel = previous.render_market_panel

def install():
    previous.market_snapshot = market_snapshot; previous.clear_cache = clear_cache; previous.render_market_panel = render_market_panel
    result = dict(previous.install()); result["model_version"] = MODEL_VERSION; result["freshness_policy"] = "same-slate"
    return result

def __getattr__(name): return getattr(previous, name)
__all__ = ["MODEL_VERSION", "API_SOURCE", "SNAPSHOT_PATH", "CACHE_TTL_SECONDS", "market_snapshot", "clear_cache", "render_market_panel", "install"]
