"""Odds-API.io CFB player-prop gap-fill transport.

This is a secondary/backup source. It never creates synthetic lines and only
emits supported player props that can be matched to one verified CFB game.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import math
import re
from typing import Any, Mapping, Sequence

import requests

from live_odds_feed import ODDS_BASE, decimal_to_american, get_api_key, get_bookmakers

SPORT = "american-football"
LEAGUE = "usa-ncaaf"

_MARKETS = {
    "player passing yards": "passing_yards",
    "passing yards": "passing_yards",
    "pass yds": "passing_yards",
    "player rushing yards": "rushing_yards",
    "rushing yards": "rushing_yards",
    "rush yds": "rushing_yards",
    "player receiving yards": "receiving_yards",
    "receiving yards": "receiving_yards",
    "receiving yds": "receiving_yards",
    "player receptions": "receiving_receptions",
    "receptions": "receiving_receptions",
    "player passing touchdowns": "passing_touchdowns",
    "passing touchdowns": "passing_touchdowns",
    "pass tds": "passing_touchdowns",
    "anytime touchdown": "touchdowns",
    "anytime td": "touchdowns",
    "player touchdown": "touchdowns",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _norm(value: Any) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", _text(value).casefold()))


def _finite(value: Any) -> float | None:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    return out if math.isfinite(out) else None


def _market_key(value: Any) -> str | None:
    text = _norm(value)
    for needle, key in _MARKETS.items():
        if _norm(needle) in text:
            return key
    return None


def _aware(value: Any) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    try:
        dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None or dt.utcoffset() is None:
        return None
    return dt.astimezone(timezone.utc)


def _same_team(left: Any, right: Any) -> bool:
    a, b = _norm(left), _norm(right)
    if not a or not b:
        return False
    return a == b or (len(a) >= 4 and len(b) >= 4 and (a in b or b in a))


def _rows(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, Mapping):
        return [dict(v, _attachment_key=str(k)) for k, v in value.items() if isinstance(v, Mapping)]
    if isinstance(value, list):
        return [dict(v) for v in value if isinstance(v, Mapping)]
    return []


def _american(value: Any) -> int | None:
    number = _finite(value)
    if number is None:
        return None
    if number > 1.0 and number < 20.0:
        return decimal_to_american(number)
    try:
        return int(round(number))
    except (TypeError, ValueError):
        return None


def _player_name(row: Mapping[str, Any], market: Mapping[str, Any]) -> str:
    for value in (
        row.get("playerName"), row.get("player_name"), row.get("participantName"),
        row.get("participant"), row.get("name"), row.get("label"),
        market.get("playerName"), market.get("player_name"),
    ):
        if isinstance(value, Mapping):
            value = value.get("displayName") or value.get("name") or value.get("fullName")
        text = _text(value)
        if text and _norm(text) not in {"over", "under", "o", "u"}:
            text = re.sub(r"\s+(?:over|under)\s+[-+]?\d+(?:\.\d+)?\s*$", "", text, flags=re.I).strip()
            if text:
                return text
    return ""


def _side(row: Mapping[str, Any]) -> str:
    for value in (row.get("side"), row.get("type"), row.get("name"), row.get("label")):
        text = _norm(value)
        if text in {"over", "o"} or text.startswith("over ") or text.endswith(" over"):
            return "over"
        if text in {"under", "u"} or text.startswith("under ") or text.endswith(" under"):
            return "under"
    return ""


def _line(row: Mapping[str, Any], market: Mapping[str, Any]) -> float | None:
    for key in ("line", "hdp", "points", "total", "threshold", "max"):
        value = _finite(row.get(key))
        if value is not None:
            return value
    for key in ("line", "hdp", "points", "total", "threshold"):
        value = _finite(market.get(key))
        if value is not None:
            return value
    return None


def parse_event_player_props(payload: Mapping[str, Any], *, observed_at_utc: str | None = None) -> list[dict[str, Any]]:
    if not isinstance(payload, Mapping):
        return []
    event_id = _text(payload.get("id") or payload.get("eventId"))
    away = _text(payload.get("away") or payload.get("away_team"))
    home = _text(payload.get("home") or payload.get("home_team"))
    event_start = _text(payload.get("date") or payload.get("startTime") or payload.get("start_time_utc"))
    default_stamp = observed_at_utc or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    books = payload.get("bookmakers") or {}
    if not isinstance(books, Mapping):
        return []
    out: list[dict[str, Any]] = []
    for raw_book, markets in books.items():
        book = _text(raw_book)
        if not book:
            continue
        market_rows = list(markets.values()) if isinstance(markets, Mapping) else markets if isinstance(markets, list) else []
        for market in market_rows:
            if not isinstance(market, Mapping):
                continue
            market_name = market.get("name") or market.get("label") or market.get("key") or market.get("type")
            stat = _market_key(market_name)
            if stat is None:
                continue
            stamp = _text(market.get("updatedAt") or market.get("updated_at") or default_stamp)
            outcomes = market.get("odds") or market.get("outcomes") or []
            if isinstance(outcomes, Mapping):
                outcomes = list(outcomes.values())
            if not isinstance(outcomes, list):
                continue
            for raw in outcomes:
                if not isinstance(raw, Mapping):
                    continue
                player = _player_name(raw, market)
                line = _line(raw, market)
                if not player or line is None:
                    continue
                side = _side(raw)
                if side in {"over", "under"}:
                    price = _american(raw.get("price") if raw.get("price") is not None else raw.get("americanOdds") if raw.get("americanOdds") is not None else raw.get("odds"))
                    out.append({
                        "provider": "Odds-API.io", "provider_event_id": event_id,
                        "provider_player_id": _text(raw.get("playerId") or raw.get("participantId")),
                        "provider_market_id": _text(market.get("id") or market.get("marketId") or market.get("_attachment_key")),
                        "player_name": player, "stat_id": stat, "sportsbook": book,
                        "side": side, "line": line, "price": price, "observed_at_utc": stamp,
                        "away_team": away, "home_team": home, "event_start": event_start,
                    })
                    continue
                over = raw.get("over")
                under = raw.get("under")
                if over is not None:
                    out.append({
                        "provider": "Odds-API.io", "provider_event_id": event_id,
                        "provider_player_id": _text(raw.get("playerId") or raw.get("participantId")),
                        "provider_market_id": _text(market.get("id") or market.get("marketId") or market.get("_attachment_key")),
                        "player_name": player, "stat_id": stat, "sportsbook": book,
                        "side": "over", "line": line, "price": _american(over), "observed_at_utc": stamp,
                        "away_team": away, "home_team": home, "event_start": event_start,
                    })
                if under is not None:
                    out.append({
                        "provider": "Odds-API.io", "provider_event_id": event_id,
                        "provider_player_id": _text(raw.get("playerId") or raw.get("participantId")),
                        "provider_market_id": _text(market.get("id") or market.get("marketId") or market.get("_attachment_key")),
                        "player_name": player, "stat_id": stat, "sportsbook": book,
                        "side": "under", "line": line, "price": _american(under), "observed_at_utc": stamp,
                        "away_team": away, "home_team": home, "event_start": event_start,
                    })
    return out


def _event_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [dict(row) for row in payload if isinstance(row, Mapping)]
    if isinstance(payload, Mapping):
        data = payload.get("data")
        return [dict(row) for row in data if isinstance(row, Mapping)] if isinstance(data, list) else []
    return []


def _match_event(game: Mapping[str, Any], events: Sequence[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    away = game.get("away_team") or game.get("awayTeam")
    home = game.get("home_team") or game.get("homeTeam")
    target = _aware(game.get("kickoff_iso") or game.get("start_time_utc") or game.get("date"))
    candidates: list[Mapping[str, Any]] = []
    for event in events:
        if not (_same_team(event.get("away"), away) and _same_team(event.get("home"), home)):
            continue
        event_dt = _aware(event.get("date") or event.get("startTime"))
        if target is not None and event_dt is not None and abs((event_dt - target).total_seconds()) > 45 * 60:
            continue
        candidates.append(event)
    return candidates[0] if len(candidates) == 1 else None


def fetch_odds_api_cfb_player_props(slate_games: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    key = get_api_key()
    if not key or not slate_games:
        return []
    kickoffs = [_aware(game.get("kickoff_iso") or game.get("start_time_utc") or game.get("date")) for game in slate_games]
    kickoffs = [value for value in kickoffs if value is not None]
    params: dict[str, Any] = {
        "apiKey": str(key), "sport": SPORT, "league": LEAGUE,
        "status": "pending,live", "limit": 100,
    }
    if kickoffs:
        params["from"] = (min(kickoffs) - timedelta(hours=6)).isoformat().replace("+00:00", "Z")
        params["to"] = (max(kickoffs) + timedelta(hours=8)).isoformat().replace("+00:00", "Z")
    try:
        response = requests.get(f"{ODDS_BASE}/events", params=params, timeout=15)
        response.raise_for_status()
        events = _event_list(response.json())
    except Exception:
        return []
    books = get_bookmakers()
    out: list[dict[str, Any]] = []
    for game in slate_games:
        event = _match_event(game, events)
        if event is None or event.get("id") is None:
            continue
        try:
            response = requests.get(
                f"{ODDS_BASE}/odds",
                params={"apiKey": str(key), "eventId": str(event.get("id")), "bookmakers": str(books)},
                timeout=15,
            )
            response.raise_for_status()
            payload = response.json()
        except Exception:
            continue
        payloads = payload if isinstance(payload, list) else payload.get("data") if isinstance(payload, Mapping) and isinstance(payload.get("data"), list) else [payload] if isinstance(payload, Mapping) else []
        for item in payloads:
            if not isinstance(item, Mapping):
                continue
            for row in parse_event_player_props(item):
                row["official_game_id"] = _text(game.get("official_game_id") or game.get("event_id") or game.get("game_id"))
                out.append(row)
    return out


__all__ = ["LEAGUE", "SPORT", "fetch_odds_api_cfb_player_props", "parse_event_player_props"]
