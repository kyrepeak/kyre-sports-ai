"""WNBA Assists — Step 2 verified daily slate feed.

Schedule only. No roster, injury, sportsbook, projection, Monte Carlo, PRA,
Points, Rebounds or Daily Picks production modules are imported here.

Primary: WNBA official CDN full-league schedule.
Confirmation/fallback: ESPN WNBA daily scoreboard.
All selection is by America/New_York calendar date so adjacent UTC dates cannot
leak yesterday/tomorrow games into the Assists slate.
"""
from __future__ import annotations

from datetime import datetime
import json
from typing import Any
import urllib.request
from zoneinfo import ZoneInfo

import streamlit as st

_ET = ZoneInfo("America/New_York")
_UTC = ZoneInfo("UTC")

WNBA_SCHEDULE_URL = "https://cdn.wnba.com/static/json/staticData/scheduleLeagueV2_1.json"
ESPN_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/scoreboard?dates={date_compact}"

# 2026 league membership. This is an identity guard only; it does not create games.
WNBA_TEAMS_2026 = {
    "Atlanta Dream", "Chicago Sky", "Connecticut Sun", "Dallas Wings",
    "Golden State Valkyries", "Indiana Fever", "Las Vegas Aces",
    "Los Angeles Sparks", "Minnesota Lynx", "New York Liberty",
    "Phoenix Mercury", "Portland Fire", "Seattle Storm", "Toronto Tempo",
    "Washington Mystics",
}


def _http_json(url: str, timeout: int = 12) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    meta: dict[str, Any] = {"url": url, "ok": False, "status": None, "error": ""}
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 KyreSportsAI/1.0",
                "Accept": "application/json,text/plain,*/*",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            meta["status"] = int(getattr(response, "status", 200) or 200)
            raw = response.read()
        payload = json.loads(raw.decode("utf-8"))
        if isinstance(payload, dict):
            meta["ok"] = True
            return payload, meta
        meta["error"] = "JSON root was not an object"
    except Exception as exc:  # diagnostics only; never fabricate schedule rows
        meta["error"] = f"{type(exc).__name__}: {exc}"
    return None, meta


def _team_name(team: Any) -> str:
    if not isinstance(team, dict):
        return ""
    full = str(team.get("teamName") or team.get("displayName") or team.get("name") or "").strip()
    city = str(team.get("teamCity") or team.get("location") or "").strip()
    nickname = str(team.get("teamName") or team.get("nickname") or "").strip()
    if full and (not city or full.lower().startswith(city.lower())):
        return full
    if city and nickname:
        return f"{city} {nickname}".strip()
    return full


def _parse_iso(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    # WNBA may expose an explicit ET timestamp without an offset.
    try:
        if text.endswith("Z"):
            return datetime.fromisoformat(text[:-1] + "+00:00").astimezone(_ET)
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=_ET)
        return dt.astimezone(_ET)
    except Exception:
        pass
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).replace(tzinfo=_ET)
        except Exception:
            continue
    return None


def _normalize_status(text: Any, code: Any = None) -> str:
    t = str(text or "").strip().upper()
    c = str(code or "").strip()
    if "FINAL" in t or c == "3":
        return "FINAL"
    if any(k in t for k in ("LIVE", "QTR", "HALF", "OT", "IN PROGRESS")) or c == "2":
        return "LIVE"
    if any(k in t for k in ("POSTPON", "CANCEL", "SUSPEND")):
        return t or "DELAYED"
    return "UPCOMING"


def _wnba_games(payload: dict[str, Any], slate_date: str) -> list[dict[str, Any]]:
    league = payload.get("leagueSchedule") if isinstance(payload, dict) else None
    if not isinstance(league, dict):
        league = payload
    game_dates = league.get("gameDates", []) if isinstance(league, dict) else []
    rows: list[dict[str, Any]] = []
    for date_block in game_dates if isinstance(game_dates, list) else []:
        if not isinstance(date_block, dict):
            continue
        games = date_block.get("games", [])
        for game in games if isinstance(games, list) else []:
            if not isinstance(game, dict):
                continue
            dt = None
            for key in ("gameDateTimeUTC", "gameDateTimeEst", "gameDateTime", "gameTimeUTC"):
                dt = _parse_iso(game.get(key))
                if dt:
                    break
            if dt is None:
                date_text = str(date_block.get("gameDate") or game.get("gameDate") or "")[:10]
                if date_text != slate_date:
                    continue
            elif dt.strftime("%Y-%m-%d") != slate_date:
                continue

            away = _team_name(game.get("awayTeam"))
            home = _team_name(game.get("homeTeam"))
            if not away or not home:
                continue
            rows.append({
                "game_id": str(game.get("gameId") or game.get("gameID") or ""),
                "away": away,
                "home": home,
                "tip_et": dt.strftime("%-I:%M %p ET") if dt else "TBD",
                "tip_iso_et": dt.isoformat() if dt else "",
                "venue": str(game.get("arenaName") or game.get("arena") or "TBD"),
                "status": _normalize_status(game.get("gameStatusText"), game.get("gameStatus")),
                "source": "WNBA official CDN",
            })
    return rows


def _espn_games(payload: dict[str, Any], slate_date: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    events = payload.get("events", []) if isinstance(payload, dict) else []
    for event in events if isinstance(events, list) else []:
        if not isinstance(event, dict):
            continue
        dt = _parse_iso(event.get("date"))
        if dt is None or dt.strftime("%Y-%m-%d") != slate_date:
            continue
        competitions = event.get("competitions", [])
        comp = competitions[0] if isinstance(competitions, list) and competitions else {}
        if not isinstance(comp, dict):
            continue
        away = home = ""
        for competitor in comp.get("competitors", []) if isinstance(comp.get("competitors"), list) else []:
            if not isinstance(competitor, dict):
                continue
            team = competitor.get("team", {})
            name = str(team.get("displayName") or team.get("shortDisplayName") or "").strip() if isinstance(team, dict) else ""
            if competitor.get("homeAway") == "away":
                away = name
            elif competitor.get("homeAway") == "home":
                home = name
        if not away or not home:
            continue
        status_obj = event.get("status", {}) if isinstance(event.get("status"), dict) else {}
        status_type = status_obj.get("type", {}) if isinstance(status_obj.get("type"), dict) else {}
        status_text = status_type.get("description") or status_type.get("detail") or status_type.get("name")
        venue_obj = comp.get("venue", {}) if isinstance(comp.get("venue"), dict) else {}
        rows.append({
            "game_id": str(event.get("id") or ""),
            "away": away,
            "home": home,
            "tip_et": dt.strftime("%-I:%M %p ET"),
            "tip_iso_et": dt.isoformat(),
            "venue": str(venue_obj.get("fullName") or "TBD"),
            "status": _normalize_status(status_text),
            "source": "ESPN WNBA daily",
        })
    return rows


def _key(row: dict[str, Any]) -> tuple[str, str]:
    return (str(row.get("away", "")).strip().lower(), str(row.get("home", "")).strip().lower())


@st.cache_data(ttl=300, show_spinner=False)
def load_verified_wnba_slate(slate_date: str) -> dict[str, Any]:
    compact = slate_date.replace("-", "")
    wnba_payload, wnba_meta = _http_json(WNBA_SCHEDULE_URL)
    espn_payload, espn_meta = _http_json(ESPN_SCOREBOARD_URL.format(date_compact=compact))

    wnba_rows = _wnba_games(wnba_payload or {}, slate_date)
    espn_rows = _espn_games(espn_payload or {}, slate_date)

    # Official WNBA is authoritative when available. ESPN confirms pairings and
    # supplies a safe fallback if the official transport is temporarily down.
    primary_rows = wnba_rows if wnba_rows else espn_rows
    confirmation_keys = {_key(r) for r in espn_rows}

    clean: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in primary_rows:
        k = _key(row)
        if not all(k) or k in seen:
            continue
        seen.add(k)
        row = dict(row)
        row["teams_valid"] = row["away"] in WNBA_TEAMS_2026 and row["home"] in WNBA_TEAMS_2026
        row["espn_confirmed"] = k in confirmation_keys if espn_rows else False
        clean.append(row)

    clean.sort(key=lambda r: str(r.get("tip_iso_et") or "9999"))
    teams = sorted({t for r in clean for t in (r.get("away"), r.get("home")) if t})
    invalid = [r for r in clean if not r.get("teams_valid")]

    if wnba_rows:
        verification = "VERIFIED" if clean and not invalid else ("NO GAMES" if not clean else "CHECK")
        authoritative_source = "WNBA official CDN"
    elif espn_rows:
        verification = "FALLBACK" if clean and not invalid else ("NO GAMES" if not clean else "CHECK")
        authoritative_source = "ESPN WNBA daily fallback"
    else:
        verification = "UNAVAILABLE"
        authoritative_source = "NONE"

    return {
        "slate_date": slate_date,
        "verification": verification,
        "source": authoritative_source,
        "games": clean,
        "games_found": len(clean),
        "teams_validated": len(teams) if not invalid else max(0, len(teams) - len({t for r in invalid for t in (r.get('away'), r.get('home')) if t not in WNBA_TEAMS_2026})),
        "wnba_games": len(wnba_rows),
        "espn_games": len(espn_rows),
        "espn_confirmed": sum(1 for r in clean if r.get("espn_confirmed")),
        "invalid_team_rows": len(invalid),
        "wnba_meta": wnba_meta,
        "espn_meta": espn_meta,
        "checked_at_et": datetime.now(_ET).strftime("%Y-%m-%d %I:%M:%S %p ET"),
    }


__all__ = ["load_verified_wnba_slate", "WNBA_TEAMS_2026"]
