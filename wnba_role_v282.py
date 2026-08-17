"""WNBA PRA V2.8.2 — hardened Step 5 usage/minutes engine.

This module keeps V2.8/V2.8.1 basketball logic but removes the fragile usage
bridge that could raise AttributeError inside Streamlit. Official Advanced USG%
remains first priority. If it is unavailable, ESPN box-score USG is attempted;
if that path also fails, an explicitly labeled production-role proxy is used so
the page remains operational instead of crashing.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

import wnba_role_v28 as base
import wnba_role_v281 as prior

OUT_STATUSES = base.OUT_STATUSES
UNCERTAIN_STATUSES = base.UNCERTAIN_STATUSES


def _merge_usage_frames(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    season = frames.get("SEASON")
    if season is None or season.empty or "USG_PCT" not in season.columns:
        return pd.DataFrame()
    cols = [c for c in ("PLAYER_ID", "TEAM_ID", "PLAYER_NAME", "USG_PCT") if c in season.columns]
    out = season[cols].copy()
    for label in ("L10", "L5"):
        recent = frames.get(label)
        if recent is None or recent.empty or "USG_PCT" not in recent.columns:
            continue
        keep = [c for c in ("PLAYER_ID", "TEAM_ID", "USG_PCT") if c in recent.columns]
        if len(keep) < 3:
            continue
        r = recent[keep].copy().rename(columns={"USG_PCT": f"{label}_USG_PCT"})
        out = out.merge(r, on=["PLAYER_ID", "TEAM_ID"], how="left")
    for c in ("USG_PCT", "L10_USG_PCT", "L5_USG_PCT"):
        if c not in out.columns:
            out[c] = np.nan
    return out


def _official_usage(season: int):
    """Call the original low-level Advanced Stats fetchers directly."""
    frames, sources = {}, []
    for label, last_n in (("SEASON", 0), ("L10", 10), ("L5", 5)):
        try:
            frame, source = base._advanced_usage_fetch(int(season), int(last_n))
        except Exception:
            frame, source = pd.DataFrame(), "unavailable"
        frames[label] = frame
        if source and source != "unavailable":
            sources.append(source)
    merged = _merge_usage_frames(frames)
    return merged, (" + ".join(dict.fromkeys(sources)) if sources and not merged.empty else "unavailable")


def _production_role_proxy(season: int):
    """Last-resort role proxy; explicitly NOT labeled as official USG%."""
    try:
        stats = base.availability.player_form_table(int(season))
    except Exception:
        stats = pd.DataFrame()
    if stats is None or stats.empty:
        return pd.DataFrame(), "unavailable"
    needed = {"PLAYER_ID", "TEAM_ID", "PLAYER_NAME", "MIN", "PTS", "AST"}
    if not needed.issubset(set(stats.columns)):
        return pd.DataFrame(), "unavailable"
    rows = []
    for tid, team in stats.groupby("TEAM_ID"):
        team = team.copy()
        mins = pd.to_numeric(team["MIN"], errors="coerce").fillna(0).clip(lower=.1)
        pts = pd.to_numeric(team["PTS"], errors="coerce").fillna(0)
        ast = pd.to_numeric(team["AST"], errors="coerce").fillna(0)
        load = (pts + 1.35 * ast) / mins
        med = float(load[load.gt(0)].median()) if load.gt(0).any() else 0.25
        load = load.where(load.gt(0), med).clip(lower=.05)
        # Calibrate to a realistic WNBA role band while preserving within-team rank.
        z = (load - float(load.mean())) / max(float(load.std(ddof=0)), .08)
        proxy = (20.0 + 4.5 * z).clip(8.0, 35.0)
        for idx, r in team.iterrows():
            val = float(proxy.loc[idx])
            rows.append({
                "PLAYER_ID": r.get("PLAYER_ID"),
                "TEAM_ID": r.get("TEAM_ID"),
                "PLAYER_NAME": r.get("PLAYER_NAME"),
                "USG_PCT": val,
                "L10_USG_PCT": val,
                "L5_USG_PCT": val,
            })
    out = pd.DataFrame(rows)
    return out, "Production-role proxy (estimated; not official USG%)"


@st.cache_data(ttl=900, show_spinner=False)
def advanced_usage_table(season: int | None = None):
    season = int(season or base.availability.current_season())

    official, source = _official_usage(season)
    if official is not None and not official.empty:
        return official, source

    # V2.8.1 ESPN possession-based fallback. Any provider/parser failure is
    # contained here so it can never take down the PRA page.
    try:
        day_str = base._day_str()
        espn = prior._espn_usage_fallback(season, day_str)
        if espn is not None and not espn.empty:
            return espn, "ESPN WNBA box-score estimated USG%"
    except Exception:
        pass

    return _production_role_proxy(season)


# Use the safer minute-cap allocator from V2.8.1.
_redistribute_team_minutes = prior._redistribute_team_minutes

# Patch the V2.8 module globals used dynamically by its projection functions.
base.advanced_usage_table = advanced_usage_table
base._redistribute_team_minutes = _redistribute_team_minutes

role_projection_for_game = base.role_projection_for_game


def role_diagnostics(day):
    """Never allow a provider-layer exception to crash the page header."""
    try:
        # Clear only the old role diagnostic cache so it recomputes with the
        # V2.8.2 patched usage/minute functions.
        try:
            base._role_diag_for_day.clear()
        except Exception:
            pass
        return base.role_diagnostics(day)
    except Exception as exc:
        day_str = base._day_str(day)
        try:
            schedule = base.availability.schedule_for_date(day_str)
            games = 0 if schedule is None else len(schedule)
            teams = 0 if schedule is None or schedule.empty else len(set(schedule["away_team_id"].astype(int).tolist() + schedule["home_team_id"].astype(int).tolist()))
        except Exception:
            games = teams = 0
        return {
            "state": "PARTIAL",
            "selected_date": day_str,
            "games": int(games),
            "teams": int(teams),
            "players": 0,
            "out_applied": 0,
            "uncertain": 0,
            "starter_flags": 0,
            "usage_players": 0,
            "team_minutes_ok": 0,
            "usage_source": f"Step 5 fallback active • {type(exc).__name__}",
        }


def clear_role_cache():
    for fn in (advanced_usage_table,):
        try:
            fn.clear()
        except Exception:
            pass
    try:
        prior._espn_usage_fallback.clear()
    except Exception:
        pass
    try:
        base.clear_role_cache()
    except Exception:
        pass


# Re-export Step 1-4 interfaces expected by the existing V2.8 UI.
availability = base.availability
current_season = base.current_season
schedule_for_date = base.schedule_for_date
schedule_diagnostics = base.schedule_diagnostics
clear_schedule_cache = base.clear_schedule_cache
data_health = base.data_health
empirical_profile = base.empirical_profile
game_for_team = base.game_for_team
logo_url = base.logo_url
official_roster = base.official_roster
player_game_log = base.player_game_log
player_form_table = base.player_form_table
slate_player_pool = base.slate_player_pool
team_player_pool = base.team_player_pool
availability_for_game = base.availability_for_game
availability_diagnostics = base.availability_diagnostics
context_diagnostics = base.context_diagnostics
game_context = base.game_context
