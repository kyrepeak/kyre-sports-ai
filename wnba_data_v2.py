"""WNBA PRA V2 official-data foundation.

Primary data source: stats.wnba.com. Descriptive official data is kept separate
from projection logic. If an official endpoint is unavailable, callers get an
empty frame/error state rather than fabricated data.
"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests
import streamlit as st

ET = ZoneInfo("America/New_York")
WNBA_STATS = "https://stats.wnba.com/stats"
LEAGUE_ID = "10"
TEAM_LOGO = "https://cdn.nba.com/logos/wnba/{team_id}/global/L/logo.svg"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.wnba.com",
    "Referer": "https://www.wnba.com/",
    "Connection": "keep-alive",
}


def current_season() -> int:
    return datetime.now(ET).year


def _request(endpoint: str, params: dict[str, Any], timeout: int = 22) -> dict:
    response = requests.get(
        f"{WNBA_STATS}/{endpoint}", params=params, headers=HEADERS, timeout=timeout
    )
    response.raise_for_status()
    return response.json()


def _frame_from_result(payload: dict, preferred: str | None = None) -> pd.DataFrame:
    sets = payload.get("resultSets")
    if sets is None:
        sets = payload.get("resultSet")
    if not sets:
        return pd.DataFrame()
    if isinstance(sets, dict):
        return pd.DataFrame(sets.get("rowSet") or [], columns=sets.get("headers") or [])
    chosen = None
    if preferred:
        for item in sets:
            if str(item.get("name", "")).lower() == preferred.lower():
                chosen = item
                break
    chosen = chosen or sets[0]
    return pd.DataFrame(chosen.get("rowSet") or [], columns=chosen.get("headers") or [])


def _to_et_display(value: Any) -> str:
    if value in (None, "", "TBD"):
        return "TBD"
    try:
        ts = pd.to_datetime(value, utc=True)
        return ts.tz_convert(ET).strftime("%-I:%M %p ET")
    except Exception:
        try:
            ts = pd.to_datetime(value)
            if getattr(ts, "tzinfo", None) is None:
                ts = ts.tz_localize(ET)
            else:
                ts = ts.tz_convert(ET)
            return ts.strftime("%-I:%M %p ET")
        except Exception:
            return str(value)


def _safe_date(value: Any) -> str | None:
    try:
        return pd.to_datetime(value).strftime("%Y-%m-%d")
    except Exception:
        return None


def _team_name(team: dict) -> str:
    city = str(team.get("teamCity") or "").strip()
    name = str(team.get("teamName") or "").strip()
    full = " ".join(x for x in (city, name) if x).strip()
    return full or str(team.get("teamTricode") or team.get("teamName") or "Unknown")


def _status_bucket(status_code: Any, status_text: Any = "") -> str:
    try:
        code = int(status_code)
    except Exception:
        code = 0
    if code == 1:
        return "UPCOMING"
    if code == 2:
        return "LIVE"
    if code == 3:
        return "FINAL"
    text = str(status_text or "").lower()
    if "final" in text:
        return "FINAL"
    if any(x in text for x in ("q1", "q2", "q3", "q4", "half", "ot", "live")):
        return "LIVE"
    return "UPCOMING"


@st.cache_data(ttl=1800, show_spinner=False)
def official_schedule(season: int | None = None) -> pd.DataFrame:
    """Official WNBA season schedule via the WNBA Stats schedule endpoint."""
    season = int(season or current_season())
    payload = _request("scheduleleaguev2", {"LeagueID": LEAGUE_ID, "SeasonYear": str(season)})
    league = payload.get("leagueSchedule") or payload.get("LeagueSchedule") or {}
    dates = league.get("gameDates") or league.get("GameDates") or []
    rows: list[dict[str, Any]] = []
    for block in dates:
        block_date = block.get("gameDate") or block.get("gameDateEst") or block.get("gameDateUTC")
        for game in block.get("games", []) or []:
            home = game.get("homeTeam") or {}
            away = game.get("awayTeam") or {}
            raw_dt = game.get("gameDateTimeUTC") or game.get("gameDateTimeEst") or game.get("gameDateTime")
            rows.append({
                "game_id": str(game.get("gameId") or game.get("gameID") or ""),
                "game_date": _safe_date(raw_dt) or _safe_date(block_date),
                "first_tip_et": _to_et_display(raw_dt),
                "status": _status_bucket(game.get("gameStatus"), game.get("gameStatusText")),
                "status_text": str(game.get("gameStatusText") or ""),
                "away_team_id": int(away.get("teamId") or 0),
                "away_team": _team_name(away),
                "away_tricode": str(away.get("teamTricode") or ""),
                "home_team_id": int(home.get("teamId") or 0),
                "home_team": _team_name(home),
                "home_tricode": str(home.get("teamTricode") or ""),
                "venue": str(game.get("arenaName") or game.get("arenaCity") or "Venue TBD"),
                "source": "WNBA Stats",
            })
    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame = frame.drop_duplicates(subset=["game_id"], keep="last")
        frame = frame.sort_values(["game_date", "first_tip_et"], na_position="last")
    return frame


@st.cache_data(ttl=600, show_spinner=False)
def schedule_for_date(day: str | date) -> pd.DataFrame:
    day_str = pd.to_datetime(day).strftime("%Y-%m-%d")
    schedule = official_schedule(pd.to_datetime(day).year)
    if schedule.empty:
        return schedule
    return schedule[schedule["game_date"].eq(day_str)].reset_index(drop=True)


def _player_params(season: int, last_n: int = 0) -> dict[str, Any]:
    return {
        "College": "", "Conference": "", "Country": "", "DateFrom": "", "DateTo": "",
        "Division": "", "DraftPick": "", "DraftYear": "", "GameScope": "", "GameSegment": "",
        "Height": "", "LastNGames": int(last_n), "LeagueID": LEAGUE_ID, "Location": "",
        "MeasureType": "Base", "Month": 0, "OpponentTeamID": 0, "Outcome": "", "PORound": 0,
        "PaceAdjust": "N", "PerMode": "PerGame", "Period": 0, "PlayerExperience": "",
        "PlayerPosition": "", "PlusMinus": "N", "Rank": "N", "Season": str(season),
        "SeasonSegment": "", "SeasonType": "Regular Season", "ShotClockRange": "",
        "StarterBench": "", "TeamID": 0, "VsConference": "", "VsDivision": "", "Weight": "",
    }


@st.cache_data(ttl=900, show_spinner=False)
def official_player_stats(season: int | None = None, last_n: int = 0) -> pd.DataFrame:
    season = int(season or current_season())
    payload = _request("leaguedashplayerstats", _player_params(season, last_n))
    df = _frame_from_result(payload)
    if df.empty:
        return df
    df.columns = [str(c).upper() for c in df.columns]
    for col in ("PLAYER_ID", "TEAM_ID", "GP", "W", "L", "MIN", "PTS", "REB", "AST", "STL", "BLK", "TOV", "FG_PCT", "FG3_PCT", "FT_PCT", "PLUS_MINUS"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


@st.cache_data(ttl=900, show_spinner=False)
def player_form_table(season: int | None = None) -> pd.DataFrame:
    season = int(season or current_season())
    base = official_player_stats(season, 0)
    if base.empty:
        return base
    out = base.copy()
    for label, n in (("L10", 10), ("L5", 5)):
        try:
            recent = official_player_stats(season, n)
        except Exception:
            recent = pd.DataFrame()
        if recent.empty or "PLAYER_ID" not in recent.columns:
            continue
        keep = [c for c in ("PLAYER_ID", "GP", "MIN", "PTS", "REB", "AST") if c in recent.columns]
        recent = recent[keep].copy().rename(columns={c: f"{label}_{c}" for c in keep if c != "PLAYER_ID"})
        out = out.merge(recent, on="PLAYER_ID", how="left")
    return out


@st.cache_data(ttl=1800, show_spinner=False)
def official_roster(team_id: int, season: int | None = None) -> pd.DataFrame:
    season = int(season or current_season())
    payload = _request("commonteamroster", {"LeagueID": LEAGUE_ID, "Season": str(season), "TeamID": int(team_id)})
    df = _frame_from_result(payload, "CommonTeamRoster")
    if df.empty:
        return df
    df.columns = [str(c).upper() for c in df.columns]
    return df


@st.cache_data(ttl=900, show_spinner=False)
def player_game_log(player_id: int, season: int | None = None) -> pd.DataFrame:
    season = int(season or current_season())
    payload = _request("playergamelog", {"LeagueID": LEAGUE_ID, "PlayerID": int(player_id), "Season": str(season), "SeasonType": "Regular Season"})
    df = _frame_from_result(payload)
    if df.empty:
        return df
    df.columns = [str(c).upper() for c in df.columns]
    for col in ("MIN", "PTS", "REB", "AST", "FGA", "FGM", "FG3A", "FG3M", "FTA", "FTM"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "GAME_DATE" in df.columns:
        df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"], errors="coerce")
        df = df.sort_values("GAME_DATE", ascending=False)
    return df.reset_index(drop=True)


def empirical_profile(log: pd.DataFrame) -> dict[str, Any]:
    if log is None or log.empty:
        return {}
    cols = [c for c in ("PTS", "REB", "AST") if c in log.columns]
    if len(cols) < 3:
        return {}
    clean = log[cols].apply(pd.to_numeric, errors="coerce").dropna()
    if clean.empty:
        return {}
    l10, l5 = clean.head(10), clean.head(5)
    corr = clean.corr().fillna(0)
    std = clean.std(ddof=1).fillna(0)
    return {
        "games": len(clean),
        "pts": float(clean["PTS"].mean()), "reb": float(clean["REB"].mean()), "ast": float(clean["AST"].mean()),
        "pra": float((clean["PTS"] + clean["REB"] + clean["AST"]).mean()),
        "sd_pts": float(max(std["PTS"], 1.0)), "sd_reb": float(max(std["REB"], .7)), "sd_ast": float(max(std["AST"], .7)),
        "l10_pts": float(l10["PTS"].mean()), "l10_reb": float(l10["REB"].mean()), "l10_ast": float(l10["AST"].mean()),
        "l10_pra": float((l10["PTS"] + l10["REB"] + l10["AST"]).mean()),
        "l5_pts": float(l5["PTS"].mean()), "l5_reb": float(l5["REB"].mean()), "l5_ast": float(l5["AST"].mean()),
        "l5_pra": float((l5["PTS"] + l5["REB"] + l5["AST"]).mean()),
        "corr_pr": float(np.clip(corr.loc["PTS", "REB"], -.75, .75)),
        "corr_pa": float(np.clip(corr.loc["PTS", "AST"], -.75, .75)),
        "corr_ra": float(np.clip(corr.loc["REB", "AST"], -.75, .75)),
    }


def team_player_pool(stats: pd.DataFrame, team_id: int) -> pd.DataFrame:
    if stats is None or stats.empty or "TEAM_ID" not in stats.columns:
        return pd.DataFrame()
    return stats[pd.to_numeric(stats["TEAM_ID"], errors="coerce").eq(int(team_id))].copy()


def slate_player_pool(schedule: pd.DataFrame, stats: pd.DataFrame) -> pd.DataFrame:
    if schedule is None or schedule.empty or stats is None or stats.empty:
        return pd.DataFrame()
    team_ids = set(pd.to_numeric(pd.concat([schedule["away_team_id"], schedule["home_team_id"]]), errors="coerce").dropna().astype(int))
    pool = stats[pd.to_numeric(stats["TEAM_ID"], errors="coerce").isin(team_ids)].copy()
    if pool.empty:
        return pool
    for prefix in ("", "L10_", "L5_"):
        needed = [f"{prefix}{x}" for x in ("PTS", "REB", "AST")]
        if all(c in pool.columns for c in needed):
            pool[f"{prefix}PRA"] = pool[needed].sum(axis=1)
    return pool


def game_for_team(schedule: pd.DataFrame, team_id: int) -> dict[str, Any] | None:
    if schedule is None or schedule.empty:
        return None
    mask = schedule["away_team_id"].eq(int(team_id)) | schedule["home_team_id"].eq(int(team_id))
    rows = schedule[mask]
    if rows.empty:
        return None
    row = rows.iloc[0].to_dict()
    if int(row.get("away_team_id", 0)) == int(team_id):
        row["opponent"] = row.get("home_team")
        row["opponent_team_id"] = row.get("home_team_id")
        row["side"] = "away"
    else:
        row["opponent"] = row.get("away_team")
        row["opponent_team_id"] = row.get("away_team_id")
        row["side"] = "home"
    return row


def logo_url(team_id: int | float | None) -> str:
    try:
        return TEAM_LOGO.format(team_id=int(team_id))
    except Exception:
        return ""


def data_health(schedule: pd.DataFrame | None, stats: pd.DataFrame | None) -> dict[str, str]:
    return {
        "WNBA.com schedule": "CONNECTED" if schedule is not None and not schedule.empty else "CHECK",
        "WNBA.com player stats": "CONNECTED" if stats is not None and not stats.empty else "CHECK",
        "Official rosters": "ON DEMAND",
        "Confirmed starters": "PENDING",
        "Injury status": "PENDING",
    }
