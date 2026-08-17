"""WNBA PRA V2.2 data guard.

Hard-isolates the WNBA data layer from NBA/MLB rows. The public WNBA schedule
CDN remains the schedule source; WNBA Stats player endpoints are accepted only
when team ids use the WNBA 161166... namespace. Bad/mixed league responses are
filtered to empty instead of leaking another league into the WNBA UI.
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

import wnba_data_v21 as transport
import wnba_data_v2 as core

WNBA_TEAM_ID_PREFIX = "161166"


def _is_wnba_team_id(value) -> bool:
    try:
        return str(int(float(value))).startswith(WNBA_TEAM_ID_PREFIX)
    except Exception:
        return False


def _guard_schedule(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame(columns=getattr(frame, "columns", None))
    out = frame.copy()
    if not {"away_team_id", "home_team_id"}.issubset(out.columns):
        return pd.DataFrame(columns=out.columns)
    mask = out["away_team_id"].map(_is_wnba_team_id) & out["home_team_id"].map(_is_wnba_team_id)
    out = out.loc[mask].copy()
    return out.reset_index(drop=True)


def _guard_stats(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame(columns=getattr(frame, "columns", None))
    out = frame.copy()
    if "TEAM_ID" not in out.columns:
        return pd.DataFrame(columns=out.columns)
    out = out.loc[out["TEAM_ID"].map(_is_wnba_team_id)].copy()
    return out.reset_index(drop=True)


@st.cache_data(ttl=1800, show_spinner=False)
def official_schedule(season: int | None = None) -> pd.DataFrame:
    return _guard_schedule(transport.official_schedule(season))


@st.cache_data(ttl=600, show_spinner=False)
def schedule_for_date(day: str | date) -> pd.DataFrame:
    day_str = pd.to_datetime(day).strftime("%Y-%m-%d")
    schedule = official_schedule(pd.to_datetime(day).year)
    if schedule.empty:
        return schedule
    return schedule.loc[schedule["game_date"].eq(day_str)].reset_index(drop=True)


@st.cache_data(ttl=900, show_spinner=False)
def official_player_stats(season: int | None = None, last_n: int = 0) -> pd.DataFrame:
    return _guard_stats(transport.official_player_stats(season, last_n))


@st.cache_data(ttl=900, show_spinner=False)
def player_form_table(season: int | None = None) -> pd.DataFrame:
    season = int(season or transport.current_season())
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
        recent = recent[keep].copy().rename(
            columns={c: f"{label}_{c}" for c in keep if c != "PLAYER_ID"}
        )
        out = out.merge(recent, on="PLAYER_ID", how="left")
    return _guard_stats(out)


@st.cache_data(ttl=1800, show_spinner=False)
def official_roster(team_id: int, season: int | None = None) -> pd.DataFrame:
    if not _is_wnba_team_id(team_id):
        return pd.DataFrame()
    return transport.official_roster(int(team_id), season)


@st.cache_data(ttl=900, show_spinner=False)
def player_game_log(player_id: int, season: int | None = None) -> pd.DataFrame:
    return transport.player_game_log(player_id, season)


def team_player_pool(stats: pd.DataFrame, team_id: int) -> pd.DataFrame:
    if not _is_wnba_team_id(team_id):
        return pd.DataFrame()
    return core.team_player_pool(_guard_stats(stats), int(team_id))


def slate_player_pool(schedule: pd.DataFrame, stats: pd.DataFrame) -> pd.DataFrame:
    return core.slate_player_pool(_guard_schedule(schedule), _guard_stats(stats))


def game_for_team(schedule: pd.DataFrame, team_id: int):
    if not _is_wnba_team_id(team_id):
        return None
    return core.game_for_team(_guard_schedule(schedule), int(team_id))


def logo_url(team_id):
    if not _is_wnba_team_id(team_id):
        return ""
    return transport.logo_url(team_id)


def data_health(schedule, stats):
    guarded_schedule = _guard_schedule(schedule)
    guarded_stats = _guard_stats(stats)
    return {
        "WNBA schedule": "CONNECTED" if not guarded_schedule.empty else "CHECK",
        "WNBA player stats": "CONNECTED" if not guarded_stats.empty else "CHECK",
        "League isolation": "WNBA ONLY",
        "Official rosters": "ON DEMAND",
        "Confirmed starters": "PENDING",
        "Injury status": "PENDING",
    }


current_season = transport.current_season
empirical_profile = transport.empirical_profile
