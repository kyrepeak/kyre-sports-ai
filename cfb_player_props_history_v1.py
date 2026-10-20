"""CFB Player Props V1 — verified ESPN athlete gamelog history."""
from __future__ import annotations

from datetime import datetime, timezone
import math
import re
from typing import Any, Mapping

import requests
import streamlit as st

from cfb_player_props_identity_v1 import CanonicalPlayerIdentity
from cfb_player_props_market_v1 import SUPPORTED_MARKETS

MODEL_VERSION = "CFB PLAYER PROPS HISTORY V1 • ESPN VERIFIED GAMELOG"
GAMELOG_BASE = "https://site.web.api.espn.com/apis/common/v3/sports/football/college-football/athletes"
SOURCE = "ESPN CFB athlete gamelog"
HEADERS = {"User-Agent": "KyreSportsAI/CFB-Player-Props-V1", "Accept": "application/json"}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", _text(value).lower())


def _finite(value: Any) -> float | None:
    try:
        out = float(str(value).replace(",", "").strip())
        return out if math.isfinite(out) else None
    except (TypeError, ValueError):
        return None


def _event_rows(events: Any) -> list[dict[str, Any]]:
    if isinstance(events, Mapping):
        items = events.get("items")
        if isinstance(items, list):
            return [dict(x) for x in items if isinstance(x, Mapping)]
        out = []
        for key, value in events.items():
            if isinstance(value, Mapping):
                row = dict(value)
                row.setdefault("eventId", str(key))
                out.append(row)
        return out
    return [dict(x) for x in events if isinstance(x, Mapping)] if isinstance(events, list) else []


def _categories(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    cats = payload.get("categories")
    if isinstance(cats, list):
        return [x for x in cats if isinstance(x, Mapping)]
    stats = payload.get("statistics")
    if isinstance(stats, Mapping) and isinstance(stats.get("categories"), list):
        return [x for x in stats["categories"] if isinstance(x, Mapping)]
    return []


def _event_meta(payload: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    raw = payload.get("events") or payload.get("eventMetadata") or {}
    rows = _event_rows(raw)
    return {_text(r.get("eventId") or r.get("id")): r for r in rows if _text(r.get("eventId") or r.get("id"))}


def _is_completed(item: Mapping[str, Any], meta: Mapping[str, Any]) -> bool:
    direct = item.get("completed")
    if direct is not None:
        return bool(direct)
    status = item.get("status") or meta.get("status") or {}
    if isinstance(status, Mapping):
        status = status.get("type") or status
        if isinstance(status, Mapping):
            if status.get("completed") is not None:
                return bool(status.get("completed"))
            status = status.get("state") or status.get("name") or status.get("description")
    text = _text(status).lower()
    return text in {"post", "final", "completed", "complete", "closed"} or "final" in text


def _game_date(item: Mapping[str, Any], meta: Mapping[str, Any]) -> str:
    value = item.get("date") or meta.get("date") or meta.get("startDate") or ""
    text = _text(value)
    if not text:
        return ""
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return text[:10]


def _category_kind(category: Mapping[str, Any]) -> str:
    return _norm(category.get("name") or category.get("displayName") or category.get("abbreviation"))


def _stat_lookup(category: Mapping[str, Any], item: Mapping[str, Any]) -> dict[str, float]:
    raw = item.get("stats") or item.get("statistics") or []
    if isinstance(raw, Mapping):
        out = {}
        for key, value in raw.items():
            number = _finite(value)
            if number is not None:
                out[_norm(key)] = number
        return out
    labels = [_norm(x) for x in (category.get("labels") or category.get("names") or [])]
    values = list(raw) if isinstance(raw, list) else []
    out = {}
    for idx in range(min(len(labels), len(values))):
        number = _finite(values[idx])
        if number is not None and labels[idx]:
            out[labels[idx]] = number
    return out


def _pick(stats: Mapping[str, float], *aliases: str) -> float | None:
    for alias in aliases:
        key = _norm(alias)
        if key in stats:
            return float(stats[key])
    return None


def normalize_gamelog_payload(payload: Mapping[str, Any], market_key: str) -> list[dict[str, Any]]:
    if market_key not in SUPPORTED_MARKETS:
        return []
    meta = _event_meta(payload)
    values_by_event: dict[str, dict[str, Any]] = {}
    for category in _categories(payload):
        kind = _category_kind(category)
        for item in _event_rows(category.get("events")):
            event_id = _text(item.get("eventId") or item.get("id"))
            if not event_id:
                continue
            event_meta = meta.get(event_id, {})
            if not _is_completed(item, event_meta):
                continue
            stats = _stat_lookup(category, item)
            value: float | None = None
            if market_key == "passing_yards" and "pass" in kind:
                value = _pick(stats, "YDS", "passingYards", "passYards")
            elif market_key == "passing_touchdowns" and "pass" in kind:
                value = _pick(stats, "TD", "passingTouchdowns", "passTouchdowns")
            elif market_key == "rushing_yards" and ("rush" in kind or "rushing" in kind):
                value = _pick(stats, "YDS", "rushingYards", "rushYards")
            elif market_key == "receiving_yards" and ("receiv" in kind):
                value = _pick(stats, "YDS", "receivingYards", "recYards")
            elif market_key == "receiving_receptions" and ("receiv" in kind):
                value = _pick(stats, "REC", "receptions", "receivingReceptions")
            elif market_key == "touchdowns" and ("rush" in kind or "receiv" in kind):
                value = _pick(stats, "TD", "touchdowns", "rushingTouchdowns", "receivingTouchdowns")
            if value is None or not math.isfinite(value) or value < 0:
                continue
            row = values_by_event.setdefault(event_id, {
                "event_id": event_id,
                "completed": True,
                "source": SOURCE,
                "market_key": market_key,
                "value": 0.0 if market_key == "touchdowns" else value,
                "game_date": _game_date(item, event_meta),
            })
            if market_key == "touchdowns":
                row["value"] = float(row["value"]) + float(value)
            else:
                row["value"] = float(value)
    rows = list(values_by_event.values())
    rows.sort(key=lambda row: (row.get("game_date") or "", row["event_id"]), reverse=True)
    return rows


@st.cache_data(ttl=300, show_spinner=False)
def _fetch_gamelog(athlete_id: str, season: int) -> dict[str, Any]:
    athlete_id = _text(athlete_id)
    if not athlete_id:
        return {}
    try:
        response = requests.get(
            f"{GAMELOG_BASE}/{athlete_id}/gamelog",
            params={"season": int(season)},
            headers=HEADERS,
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def load_verified_player_history(
    player: CanonicalPlayerIdentity, market_key: str, *, season: int
) -> list[dict[str, Any]]:
    if not player.official_player_id or market_key not in SUPPORTED_MARKETS:
        return []
    return normalize_gamelog_payload(_fetch_gamelog(player.official_player_id, int(season)), market_key)


__all__ = ["GAMELOG_BASE", "MODEL_VERSION", "SOURCE", "load_verified_player_history", "normalize_gamelog_payload"]
