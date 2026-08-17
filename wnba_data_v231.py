"""WNBA PRA V2.3.1 fast player-form transport.

Runs season, L10 and L5 WNBA player-stat requests in parallel with bounded
timeouts so the PRA page cannot sit blank for ~60 seconds on a cold cache.
All returned rows still pass the V2.2 WNBA-only team-id guard.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd
import streamlit as st

import wnba_data_v21 as transport
import wnba_data_v22 as guarded


def _fetch_one(season: int, last_n: int) -> pd.DataFrame:
    try:
        payload = transport.base._request(
            "leaguedashplayerstats",
            transport._player_params(int(season), int(last_n)),
            timeout=8,
        )
        df = transport.base._frame_from_result(payload)
        if df.empty:
            return df
        df.columns = [str(c).upper() for c in df.columns]
        for col in (
            "PLAYER_ID", "TEAM_ID", "GP", "W", "L", "MIN", "PTS", "REB", "AST",
            "STL", "BLK", "TOV", "FG_PCT", "FG3_PCT", "FT_PCT", "PLUS_MINUS",
        ):
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return guarded._guard_stats(df)
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=900, show_spinner=False)
def _player_form_table_backend(season: int) -> pd.DataFrame:
    season = int(season)
    requests = {0: "SEASON", 10: "L10", 5: "L5"}
    results: dict[int, pd.DataFrame] = {}

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(_fetch_one, season, n): n for n in requests}
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
        recent = recent[keep].copy().rename(
            columns={c: f"{label}_{c}" for c in keep if c != "PLAYER_ID"}
        )
        out = out.merge(recent, on="PLAYER_ID", how="left")

    return guarded._guard_stats(out)


def player_form_table(season: int | None = None) -> pd.DataFrame:
    season = int(season or transport.current_season())
    with st.spinner("⚡ Loading WNBA season + Last 10 + Last 5 in parallel…"):
        return _player_form_table_backend(season)


# Re-export the guarded V2.2 helpers so the UI keeps one WNBA-only interface.
current_season = guarded.current_season
data_health = guarded.data_health
empirical_profile = guarded.empirical_profile
game_for_team = guarded.game_for_team
logo_url = guarded.logo_url
official_roster = guarded.official_roster
player_game_log = guarded.player_game_log
schedule_for_date = guarded.schedule_for_date
slate_player_pool = guarded.slate_player_pool
team_player_pool = guarded.team_player_pool
