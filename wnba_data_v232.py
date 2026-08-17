"""WNBA PRA V2.3.2 resilient data transport.

Primary path stays WNBA-owned data: the public WNBA CDN for schedule and
WNBA Stats for player production. If Streamlit Cloud receives an empty/non-JSON
WNBA CDN response, the selected-date schedule can fall back to ESPN's WNBA
scoreboard. Player stats retry the same LeagueID=10 request through the NBA
Stats host before returning empty. Every schedule/stat row is still guarded to
WNBA team IDs so another league can never bleed into the PRA page.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from zoneinfo import ZoneInfo

import pandas as pd
import requests
import streamlit as st

import wnba_data_v21 as transport
import wnba_data_v22 as guarded

ET = ZoneInfo("America/New_York")
WNBA_CDN = "https://cdn.wnba.com/static/json/staticData/scheduleLeagueV2.json"
ESPN_SCOREBOARD = "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba/scoreboard"
PLAYER_HOSTS = (
    "https://stats.wnba.com/stats/leaguedashplayerstats",
    "https://stats.nba.com/stats/leaguedashplayerstats",
)

# Official WNBA team IDs. Expansion IDs are confirmed by WNBA team pages.
TEAM_IDS = {
    "ATL": 1611661330, "ATLANTA DREAM": 1611661330,
    "CHI": 1611661329, "CHICAGO SKY": 1611661329,
    "CON": 1611661323, "CONNECTICUT SUN": 1611661323,
    "DAL": 1611661321, "DALLAS WINGS": 1611661321,
    "IND": 1611661325, "INDIANA FEVER": 1611661325,
    "LV": 1611661319, "LVA": 1611661319, "LAS VEGAS ACES": 1611661319,
    "LA": 1611661320, "LAS": 1611661320, "LOS ANGELES SPARKS": 1611661320,
    "MIN": 1611661324, "MINNESOTA LYNX": 1611661324,
    "NY": 1611661313, "NYL": 1611661313, "NEW YORK LIBERTY": 1611661313,
    "PHX": 1611661317, "PHO": 1611661317, "PHOENIX MERCURY": 1611661317,
    "SEA": 1611661328, "SEATTLE STORM": 1611661328,
    "WSH": 1611661322, "WAS": 1611661322, "WASHINGTON MYSTICS": 1611661322,
    "GS": 1611661331, "GSV": 1611661331, "GOLDEN STATE VALKYRIES": 1611661331,
    "POR": 1611661327, "PDX": 1611661327, "PORTLAND FIRE": 1611661327,
    "TOR": 1611661332, "TORONTO TEMPO": 1611661332,
}


def _json_response(url: str, *, params=None, headers=None, timeout=8):
    response = requests.get(url, params=params, headers=headers, timeout=timeout)
    response.raise_for_status()
    text = (response.text or "").lstrip()
    if not text or not text.startswith(("{", "[")):
        raise ValueError(f"non-JSON response from {url}")
    return response.json()


def _tip_et(value) -> str:
    if not value:
        return "TBD"
    try:
        ts = pd.to_datetime(value, utc=True)
        return ts.tz_convert(ET).strftime("%-I:%M %p ET")
    except Exception:
        return str(value)


def _status_bucket(state: str, description: str = "") -> str:
    s = str(state or "").lower()
    d = str(description or "").lower()
    if s in ("post", "final") or "final" in d:
        return "FINAL"
    if s in ("in", "live") or any(x in d for x in ("quarter", "half", "ot", "end of")):
        return "LIVE"
    return "UPCOMING"


def _team_id(team: dict) -> int:
    keys = [
        str(team.get("abbreviation") or "").upper(),
        str(team.get("shortDisplayName") or "").upper(),
        str(team.get("displayName") or "").upper(),
        str(team.get("name") or "").upper(),
    ]
    for key in keys:
        if key in TEAM_IDS:
            return TEAM_IDS[key]
    return 0


def _wnba_cdn_schedule() -> pd.DataFrame:
    # Public CDN should not need stats-site Origin/Referer headers. Two attempts
    # avoid a transient empty edge-cache response.
    last_error = None
    for attempt in range(2):
        try:
            params = {"_": pd.Timestamp.utcnow().strftime("%Y%m%d%H%M")} if attempt else None
            payload = _json_response(
                WNBA_CDN,
                params=params,
                headers={"User-Agent": transport.base.HEADERS.get("User-Agent", "Mozilla/5.0"), "Accept": "application/json"},
                timeout=8,
            )
            league = payload.get("leagueSchedule") or {}
            rows = []
            for block in league.get("gameDates", []) or []:
                block_date = block.get("gameDate")
                for game in block.get("games", []) or []:
                    away, home = game.get("awayTeam") or {}, game.get("homeTeam") or {}
                    raw_dt = game.get("gameDateTimeUTC") or game.get("gameDateTimeEst") or block_date
                    rows.append({
                        "game_id": str(game.get("gameId") or game.get("gameID") or ""),
                        "game_date": transport.base._safe_date(raw_dt) or transport.base._safe_date(block_date),
                        "first_tip_et": transport._tip_et(game),
                        "status": transport.base._status_bucket(game.get("gameStatus"), game.get("gameStatusText")),
                        "status_text": str(game.get("gameStatusText") or ""),
                        "away_team_id": int(away.get("teamId") or 0),
                        "away_team": transport.base._team_name(away),
                        "away_tricode": str(away.get("teamTricode") or ""),
                        "home_team_id": int(home.get("teamId") or 0),
                        "home_team": transport.base._team_name(home),
                        "home_tricode": str(home.get("teamTricode") or ""),
                        "venue": str(game.get("arenaName") or game.get("arenaCity") or "Venue TBD"),
                        "source": "WNBA official CDN",
                    })
            return guarded._guard_schedule(pd.DataFrame(rows))
        except Exception as exc:
            last_error = exc
    if last_error:
        raise last_error
    return pd.DataFrame()


def _espn_schedule_for_date(day) -> pd.DataFrame:
    day_ts = pd.to_datetime(day)
    payload = _json_response(
        ESPN_SCOREBOARD,
        params={"dates": day_ts.strftime("%Y%m%d"), "limit": 100},
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
        timeout=8,
    )
    rows = []
    for event in payload.get("events", []) or []:
        comps = event.get("competitions") or []
        if not comps:
            continue
        comp = comps[0]
        sides = {}
        for competitor in comp.get("competitors", []) or []:
            sides[str(competitor.get("homeAway") or "").lower()] = competitor
        away_c, home_c = sides.get("away") or {}, sides.get("home") or {}
        away_t, home_t = away_c.get("team") or {}, home_c.get("team") or {}
        away_id, home_id = _team_id(away_t), _team_id(home_t)
        if not guarded._is_wnba_team_id(away_id) or not guarded._is_wnba_team_id(home_id):
            continue
        status = (event.get("status") or {}).get("type") or {}
        venue = (comp.get("venue") or {}).get("fullName") or "Venue TBD"
        raw_dt = event.get("date") or comp.get("date")
        rows.append({
            "game_id": str(event.get("id") or ""),
            "game_date": day_ts.strftime("%Y-%m-%d"),
            "first_tip_et": _tip_et(raw_dt),
            "status": _status_bucket(status.get("state"), status.get("description") or status.get("detail")),
            "status_text": str(status.get("shortDetail") or status.get("detail") or status.get("description") or ""),
            "away_team_id": away_id,
            "away_team": str(away_t.get("displayName") or away_t.get("shortDisplayName") or "Away"),
            "away_tricode": str(away_t.get("abbreviation") or ""),
            "home_team_id": home_id,
            "home_team": str(home_t.get("displayName") or home_t.get("shortDisplayName") or "Home"),
            "home_tricode": str(home_t.get("abbreviation") or ""),
            "venue": str(venue),
            "source": "ESPN WNBA schedule fallback",
        })
    return guarded._guard_schedule(pd.DataFrame(rows))


@st.cache_data(ttl=900, show_spinner=False)
def schedule_for_date(day: str | date) -> pd.DataFrame:
    day_str = pd.to_datetime(day).strftime("%Y-%m-%d")
    try:
        schedule = _wnba_cdn_schedule()
        selected = schedule.loc[schedule["game_date"].eq(day_str)].reset_index(drop=True) if not schedule.empty else schedule
        # If the official season feed loaded correctly, an empty selected day is
        # a legitimate off-day and must not be filled from another league.
        if not schedule.empty:
            return selected
    except Exception:
        pass
    try:
        return _espn_schedule_for_date(day_str)
    except Exception:
        return pd.DataFrame(columns=[
            "game_id", "game_date", "first_tip_et", "status", "status_text",
            "away_team_id", "away_team", "away_tricode", "home_team_id",
            "home_team", "home_tricode", "venue", "source",
        ])


def _player_headers(host: str) -> dict:
    is_nba = "stats.nba.com" in host
    origin = "https://www.nba.com" if is_nba else "https://www.wnba.com"
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": origin,
        "Referer": origin + "/",
    }


def _fetch_player_stats(season: int, last_n: int) -> pd.DataFrame:
    params = transport._player_params(int(season), int(last_n))
    for host in PLAYER_HOSTS:
        try:
            payload = _json_response(host, params=params, headers=_player_headers(host), timeout=7)
            df = transport.base._frame_from_result(payload)
            if df.empty:
                continue
            df.columns = [str(c).upper() for c in df.columns]
            for col in (
                "PLAYER_ID", "TEAM_ID", "GP", "W", "L", "MIN", "PTS", "REB", "AST",
                "STL", "BLK", "TOV", "FG_PCT", "FG3_PCT", "FT_PCT", "PLUS_MINUS",
            ):
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            guarded_df = guarded._guard_stats(df)
            if not guarded_df.empty:
                guarded_df["DATA_SOURCE"] = "WNBA Stats" if "wnba.com" in host else "NBA Stats LeagueID=10 fallback"
                return guarded_df
        except Exception:
            continue
    return pd.DataFrame()


@st.cache_data(ttl=900, show_spinner=False)
def _player_form_table_backend(season: int) -> pd.DataFrame:
    results = {}
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(_fetch_player_stats, int(season), n): n for n in (0, 10, 5)}
        for future in as_completed(futures):
            n = futures[future]
            try:
                results[n] = future.result()
            except Exception:
                results[n] = pd.DataFrame()
    base = results.get(0, pd.DataFrame())
    if base.empty:
        return base
    out = base.copy()
    for label, n in (("L10", 10), ("L5", 5)):
        recent = results.get(n, pd.DataFrame())
        if recent.empty or "PLAYER_ID" not in recent.columns:
            continue
        keep = [c for c in ("PLAYER_ID", "GP", "MIN", "PTS", "REB", "AST") if c in recent.columns]
        recent = recent[keep].copy().rename(columns={c: f"{label}_{c}" for c in keep if c != "PLAYER_ID"})
        out = out.merge(recent, on="PLAYER_ID", how="left")
    return guarded._guard_stats(out)


def player_form_table(season: int | None = None) -> pd.DataFrame:
    season = int(season or transport.current_season())
    with st.spinner("🏀 Loading WNBA schedule/player feeds with automatic fallback protection…"):
        return _player_form_table_backend(season)


def data_health(schedule, stats):
    schedule = guarded._guard_schedule(schedule)
    stats = guarded._guard_stats(stats)
    schedule_source = "CHECK"
    if not schedule.empty:
        sources = set(schedule.get("source", pd.Series(dtype=str)).astype(str))
        schedule_source = "CONNECTED • WNBA" if any("WNBA official" in s for s in sources) else "FALLBACK • ESPN WNBA"
    stat_source = "CHECK"
    if not stats.empty:
        sources = set(stats.get("DATA_SOURCE", pd.Series(dtype=str)).astype(str))
        stat_source = "CONNECTED • WNBA" if any(s == "WNBA Stats" for s in sources) else "FALLBACK • NBA Stats L10"
    return {
        "WNBA schedule": schedule_source,
        "WNBA player stats": stat_source,
        "League isolation": "WNBA ONLY",
        "Official rosters": "ON DEMAND",
        "Confirmed starters": "PENDING",
        "Injury status": "PENDING",
    }


current_season = guarded.current_season
empirical_profile = guarded.empirical_profile
game_for_team = guarded.game_for_team
logo_url = guarded.logo_url
official_roster = guarded.official_roster
player_game_log = guarded.player_game_log
slate_player_pool = guarded.slate_player_pool
team_player_pool = guarded.team_player_pool
