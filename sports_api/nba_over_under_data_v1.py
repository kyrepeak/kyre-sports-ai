"""Kyre Sports API NBA Over/Under Step 2 read-only data provider."""
from __future__ import annotations

from datetime import date, datetime, timezone
import os
from typing import Any, Mapping
from zoneinfo import ZoneInfo

import httpx

NBA_OFFICIAL_SCHEDULE_URL = "https://cdn.nba.com/static/json/staticData/scheduleLeagueV2_1.json"
ESPN_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard"
THE_ODDS_API_URL = "https://api.the-odds-api.com/v4/sports/basketball_nba/odds"
PHOENIX_TIMEZONE = "America/Phoenix"
PHOENIX_TZ = ZoneInfo(PHOENIX_TIMEZONE)
ODDS_MARKET = "totals"
NBA_TEAMS = frozenset({"ATL","BOS","BKN","CHA","CHI","CLE","DAL","DEN","DET","GSW","HOU","IND","LAC","LAL","MEM","MIA","MIL","MIN","NOP","NYK","OKC","ORL","PHI","PHX","POR","SAC","SAS","TOR","UTA","WAS"})


class NBAOverUnderDataError(RuntimeError):
    pass


def _day(value: str) -> str:
    try:
        return date.fromisoformat(str(value)[:10]).isoformat()
    except ValueError as exc:
        raise NBAOverUnderDataError("date must be YYYY-MM-DD") from exc


def _dt(value: Any) -> datetime:
    text = str(value or "").strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise NBAOverUnderDataError("invalid event timestamp") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _phoenix(value: Any) -> str:
    return _dt(value).astimezone(PHOENIX_TZ).isoformat(timespec="seconds")


def _phoenix_day(value: Any) -> str:
    return _dt(value).astimezone(PHOENIX_TZ).date().isoformat()


def _get_json(url: str, *, params: Mapping[str, Any] | None = None, timeout: float = 10.0) -> Any:
    with httpx.Client(follow_redirects=True, timeout=timeout, headers={"accept":"application/json","user-agent":"kyre-sports-api-nba-step2/1"}) as client:
        response = client.get(url, params=dict(params or {}))
        response.raise_for_status()
        return response.json()


def _official(payload: Mapping[str, Any], day: str) -> list[dict[str, Any]]:
    league = payload.get("leagueSchedule") if isinstance(payload, Mapping) else None
    blocks = league.get("gameDates") if isinstance(league, Mapping) else None
    if not isinstance(blocks, list):
        raise NBAOverUnderDataError("official NBA schedule shape is invalid")
    rows: list[dict[str, Any]] = []
    for block in blocks:
        if not isinstance(block, Mapping):
            continue
        for game in block.get("games") or []:
            if not isinstance(game, Mapping):
                continue
            home, away = game.get("homeTeam") or {}, game.get("awayTeam") or {}
            h, a = str(home.get("teamTricode") or "").upper(), str(away.get("teamTricode") or "").upper()
            tip = game.get("gameDateTimeUTC")
            if h not in NBA_TEAMS or a not in NBA_TEAMS or h == a or not tip or _phoenix_day(tip) != day:
                continue
            code = int(game.get("gameStatus") or 0)
            status = "FINAL" if code == 3 else "LIVE" if code == 2 else "UPCOMING"
            rows.append({
                "game_id": str(game.get("gameId") or ""), "game_date_phoenix": day,
                "start_time_utc": str(tip), "tip_phoenix": _phoenix(tip), "status": status,
                "status_text": str(game.get("gameStatusText") or ""),
                "home_team_id": int(home.get("teamId") or 0), "home_team": " ".join(x for x in (str(home.get("teamCity") or "").strip(), str(home.get("teamName") or h).strip()) if x),
                "home_abbr": h, "home_record": f"{home.get('wins')}-{home.get('losses')}" if home.get("wins") is not None and home.get("losses") is not None else "",
                "away_team_id": int(away.get("teamId") or 0), "away_team": " ".join(x for x in (str(away.get("teamCity") or "").strip(), str(away.get("teamName") or a).strip()) if x),
                "away_abbr": a, "away_record": f"{away.get('wins')}-{away.get('losses')}" if away.get("wins") is not None and away.get("losses") is not None else "",
                "arena": str(game.get("arenaName") or ""), "city": str(game.get("arenaCity") or ""), "source": "NBA_OFFICIAL_CDN",
            })
    return rows


def _espn(payload: Mapping[str, Any], day: str) -> list[dict[str, Any]]:
    events = payload.get("events") if isinstance(payload, Mapping) else None
    if not isinstance(events, list):
        raise NBAOverUnderDataError("ESPN NBA schedule shape is invalid")
    rows: list[dict[str, Any]] = []
    for event in events:
        comps = event.get("competitions") or [] if isinstance(event, Mapping) else []
        if not comps or not isinstance(comps[0], Mapping):
            continue
        comp = comps[0]
        sides = {str(x.get("homeAway") or ""): x for x in comp.get("competitors") or [] if isinstance(x, Mapping)}
        hs, aw = sides.get("home") or {}, sides.get("away") or {}
        ht, at = hs.get("team") or {}, aw.get("team") or {}
        h, a = str(ht.get("abbreviation") or "").upper(), str(at.get("abbreviation") or "").upper()
        tip = event.get("date") or comp.get("date")
        if h not in NBA_TEAMS or a not in NBA_TEAMS or h == a or not tip or _phoenix_day(tip) != day:
            continue
        state = str((((event.get("status") or {}).get("type") or {}).get("state") or "")).lower()
        status = "FINAL" if state in {"post","final"} else "LIVE" if state in {"in","live"} else "UPCOMING"
        venue = comp.get("venue") or {}; addr = venue.get("address") or {} if isinstance(venue, Mapping) else {}
        def record(side: Mapping[str, Any]) -> str:
            rs = side.get("records") or []
            item = next((r for r in rs if isinstance(r, Mapping) and r.get("type") == "total"), {})
            return str(item.get("summary") or "")
        rows.append({
            "game_id": str(event.get("id") or ""), "game_date_phoenix": day, "start_time_utc": str(tip), "tip_phoenix": _phoenix(tip),
            "status": status, "status_text": str((((event.get("status") or {}).get("type") or {}).get("shortDetail") or "")),
            "home_team_id": int(ht.get("id") or 0), "home_team": str(ht.get("displayName") or h), "home_abbr": h, "home_record": record(hs),
            "away_team_id": int(at.get("id") or 0), "away_team": str(at.get("displayName") or a), "away_abbr": a, "away_record": record(aw),
            "arena": str(venue.get("fullName") or "") if isinstance(venue, Mapping) else "", "city": str(addr.get("city") or "") if isinstance(addr, Mapping) else "", "source": "ESPN_NBA_SCOREBOARD",
        })
    return rows


def _schedule(day: str) -> tuple[list[dict[str, Any]], str]:
    try:
        return _official(_get_json(NBA_OFFICIAL_SCHEDULE_URL), day), "NBA_OFFICIAL_CDN"
    except Exception as primary:
        try:
            payload = _get_json(ESPN_SCOREBOARD_URL, params={"dates": day.replace("-", ""), "limit": 100})
            return _espn(payload, day), "ESPN_NBA_SCOREBOARD"
        except Exception as fallback:
            raise NBAOverUnderDataError(f"NBA schedule sources unavailable: {primary}") from fallback


def _totals() -> tuple[list[dict[str, Any]], str]:
    key = str(os.getenv("THE_ODDS_API_KEY") or "").strip()
    if not key:
        return [], "NOT_CONFIGURED"
    try:
        payload = _get_json(THE_ODDS_API_URL, params={"apiKey":key,"regions":"us","markets":ODDS_MARKET,"oddsFormat":"american","dateFormat":"iso"})
    except Exception:
        return [], "UNAVAILABLE"
    rows: list[dict[str, Any]] = []
    if not isinstance(payload, list):
        return [], "INVALID_PAYLOAD"
    for event in payload:
        if not isinstance(event, Mapping) or event.get("sport_key") != "basketball_nba":
            continue
        for book in event.get("bookmakers") or []:
            for market in book.get("markets") or [] if isinstance(book, Mapping) else []:
                if not isinstance(market, Mapping) or market.get("key") != "totals":
                    continue
                outcomes = market.get("outcomes") or []
                over = next((o for o in outcomes if isinstance(o, Mapping) and o.get("name") == "Over"), None)
                under = next((o for o in outcomes if isinstance(o, Mapping) and o.get("name") == "Under"), None)
                if over and under and over.get("point") == under.get("point"):
                    rows.append({"event_id":str(event.get("id") or ""),"home_team":str(event.get("home_team") or ""),"away_team":str(event.get("away_team") or ""),"bookmaker_key":str(book.get("key") or ""),"bookmaker":str(book.get("title") or ""),"market_total":over.get("point"),"over_price":over.get("price"),"under_price":under.get("price"),"source":"THE_ODDS_API"})
    return rows, "AVAILABLE" if rows else "NO_TOTALS"


def build_nba_over_under_slate(selected_date: str) -> dict[str, Any]:
    day = _day(selected_date)
    games, schedule_source = _schedule(day)
    totals, market_state = _totals()
    return {
        "data_type": "nba_over_under_step2_slate_v1",
        "source": "Kyre Sports API",
        "date": day,
        "timezone": PHOENIX_TIMEZONE,
        "games": games,
        "totals": totals,
        "market_state": market_state,
        "provenance": {"schedule": schedule_source, "market": "THE_ODDS_API" if market_state != "NOT_CONFIGURED" else None},
        "projection_influence": 0.0,
    }


__all__ = ["NBAOverUnderDataError", "NBA_OFFICIAL_SCHEDULE_URL", "ESPN_SCOREBOARD_URL", "PHOENIX_TIMEZONE", "build_nba_over_under_slate"]
