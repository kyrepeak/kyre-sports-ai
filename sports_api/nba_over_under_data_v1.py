"""NBA Over/Under Step 2 provider for Kyre Sports API.

Read-only NBA data boundary. Schedule truth comes from the official NBA schedule
with ESPN NBA scoreboard fallback. The totals market is optional and server-side
only; no sportsbook key is ever exposed to Streamlit.
"""
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
NBA_TEAM_ABBREVIATIONS = frozenset({
    "ATL", "BOS", "BKN", "CHA", "CHI", "CLE", "DAL", "DEN", "DET", "GSW",
    "HOU", "IND", "LAC", "LAL", "MEM", "MIA", "MIL", "MIN", "NOP", "NYK",
    "OKC", "ORL", "PHI", "PHX", "POR", "SAC", "SAS", "TOR", "UTA", "WAS",
})


class NBAOverUnderDataError(RuntimeError):
    pass


def _day_text(value: str | date | datetime) -> str:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value or "").strip()
    try:
        return date.fromisoformat(text[:10]).isoformat()
    except ValueError as exc:
        raise NBAOverUnderDataError("invalid NBA slate date") from exc


def _parse_utc(value: Any) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise NBAOverUnderDataError("missing NBA tip time")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _phoenix(value: Any) -> tuple[str, str]:
    local = _parse_utc(value).astimezone(PHOENIX_TZ)
    return local.date().isoformat(), local.isoformat(timespec="seconds")


def _nba_pair(home: str, away: str) -> bool:
    home, away = home.upper(), away.upper()
    return home in NBA_TEAM_ABBREVIATIONS and away in NBA_TEAM_ABBREVIATIONS and home != away


def _get_json(
    url: str,
    *,
    params: Mapping[str, Any] | None = None,
    timeout: float = 8.0,
    transport: Any = None,
) -> Any:
    if transport is not None:
        return transport.get_json(url, params=params, timeout=timeout)
    with httpx.Client(
        timeout=timeout,
        headers={"accept": "application/json", "user-agent": "kyre-sports-api-nba-step2/1"},
        follow_redirects=True,
    ) as client:
        response = client.get(url, params=dict(params or {}))
        response.raise_for_status()
        return response.json()


def _official_games(payload: Any, day: str) -> list[dict[str, Any]]:
    league = payload.get("leagueSchedule") if isinstance(payload, Mapping) else None
    blocks = league.get("gameDates") if isinstance(league, Mapping) else None
    if not isinstance(blocks, list):
        raise NBAOverUnderDataError("official NBA schedule shape invalid")
    rows: list[dict[str, Any]] = []
    for block in blocks:
        if not isinstance(block, Mapping):
            continue
        for game in block.get("games") or []:
            if not isinstance(game, Mapping):
                continue
            home, away = game.get("homeTeam") or {}, game.get("awayTeam") or {}
            if not isinstance(home, Mapping) or not isinstance(away, Mapping):
                continue
            habbr = str(home.get("teamTricode") or "").upper()
            aabbr = str(away.get("teamTricode") or "").upper()
            if not _nba_pair(habbr, aabbr):
                continue
            raw_tip = game.get("gameDateTimeUTC")
            try:
                local_day, tip = _phoenix(raw_tip)
            except Exception:
                continue
            if local_day != day:
                continue
            status_code = int(game.get("gameStatus") or 0)
            status = "FINAL" if status_code == 3 else ("LIVE" if status_code == 2 else "UPCOMING")
            rows.append({
                "game_id": str(game.get("gameId") or ""),
                "game_date_phoenix": local_day,
                "start_time_utc": str(raw_tip),
                "tip_phoenix": tip,
                "status": status,
                "status_text": str(game.get("gameStatusText") or ""),
                "home_team_id": int(home.get("teamId") or 0),
                "home_team": " ".join(x for x in (str(home.get("teamCity") or "").strip(), str(home.get("teamName") or habbr).strip()) if x),
                "home_abbr": habbr,
                "home_record": "" if home.get("wins") is None or home.get("losses") is None else f"{home.get('wins')}-{home.get('losses')}",
                "away_team_id": int(away.get("teamId") or 0),
                "away_team": " ".join(x for x in (str(away.get("teamCity") or "").strip(), str(away.get("teamName") or aabbr).strip()) if x),
                "away_abbr": aabbr,
                "away_record": "" if away.get("wins") is None or away.get("losses") is None else f"{away.get('wins')}-{away.get('losses')}",
                "arena": str(game.get("arenaName") or ""),
                "city": str(game.get("arenaCity") or ""),
                "source": "NBA_OFFICIAL_CDN",
            })
    return rows


def _espn_games(payload: Any, day: str) -> list[dict[str, Any]]:
    events = payload.get("events") if isinstance(payload, Mapping) else None
    if not isinstance(events, list):
        raise NBAOverUnderDataError("ESPN NBA schedule shape invalid")
    rows: list[dict[str, Any]] = []
    for event in events:
        if not isinstance(event, Mapping):
            continue
        comps = event.get("competitions") or []
        if not comps or not isinstance(comps[0], Mapping):
            continue
        comp = comps[0]
        sides = {str(x.get("homeAway") or "").lower(): x for x in (comp.get("competitors") or []) if isinstance(x, Mapping)}
        home_comp, away_comp = sides.get("home") or {}, sides.get("away") or {}
        home, away = home_comp.get("team") or {}, away_comp.get("team") or {}
        if not isinstance(home, Mapping) or not isinstance(away, Mapping):
            continue
        habbr, aabbr = str(home.get("abbreviation") or "").upper(), str(away.get("abbreviation") or "").upper()
        if not _nba_pair(habbr, aabbr):
            continue
        raw_tip = event.get("date") or comp.get("date")
        try:
            local_day, tip = _phoenix(raw_tip)
        except Exception:
            continue
        if local_day != day:
            continue
        state = str((((event.get("status") or {}).get("type") or {}).get("state") or "pre")).lower()
        status = "FINAL" if state in {"post", "final"} else ("LIVE" if state in {"in", "live"} else "UPCOMING")
        venue = comp.get("venue") or {}
        address = venue.get("address") or {} if isinstance(venue, Mapping) else {}
        def rec(comp_side: Mapping[str, Any]) -> str:
            rs = comp_side.get("records") or []
            record = next((r for r in rs if isinstance(r, Mapping) and str(r.get("type") or "").lower() == "total"), None)
            return str((record or {}).get("summary") or "")
        rows.append({
            "game_id": str(event.get("id") or ""),
            "game_date_phoenix": local_day,
            "start_time_utc": str(raw_tip),
            "tip_phoenix": tip,
            "status": status,
            "status_text": str((((event.get("status") or {}).get("type") or {}).get("shortDetail") or "")),
            "home_team_id": int(home.get("id") or 0),
            "home_team": str(home.get("displayName") or habbr),
            "home_abbr": habbr,
            "home_record": rec(home_comp),
            "away_team_id": int(away.get("id") or 0),
            "away_team": str(away.get("displayName") or aabbr),
            "away_abbr": aabbr,
            "away_record": rec(away_comp),
            "arena": str(venue.get("fullName") or "") if isinstance(venue, Mapping) else "",
            "city": str(address.get("city") or "") if isinstance(address, Mapping) else "",
            "source": "ESPN_NBA_SCOREBOARD",
        })
    return rows


def _schedule(day: str, *, transport: Any = None) -> tuple[list[dict[str, Any]], str]:
    try:
        official = _get_json(NBA_OFFICIAL_SCHEDULE_URL, timeout=8, transport=transport)
        return _official_games(official, day), "NBA_OFFICIAL_CDN"
    except Exception:
        fallback = _get_json(
            ESPN_SCOREBOARD_URL,
            params={"dates": day.replace("-", ""), "limit": 100},
            timeout=8,
            transport=transport,
        )
        return _espn_games(fallback, day), "ESPN_NBA_SCOREBOARD"


def _totals(*, transport: Any = None, api_key: str | None = None) -> tuple[list[dict[str, Any]], str]:
    key = str(api_key or os.environ.get("THE_ODDS_API_KEY") or "").strip()
    if not key:
        return [], "NOT_CONFIGURED"
    try:
        payload = _get_json(
            THE_ODDS_API_URL,
            params={"apiKey": key, "regions": "us", "markets": "totals", "oddsFormat": "american", "dateFormat": "iso"},
            timeout=8,
            transport=transport,
        )
    except Exception:
        return [], "UNAVAILABLE"
    if not isinstance(payload, list):
        return [], "INVALID"
    rows: list[dict[str, Any]] = []
    for event in payload:
        if not isinstance(event, Mapping) or event.get("sport_key") != "basketball_nba":
            continue
        for book in event.get("bookmakers") or []:
            if not isinstance(book, Mapping):
                continue
            for market in book.get("markets") or []:
                if not isinstance(market, Mapping) or market.get("key") != "totals":
                    continue
                outcomes = {str(x.get("name")): x for x in market.get("outcomes") or [] if isinstance(x, Mapping)}
                over, under = outcomes.get("Over"), outcomes.get("Under")
                if not over or not under or over.get("point") != under.get("point"):
                    continue
                rows.append({
                    "event_id": str(event.get("id") or ""),
                    "home_team": str(event.get("home_team") or ""),
                    "away_team": str(event.get("away_team") or ""),
                    "bookmaker_key": str(book.get("key") or ""),
                    "bookmaker": str(book.get("title") or ""),
                    "market_total": over.get("point"),
                    "over_price": over.get("price"),
                    "under_price": under.get("price"),
                    "source": "THE_ODDS_API",
                })
    return rows, "READY"


def build_nba_over_under_slate(
    selected_date: str | date | datetime,
    *,
    transport: Any = None,
    odds_api_key: str | None = None,
) -> dict[str, Any]:
    day = _day_text(selected_date)
    games, schedule_source = _schedule(day, transport=transport)
    totals, market_state = _totals(transport=transport, api_key=odds_api_key)
    return {
        "data_type": "nba_over_under_step2_slate_v1",
        "source": "Kyre Sports API",
        "date": day,
        "timezone": PHOENIX_TIMEZONE,
        "games": games,
        "totals": totals,
        "schedule_source": schedule_source,
        "market_provider": "THE_ODDS_API",
        "market_state": market_state,
        "projection_influence": 0.0,
        "sportsbook_projection_influence": 0.0,
    }


__all__ = [
    "NBA_OFFICIAL_SCHEDULE_URL",
    "ESPN_SCOREBOARD_URL",
    "THE_ODDS_API_URL",
    "PHOENIX_TIMEZONE",
    "NBAOverUnderDataError",
    "build_nba_over_under_slate",
]
