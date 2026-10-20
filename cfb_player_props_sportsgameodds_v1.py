"""Read-only SportsGameOdds NCAAF player-prop transport."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import os
from typing import Any, Mapping
from zoneinfo import ZoneInfo

import requests
import streamlit as st

SGO_BASE = "https://api.sportsgameodds.com/v2"
SGO_LEAGUE_ID = "NCAAF"
DEFAULT_BOOKMAKERS = "draftkings,fanduel,betmgm,caesars"
STAT_IDS = (
    "passing_yards", "rushing_yards", "receiving_yards",
    "receiving_receptions", "passing_touchdowns", "touchdowns",
)
BOOK_LABELS = {"draftkings":"DraftKings","fanduel":"FanDuel","betmgm":"BetMGM","caesars":"Caesars"}
ET = ZoneInfo("America/New_York")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _secret(name: str) -> str:
    try:
        value = st.secrets.get(name, "")
    except Exception:
        value = ""
    return _text(value or os.getenv(name, ""))


def build_odd_id_filter() -> str:
    return ",".join(
        f"{stat}-PLAYER_ID-game-ou-{side}"
        for stat in STAT_IDS for side in ("over", "under")
    )


def _book_key(value: Any) -> str:
    return "".join(ch for ch in _text(value).lower() if ch.isalnum())


def _num(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _american(value: Any) -> int | None:
    try:
        return int(round(float(value)))
    except (TypeError, ValueError):
        return None


def _event_name(event: Mapping[str, Any], side: str) -> str:
    team = ((event.get("teams") or {}).get(side) or {}) if isinstance(event.get("teams"), Mapping) else {}
    names = team.get("names") or {}
    if isinstance(names, Mapping):
        for key in ("long", "display", "medium", "short"):
            if names.get(key):
                return _text(names[key])
    return _text(team.get("name") or team.get("teamName"))


def _player_name(event: Mapping[str, Any], player_id: str, market_name: Any) -> str:
    players = event.get("players") or {}
    values = players.values() if isinstance(players, Mapping) else players if isinstance(players, list) else []
    for raw in values:
        if not isinstance(raw, Mapping):
            continue
        if _text(raw.get("playerID") or raw.get("id")) != player_id:
            continue
        names = raw.get("names") or {}
        if isinstance(names, Mapping):
            for key in ("long", "display", "medium", "short"):
                if names.get(key):
                    return _text(names[key])
        for key in ("fullName", "displayName", "name"):
            if raw.get(key):
                return _text(raw[key])
    name = _text(market_name)
    for stat in STAT_IDS:
        label = stat.replace("_", " ")
        if label in name.lower():
            return name.lower().split(label, 1)[0].strip().title()
    return ""


def parse_event_props(event: Mapping[str, Any]) -> list[dict[str, Any]]:
    odds = event.get("odds") or {}
    if not isinstance(odds, Mapping):
        return []
    rows: list[dict[str, Any]] = []
    for odd_id, odd in odds.items():
        if not isinstance(odd, Mapping):
            continue
        stat = _text(odd.get("statID"))
        if stat not in STAT_IDS or _text(odd.get("periodID")) != "game" or _text(odd.get("betTypeID")).lower() != "ou":
            continue
        side = _text(odd.get("sideID")).lower()
        player_id = _text(odd.get("playerID") or odd.get("statEntityID"))
        if side not in {"over", "under"} or not player_id or player_id.lower() in {"all", "home", "away"}:
            continue
        books = odd.get("byBookmaker") or {}
        if not isinstance(books, Mapping):
            continue
        for book_id, quote in books.items():
            if not isinstance(quote, Mapping) or quote.get("available") is False:
                continue
            line = _num(quote.get("overUnder"))
            if line is None:
                continue
            bk = _book_key(book_id)
            rows.append({
                "provider": "SportsGameOdds",
                "provider_event_id": _text(event.get("eventID") or event.get("id")),
                "provider_player_id": player_id,
                "provider_market_id": _text(odd.get("oddID") or odd_id),
                "player_name": _player_name(event, player_id, odd.get("marketName")),
                "stat_id": stat,
                "sportsbook": BOOK_LABELS.get(bk, _text(book_id)),
                "side": side,
                "line": line,
                "price": _american(quote.get("odds")),
                "observed_at_utc": _text(quote.get("lastUpdatedAt") or event.get("updatedAt")),
                "away_team": _event_name(event, "away"),
                "home_team": _event_name(event, "home"),
                "event_start": _text(((event.get("status") or {}).get("startsAt") if isinstance(event.get("status"), Mapping) else "") or event.get("startTime") or event.get("date")),
            })
    return rows


def fetch_sgo_cfb_player_props(slate_date: date) -> list[dict[str, Any]]:
    api_key = _secret("SPORTSGAMEODDS_API_KEY") or _secret("SPORTSGAMEODDS_KEY")
    if not api_key:
        return []
    day = slate_date if isinstance(slate_date, date) else date.fromisoformat(_text(slate_date)[:10])
    local = datetime(day.year, day.month, day.day, tzinfo=ET)
    params = {
        "leagueID": SGO_LEAGUE_ID, "oddsAvailable": "true",
        "startsAfter": (local - timedelta(hours=6)).astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "startsBefore": (local + timedelta(days=1, hours=10)).astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "oddID": build_odd_id_filter(),
        "bookmakerID": _secret("SPORTSGAMEODDS_BOOKMAKERS") or DEFAULT_BOOKMAKERS,
        "includeAltLines": "false", "limit": 100,
    }
    try:
        response = requests.get(f"{SGO_BASE}/events", params=params, headers={"x-api-key": api_key}, timeout=20)
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return []
    events = payload.get("data") if isinstance(payload, Mapping) else []
    rows: list[dict[str, Any]] = []
    for event in events if isinstance(events, list) else []:
        if isinstance(event, Mapping):
            rows.extend(parse_event_props(event))
    return rows


__all__ = ["SGO_LEAGUE_ID", "STAT_IDS", "build_odd_id_filter", "fetch_sgo_cfb_player_props", "parse_event_props"]
