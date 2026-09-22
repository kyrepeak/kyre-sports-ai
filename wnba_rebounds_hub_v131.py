"""WNBA Rebounds V1.3.1 — Step 4 calibration / sparse-history repair.

Keeps V1.3 model semantics intact, but makes the OREB/DREB verification gate
robust to players who did not appear in three of their team's last ten games.
We search a wider *verification reservoir* of recent completed team games and
then retain only each player's 10 most recent component-valid appearances.

No sportsbook data, rebound projection, or Monte Carlo is introduced here.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

import wnba_rebounds_hub_v13 as base

MODEL_VERSION = "WNBA REBOUNDS V1.3.1 • STEP 4 CALIBRATED OREB/DREB ROLE"


def _num(value, default=np.nan):
    try:
        x = float(value)
        return default if pd.isna(x) else x
    except Exception:
        return default


@st.cache_data(ttl=1800, show_spinner=False, max_entries=64)
def _recent_rebound_role_calibrated(day_str: str, team_id: int, player_ids: tuple[int, ...]):
    """Player-last-10 OREB/DREB sample from a wider recent team-game reservoir.

    V1.3 used exactly the team's last 10 games as both the fetch window and the
    player sample. That can falsely fail a healthy rotation player who missed
    several team games. V1.3.1 scans up to 24 recent completed team games, then
    keeps only each player's 10 most recent played, component-valid games.
    """
    players = base.players
    day = pd.to_datetime(day_str).strftime("%Y-%m-%d")
    tid = int(team_id or 0)
    ids = tuple(sorted({int(x) for x in player_ids if int(x) > 0}))
    if not tid or not ids:
        return {}, 0, 0

    try:
        season = players._espn_season_schedule(pd.to_datetime(day).year)
    except Exception:
        season = pd.DataFrame()
    if season is None or season.empty:
        return {}, 0, 0

    before = pd.to_datetime(season.get("game_date"), errors="coerce") < pd.to_datetime(day)
    final = season.get("status", pd.Series("", index=season.index)).astype(str).str.upper().eq("FINAL")
    team_mask = (
        pd.to_numeric(season.get("away_team_id"), errors="coerce").eq(tid)
        | pd.to_numeric(season.get("home_team_id"), errors="coerce").eq(tid)
    )
    games = season.loc[before & final & team_mask].copy()
    if games.empty:
        return {}, 0, 0
    games["_d"] = pd.to_datetime(games["game_date"], errors="coerce")
    games = games.sort_values("_d", ascending=False).drop_duplicates("game_id").head(24)

    game_frames = []
    valid_component_games = 0
    for _, game in games.iterrows():
        gid = str(game.get("game_id") or "")
        gdate = str(game.get("game_date") or "")
        if not gid:
            continue
        frame = base._game_rebound_components(gid, gdate, tid)
        if frame.empty:
            continue
        if frame[["OREB", "DREB"]].notna().any(axis=None):
            valid_component_games += 1
        game_frames.append(frame)

    if not game_frames:
        return {}, len(games), 0

    hist = pd.concat(game_frames, ignore_index=True)
    hist["_d"] = pd.to_datetime(hist.get("GAME_DATE"), errors="coerce")

    result = {}
    for pid in ids:
        p = hist.loc[pd.to_numeric(hist["PLAYER_ID"], errors="coerce").eq(pid)].copy()
        p = p[p["MIN"].fillna(0).gt(0)].copy()
        p = p[p["OREB"].notna() & p["DREB"].notna()].sort_values("_d", ascending=False).head(10)

        mins = float(pd.to_numeric(p["MIN"], errors="coerce").fillna(0).sum())
        oreb = float(pd.to_numeric(p["OREB"], errors="coerce").fillna(0).sum())
        dreb = float(pd.to_numeric(p["DREB"], errors="coerce").fillna(0).sum())
        reb = oreb + dreb
        result[pid] = {
            "gp": int(len(p)),
            "minutes": mins,
            "oreb": oreb,
            "dreb": dreb,
            "reb": reb,
            "oreb36": (36.0 * oreb / mins) if mins > 0 else np.nan,
            "dreb36": (36.0 * dreb / mins) if mins > 0 else np.nan,
            "reb36": (36.0 * reb / mins) if mins > 0 else np.nan,
            "oreb_share": (oreb / reb) if reb > 0 else np.nan,
            "dreb_share": (dreb / reb) if reb > 0 else np.nan,
            "reb_per_min": (reb / mins) if mins > 0 else np.nan,
        }
    return result, len(games), valid_component_games


# Patch only the Step-4 history resolver. V1.3's build/render gates remain intact.
base._recent_rebound_role = _recent_rebound_role_calibrated


def _render_sparse_diagnostics():
    rows = st.session_state.get("wnba_rebounds_step4_players") or []
    if not rows or st.session_state.get("wnba_rebounds_step4_ready"):
        return
    frame = pd.DataFrame(rows)
    if frame.empty:
        return
    frame["PROJ_MIN"] = pd.to_numeric(frame.get("PROJ_MIN"), errors="coerce").fillna(0.0)
    frame["REB_ROLE_GP"] = pd.to_numeric(frame.get("REB_ROLE_GP"), errors="coerce").fillna(0).astype(int)
    fail = frame[
        frame["PROJ_MIN"].ge(5.0)
        & (
            frame["REB_ROLE_GP"].lt(3)
            | pd.to_numeric(frame.get("OREB36"), errors="coerce").isna()
            | pd.to_numeric(frame.get("DREB36"), errors="coerce").isna()
        )
    ].copy()
    if fail.empty:
        return
    fail["Player"] = fail.get("PLAYER_NAME", "Player")
    fail["Team"] = fail.get("TEAM_NAME", "")
    fail["Proj MIN"] = fail["PROJ_MIN"].round(1)
    fail["Verified GP"] = fail["REB_ROLE_GP"]
    fail["Reason"] = np.where(
        fail["REB_ROLE_GP"].lt(3),
        "Fewer than 3 played OREB/DREB-valid games found after 24-team-game reservoir",
        "Missing verified OREB or DREB component",
    )
    st.warning("🔎 Step-4 sparse-history diagnostic — no player is silently guessed or bypassed.")
    st.dataframe(
        fail[["Player", "Team", "Proj MIN", "Verified GP", "Reason"]],
        hide_index=True,
        use_container_width=True,
    )


def render_wnba_rebounds_hub(*args, **kwargs):
    # Refresh display copy without changing downstream model math.
    original = base.MODEL_VERSION
    base.MODEL_VERSION = MODEL_VERSION
    try:
        result = base.render_wnba_rebounds_hub(*args, **kwargs)
        _render_sparse_diagnostics()
        return result
    finally:
        base.MODEL_VERSION = original
