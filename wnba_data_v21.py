"""WNBA PRA V2.1 data transport hotfix.

WNBA retired the scheduleleaguev2 stats endpoint in 2026. The current-season
schedule is now served from the official public WNBA CDN. This wrapper also
puts LeagueID first in WNBA Stats query parameters before reusing the V2 data
helpers.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import pandas as pd
import requests
import streamlit as st

import wnba_data_v2 as base

SCHEDULE_CDN = "https://cdn.wnba.com/static/json/staticData/scheduleLeagueV2.json"


def _player_params(season: int, last_n: int = 0) -> dict[str, Any]:
    # Keep LeagueID first. The 2026 WNBA Stats edge has been sensitive to
    # query-string ordering on some endpoints.
    return {
        "LeagueID": base.LEAGUE_ID,
        "College": "", "Conference": "", "Country": "", "DateFrom": "", "DateTo": "",
        "Division": "", "DraftPick": "", "DraftYear": "", "GameScope": "", "GameSegment": "",
        "Height": "", "LastNGames": int(last_n), "Location": "", "MeasureType": "Base",
        "Month": 0, "OpponentTeamID": 0, "Outcome": "", "PORound": 0, "PaceAdjust": "N",
        "PerMode": "PerGame", "Period": 0, "PlayerExperience": "", "PlayerPosition": "",
        "PlusMinus": "N", "Rank": "N", "Season": str(season), "SeasonSegment": "",
        "SeasonType": "Regular Season", "ShotClockRange": "", "StarterBench": "", "TeamID": 0,
        "VsConference": "", "VsDivision": "", "Weight": "",
    }


@st.cache_data(ttl=1800, show_spinner=False)
def official_schedule(season: int | None = None) -> pd.DataFrame:
    season = int(season or base.current_season())
    if season != base.current_season():
        return pd.DataFrame()
    response = requests.get(SCHEDULE_CDN, headers=base.HEADERS, timeout=22)
    response.raise_for_status()
    payload = response.json()
    league = payload.get("leagueSchedule") or {}
    rows = []
    for block in league.get("gameDates", []) or []:
        block_date = block.get("gameDate")
        for game in block.get("games", []) or []:
            home = game.get("homeTeam") or {}
            away = game.get("awayTeam") or {}
            # gameDateTimeEst contains the actual tip time; gameDateEst can be midnight.
            raw_et = game.get("gameDateTimeEst") or game.get("gameDateTimeUTC") or game.get("gameDateTime")
            game_date = base._safe_date(raw_et) or base._safe_date(block_date)
            rows.append({
                "game_id": str(game.get("gameId") or game.get("gameID") or ""),
                "game_date": game_date,
                "first_tip_et": base._to_et_display(raw_et),
                "status": base._status_bucket(game.get("gameStatus"), game.get("gameStatusText")),
                "status_text": str(game.get("gameStatusText") or ""),
                "away_team_id": int(away.get("teamId") or 0),
                "away_team": base._team_name(away),
                "away_tricode": str(away.get("teamTricode") or ""),
                "home_team_id": int(home.get("teamId") or 0),
                "home_team": base._team_name(home),
                "home_tricode": str(home.get("teamTricode") or ""),
                "venue": str(game.get("arenaName") or game.get("arenaCity") or "Venue TBD"),
                "source": "WNBA official CDN",
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


@st.cache_data(ttl=900, show_spinner=False)
def official_player_stats(season: int | None = None, last_n: int = 0) -> pd.DataFrame:
    season = int(season or base.current_season())
    payload = base._request("leaguedashplayerstats", _player_params(season, last_n))
    df = base._frame_from_result(payload)
    if df.empty:
        return df
    df.columns = [str(c).upper() for c in df.columns]
    for col in ("PLAYER_ID", "TEAM_ID", "GP", "W", "L", "MIN", "PTS", "REB", "AST", "STL", "BLK", "TOV", "FG_PCT", "FG3_PCT", "FT_PCT", "PLUS_MINUS"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


# Patch the V2 module globals so its cached form-table helper resolves the fixed
# transport functions when it executes.
base.official_schedule = official_schedule
base.schedule_for_date = schedule_for_date
base._player_params = _player_params
base.official_player_stats = official_player_stats

current_season = base.current_season
data_health = base.data_health
empirical_profile = base.empirical_profile
game_for_team = base.game_for_team
logo_url = base.logo_url
official_roster = base.official_roster
player_form_table = base.player_form_table
player_game_log = base.player_game_log
slate_player_pool = base.slate_player_pool
team_player_pool = base.team_player_pool
