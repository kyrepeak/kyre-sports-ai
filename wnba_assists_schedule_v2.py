"""WNBA Assists — Step 2 verified daily slate V3.

Schedule-only repair. This module copies the proven Eastern-date/provider
reconciliation behavior from the PRA V2.4 slate hotfix into an isolated Assists
loader. It does not import PRA, Points, Rebounds, Daily Picks, roster, injury,
sportsbook, projection or Monte Carlo production code.

Primary: WNBA official full-season CDN.
Independent checks: ESPN WNBA daily scoreboard + ESPN WNBA season scoreboard.
All games are assigned to the America/New_York basketball date.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st

_ET = ZoneInfo("America/New_York")

WNBA_SCHEDULE_URL = "https://cdn.wnba.com/static/json/staticData/scheduleLeagueV2.json"
ESPN_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/scoreboard"

# Canonical 2026 WNBA identities. IDs are used to reconcile providers even when
# their display-name formatting differs.
_TEAM_BY_ID = {
    1611661330: ("Atlanta Dream", "ATL"),
    1611661329: ("Chicago Sky", "CHI"),
    1611661323: ("Connecticut Sun", "CON"),
    1611661321: ("Dallas Wings", "DAL"),
    1611661325: ("Indiana Fever", "IND"),
    1611661319: ("Las Vegas Aces", "LVA"),
    1611661320: ("Los Angeles Sparks", "LAS"),
    1611661324: ("Minnesota Lynx", "MIN"),
    1611661313: ("New York Liberty", "NYL"),
    1611661317: ("Phoenix Mercury", "PHX"),
    1611661328: ("Seattle Storm", "SEA"),
    1611661322: ("Washington Mystics", "WAS"),
    1611661331: ("Golden State Valkyries", "GSV"),
    1611661327: ("Portland Fire", "POR"),
    1611661332: ("Toronto Tempo", "TOR"),
}
WNBA_TEAMS_2026 = {name for name, _ in _TEAM_BY_ID.values()}

_TEAM_ID_BY_ALIAS: dict[str, int] = {}
for _tid, (_name, _abbr) in _TEAM_BY_ID.items():
    _TEAM_ID_BY_ALIAS[_name.upper()] = _tid
    _TEAM_ID_BY_ALIAS[_abbr.upper()] = _tid
_TEAM_ID_BY_ALIAS.update({
    "ATL": 1611661330,
    "CHI": 1611661329,
    "CON": 1611661323,
    "DAL": 1611661321,
    "IND": 1611661325,
    "LV": 1611661319,
    "LVA": 1611661319,
    "LA": 1611661320,
    "LAS": 1611661320,
    "MIN": 1611661324,
    "NY": 1611661313,
    "NYL": 1611661313,
    "PHO": 1611661317,
    "PHX": 1611661317,
    "SEA": 1611661328,
    "WSH": 1611661322,
    "WAS": 1611661322,
    "GS": 1611661331,
    "GSV": 1611661331,
    "PDX": 1611661327,
    "POR": 1611661327,
    "TOR": 1611661332,
})


def _request_json(provider: str, url: str, *, params=None, timeout: int = 10, attempts: int = 2):
    meta: dict[str, Any] = {
        "provider": provider,
        "url": url,
        "host": urlparse(url).netloc,
        "ok": False,
        "request_ok": False,
        "status": None,
        "http": None,
        "json": False,
        "bytes": 0,
        "elapsed_ms": None,
        "error": "",
        "selected_games": 0,
        "raw_games": 0,
        "valid_games": 0,
        "rejected_games": 0,
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (iPad; CPU OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1",
        "Accept": "application/json,text/plain,*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
    }
    last_error = None
    for n in range(max(1, int(attempts))):
        try:
            call_params = dict(params or {})
            if n and provider.startswith("WNBA"):
                call_params["_"] = pd.Timestamp.utcnow().strftime("%Y%m%d%H%M%S")
            response = requests.get(
                url,
                params=call_params or None,
                headers=headers,
                timeout=timeout,
            )
            status = int(response.status_code)
            meta["status"] = status
            meta["http"] = status
            meta["bytes"] = len(response.content or b"")
            try:
                meta["elapsed_ms"] = int(response.elapsed.total_seconds() * 1000)
            except Exception:
                pass
            response.raise_for_status()
            text = (response.text or "").lstrip()
            if not text or not text.startswith(("{", "[")):
                raise ValueError("empty/non-JSON response")
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError("JSON root was not an object")
            meta["ok"] = True
            meta["request_ok"] = True
            meta["json"] = True
            meta["error"] = ""
            return payload, meta
        except Exception as exc:
            last_error = exc
    meta["error"] = f"{type(last_error).__name__}: {last_error}"[:240] if last_error else "request failed"
    return None, meta


def _utc_to_et(value: Any) -> datetime | None:
    """Parse a timestamp whose FIELD semantics are UTC, even when it lacks Z."""
    if value is None or str(value).strip() == "":
        return None
    try:
        ts = pd.to_datetime(value, utc=True, errors="raise")
        return ts.tz_convert(_ET).to_pydatetime()
    except Exception:
        return None


def _et_local(value: Any) -> datetime | None:
    """Parse a timestamp whose FIELD semantics are Eastern/local."""
    if value is None or str(value).strip() == "":
        return None
    try:
        ts = pd.to_datetime(value, errors="raise")
        if getattr(ts, "tzinfo", None) is None:
            ts = ts.tz_localize(_ET)
        else:
            ts = ts.tz_convert(_ET)
        return ts.to_pydatetime()
    except Exception:
        return None


def _block_date(value: Any) -> str:
    if value is None:
        return ""
    try:
        return pd.to_datetime(value, errors="raise").strftime("%Y-%m-%d")
    except Exception:
        return str(value)[:10]


def _cdn_datetime_et(game: dict[str, Any]) -> datetime | None:
    # Critical: gameDateTimeUTC is UTC by definition. The WNBA feed can omit a
    # trailing Z, so generic naive-datetime parsing is wrong here.
    dt = _utc_to_et(game.get("gameDateTimeUTC"))
    if dt:
        return dt
    dt = _et_local(game.get("gameDateTimeEst"))
    if dt:
        return dt
    dt = _et_local(game.get("gameDateTime"))
    if dt:
        return dt
    return _utc_to_et(game.get("gameTimeUTC"))


def _team_name_from_parts(team: Any) -> str:
    if not isinstance(team, dict):
        return ""
    display = str(team.get("displayName") or team.get("shortDisplayName") or "").strip()
    if display:
        return display
    city = str(team.get("teamCity") or team.get("location") or "").strip()
    nick = str(team.get("teamName") or team.get("nickname") or team.get("name") or "").strip()
    if city and nick and not nick.lower().startswith(city.lower()):
        return f"{city} {nick}".strip()
    return nick or city


def _team_id(team: Any, direct: Any = None) -> int:
    try:
        tid = int(direct or 0)
    except Exception:
        tid = 0
    if tid in _TEAM_BY_ID:
        return tid
    if not isinstance(team, dict):
        return 0
    candidates = (
        team.get("abbreviation"),
        team.get("teamTricode"),
        team.get("displayName"),
        team.get("shortDisplayName"),
        _team_name_from_parts(team),
        team.get("name"),
    )
    for value in candidates:
        key = str(value or "").strip().upper()
        if key in _TEAM_ID_BY_ALIAS:
            return _TEAM_ID_BY_ALIAS[key]
    return 0


def _canonical_team(tid: int, fallback: str) -> tuple[str, str]:
    if tid in _TEAM_BY_ID:
        return _TEAM_BY_ID[tid]
    return fallback, ""


def _normalize_status(text: Any, code: Any = None) -> str:
    t = str(text or "").strip().upper()
    c = str(code or "").strip().upper()
    if "FINAL" in t or c in {"3", "POST", "FINAL"}:
        return "FINAL"
    if any(k in t for k in ("LIVE", "QTR", "QUARTER", "HALF", "OT", "IN PROGRESS")) or c in {"2", "IN", "LIVE"}:
        return "LIVE"
    if any(k in t for k in ("POSTPON", "CANCEL", "SUSPEND", "DELAY")):
        return t or "DELAYED"
    return "UPCOMING"


def _parse_cdn(payload: dict[str, Any], slate_date: str) -> tuple[list[dict[str, Any]], dict[str, int], list[dict[str, Any]]]:
    league = payload.get("leagueSchedule") if isinstance(payload, dict) else None
    if not isinstance(league, dict):
        league = payload if isinstance(payload, dict) else {}
    rows: list[dict[str, Any]] = []
    selected: list[dict[str, Any]] = []
    raw_games = rejected = 0

    game_dates = league.get("gameDates", []) if isinstance(league, dict) else []
    for block in game_dates if isinstance(game_dates, list) else []:
        if not isinstance(block, dict):
            continue
        block_date = _block_date(block.get("gameDate"))
        games = block.get("games", [])
        for game in games if isinstance(games, list) else []:
            if not isinstance(game, dict):
                continue
            raw_games += 1
            away_obj = game.get("awayTeam") or {}
            home_obj = game.get("homeTeam") or {}
            away_id = _team_id(away_obj, away_obj.get("teamId") if isinstance(away_obj, dict) else None)
            home_id = _team_id(home_obj, home_obj.get("teamId") if isinstance(home_obj, dict) else None)
            if away_id not in _TEAM_BY_ID or home_id not in _TEAM_BY_ID:
                rejected += 1
                continue

            dt = _cdn_datetime_et(game)
            game_date = dt.strftime("%Y-%m-%d") if dt else block_date
            away_name, away_abbr = _canonical_team(away_id, _team_name_from_parts(away_obj))
            home_name, home_abbr = _canonical_team(home_id, _team_name_from_parts(home_obj))
            row = {
                "game_id": str(game.get("gameId") or game.get("gameID") or ""),
                "away_team_id": away_id,
                "home_team_id": home_id,
                "away": away_name,
                "home": home_name,
                "away_tricode": str((away_obj or {}).get("teamTricode") or away_abbr),
                "home_tricode": str((home_obj or {}).get("teamTricode") or home_abbr),
                "game_date": game_date,
                "tip_et": dt.strftime("%-I:%M %p ET") if dt else "TBD",
                "tip_iso_et": dt.isoformat() if dt else "",
                "venue": str(game.get("arenaName") or game.get("arenaCity") or "TBD"),
                "status": _normalize_status(game.get("gameStatusText"), game.get("gameStatus")),
                "source": "WNBA official CDN",
            }
            rows.append(row)
            if game_date == slate_date:
                selected.append(row)

    selected = _dedupe(selected)
    return selected, {
        "raw_games": raw_games,
        "valid_games": len(rows),
        "rejected_games": rejected,
        "selected_games": len(selected),
    }, rows


def _parse_espn(payload: dict[str, Any], slate_date: str, source: str) -> tuple[list[dict[str, Any]], dict[str, int], list[dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    selected: list[dict[str, Any]] = []
    raw_games = rejected = 0

    events = payload.get("events", []) if isinstance(payload, dict) else []
    for event in events if isinstance(events, list) else []:
        if not isinstance(event, dict):
            continue
        raw_games += 1
        comps = event.get("competitions") or []
        comp = comps[0] if isinstance(comps, list) and comps else {}
        if not isinstance(comp, dict):
            rejected += 1
            continue

        sides: dict[str, dict[str, Any]] = {}
        competitors = comp.get("competitors", [])
        for competitor in competitors if isinstance(competitors, list) else []:
            if isinstance(competitor, dict):
                sides[str(competitor.get("homeAway") or "").lower()] = competitor
        away_c, home_c = sides.get("away") or {}, sides.get("home") or {}
        away_obj = away_c.get("team") or {}
        home_obj = home_c.get("team") or {}
        away_id = _team_id(away_obj)
        home_id = _team_id(home_obj)
        if away_id not in _TEAM_BY_ID or home_id not in _TEAM_BY_ID:
            rejected += 1
            continue

        dt = _utc_to_et(event.get("date") or comp.get("date"))
        if dt is None:
            rejected += 1
            continue
        game_date = dt.strftime("%Y-%m-%d")
        status_obj = event.get("status") if isinstance(event.get("status"), dict) else {}
        status_type = status_obj.get("type") if isinstance(status_obj.get("type"), dict) else {}
        status_text = (
            status_type.get("description")
            or status_type.get("detail")
            or status_type.get("shortDetail")
            or status_type.get("name")
            or ""
        )
        venue_obj = comp.get("venue") if isinstance(comp.get("venue"), dict) else {}
        away_name, away_abbr = _canonical_team(away_id, _team_name_from_parts(away_obj))
        home_name, home_abbr = _canonical_team(home_id, _team_name_from_parts(home_obj))
        row = {
            "game_id": str(event.get("id") or ""),
            "away_team_id": away_id,
            "home_team_id": home_id,
            "away": away_name,
            "home": home_name,
            "away_tricode": str((away_obj or {}).get("abbreviation") or away_abbr),
            "home_tricode": str((home_obj or {}).get("abbreviation") or home_abbr),
            "game_date": game_date,
            "tip_et": dt.strftime("%-I:%M %p ET"),
            "tip_iso_et": dt.isoformat(),
            "venue": str(venue_obj.get("fullName") or "TBD"),
            "status": _normalize_status(status_text, status_type.get("state")),
            "source": source,
        }
        rows.append(row)
        if game_date == slate_date:
            selected.append(row)

    selected = _dedupe(selected)
    return selected, {
        "raw_games": raw_games,
        "valid_games": len(rows),
        "rejected_games": rejected,
        "selected_games": len(selected),
    }, rows


def _dedupe(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[tuple[int, int]] = set()
    for row in rows:
        key = (int(row.get("away_team_id") or 0), int(row.get("home_team_id") or 0))
        if not all(key) or key in seen:
            continue
        seen.add(key)
        out.append(dict(row))
    out.sort(key=lambda r: str(r.get("tip_iso_et") or "9999"))
    return out


def _signature(rows: list[dict[str, Any]]) -> tuple[tuple[int, int], ...]:
    pairs = []
    for row in rows or []:
        try:
            pairs.append((int(row.get("away_team_id") or 0), int(row.get("home_team_id") or 0)))
        except Exception:
            continue
    return tuple(sorted(set(pairs)))


def _merge_meta(meta: dict[str, Any], counts: dict[str, int]) -> dict[str, Any]:
    out = dict(meta)
    out.update(counts)
    return out


@st.cache_data(ttl=300, show_spinner=False)
def load_verified_wnba_slate(slate_date: str) -> dict[str, Any]:
    slate_date = pd.to_datetime(slate_date).strftime("%Y-%m-%d")
    year = pd.to_datetime(slate_date).year

    attempts: list[dict[str, Any]] = []
    candidates: list[tuple[int, list[dict[str, Any]], str]] = []
    season_sources_ok = 0

    # 1) Official WNBA full-season CDN.
    payload, wnba_meta = _request_json("WNBA official CDN", WNBA_SCHEDULE_URL, timeout=10, attempts=2)
    if payload is not None:
        selected, counts, all_rows = _parse_cdn(payload, slate_date)
        wnba_meta = _merge_meta(wnba_meta, counts)
        wnba_meta["parse_ok"] = True
        if all_rows:
            season_sources_ok += 1
        if selected:
            candidates.append((0, selected, "WNBA official CDN"))
    else:
        wnba_meta["parse_ok"] = False
    attempts.append(wnba_meta)

    # 2) ESPN exact-date scoreboard.
    payload, espn_meta = _request_json(
        "ESPN WNBA daily",
        ESPN_SCOREBOARD_URL,
        params={"dates": slate_date.replace("-", ""), "limit": 100},
        timeout=10,
        attempts=2,
    )
    if payload is not None:
        selected, counts, _ = _parse_espn(payload, slate_date, "ESPN WNBA daily")
        espn_meta = _merge_meta(espn_meta, counts)
        espn_meta["parse_ok"] = True
        if selected:
            candidates.append((1, selected, "ESPN WNBA daily"))
    else:
        espn_meta["parse_ok"] = False
    attempts.append(espn_meta)

    # 3) ESPN season-wide scoreboard, independent off-day/date confirmation.
    payload, espn_season_meta = _request_json(
        "ESPN WNBA season",
        ESPN_SCOREBOARD_URL,
        params={"dates": str(year), "limit": 1000},
        timeout=12,
        attempts=2,
    )
    if payload is not None:
        selected, counts, all_rows = _parse_espn(payload, slate_date, "ESPN WNBA season")
        espn_season_meta = _merge_meta(espn_season_meta, counts)
        espn_season_meta["parse_ok"] = True
        if all_rows:
            season_sources_ok += 1
        if selected:
            candidates.append((2, selected, "ESPN WNBA season"))
    else:
        espn_season_meta["parse_ok"] = False
    attempts.append(espn_season_meta)

    signature_groups: dict[tuple[tuple[int, int], ...], list[tuple[int, list[dict[str, Any]], str]]] = {}
    for item in candidates:
        signature_groups.setdefault(_signature(item[1]), []).append(item)

    agreement = 0
    chosen = "NONE"
    confirming: list[str] = []
    games: list[dict[str, Any]] = []
    raw_state = "PROVIDER_FAILURE"

    if signature_groups:
        _, members = max(
            signature_groups.items(),
            key=lambda item: (len(item[1]), -min(x[0] for x in item[1])),
        )
        members.sort(key=lambda x: x[0])
        _, games, chosen = members[0]
        confirming = [x[2] for x in members]
        agreement = len(members)
        raw_state = "VERIFIED" if agreement >= 2 or len(candidates) == 1 else "PROVIDER_CONFLICT"
    elif season_sources_ok:
        raw_state = "VERIFIED_OFF_DAY"

    if raw_state == "VERIFIED":
        verification = "VERIFIED"
    elif raw_state == "VERIFIED_OFF_DAY":
        verification = "NO GAMES"
    elif raw_state == "PROVIDER_CONFLICT":
        verification = "CHECK"
    else:
        verification = "UNAVAILABLE"

    games = _dedupe(games)
    daily_sig = _signature(
        next((rows for _, rows, src in candidates if src == "ESPN WNBA daily"), [])
    )
    chosen_sig = _signature(games)
    espn_confirmed = len(games) if games and daily_sig == chosen_sig else 0

    for row in games:
        row["teams_valid"] = (
            int(row.get("away_team_id") or 0) in _TEAM_BY_ID
            and int(row.get("home_team_id") or 0) in _TEAM_BY_ID
        )
        row["espn_confirmed"] = bool(espn_confirmed)

    teams = {
        int(tid)
        for row in games
        for tid in (row.get("away_team_id"), row.get("home_team_id"))
        if int(tid or 0) in _TEAM_BY_ID
    }

    return {
        "slate_date": slate_date,
        "verification": verification,
        "diagnostic_state": raw_state,
        "source": chosen,
        "games": games,
        "games_found": len(games),
        "teams_validated": len(teams),
        "wnba_games": int(wnba_meta.get("selected_games") or 0),
        "espn_games": int(espn_meta.get("selected_games") or 0),
        "espn_season_games": int(espn_season_meta.get("selected_games") or 0),
        "espn_confirmed": espn_confirmed,
        "invalid_team_rows": sum(1 for row in games if not row.get("teams_valid")),
        "source_agreement": agreement,
        "confirming_sources": confirming,
        "candidate_slates": {
            "|".join(f"{away}-{home}" for away, home in sig): [x[2] for x in members]
            for sig, members in signature_groups.items()
        },
        "season_sources_ok": season_sources_ok,
        "attempts": attempts,
        "wnba_meta": wnba_meta,
        "espn_meta": espn_meta,
        "espn_season_meta": espn_season_meta,
        "checked_at_et": datetime.now(_ET).strftime("%Y-%m-%d %I:%M:%S %p ET"),
    }


__all__ = [
    "load_verified_wnba_slate",
    "WNBA_TEAMS_2026",
    "WNBA_SCHEDULE_URL",
    "ESPN_SCOREBOARD_URL",
]
