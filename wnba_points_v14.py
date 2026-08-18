"""WNBA Points V1.4 — Points-specific empirical history integrity.

Keeps V1.3 strict current-roster player pool, projection math and SportsGameOdds
transport intact. The change is isolated to Points variance/history plumbing:
- empirical game logs are keyed to the selected Points slate date explicitly;
- verified ESPN WNBA summaries are matched by team + player id/name;
- 5M Monte Carlo uses actual scoring variance whenever >=5 prior games exist;
- old PRA session-date state can no longer make Points history silently read zero.

Frozen WNBA PRA V3.2.1 and MLB V2.1.7 are not modified.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import streamlit as st

import wnba_points_v13 as prior
import wnba_players_v25 as players
import wnba_sportsgameodds_v1 as sgo1

base = prior.base
MODEL_VERSION = "WNBA POINTS V1.4 • EXPLICIT EMPIRICAL HISTORY"
MODEL_SCHEMA = "WNBA-POINTS-V1.4-STRICT-ROSTER-EMPIRICAL"
STANDARD_SIMS = prior.STANDARD_SIMS
FINAL_SIMS = prior.FINAL_SIMS
BATCH_SIZE = prior.BATCH_SIZE
CACHE_DIR = prior.CACHE_DIR
market = prior.market
sgo = prior.sgo


def _day(day):
    return pd.to_datetime(day).strftime("%Y-%m-%d")


def std_key(day):
    return f"wnba_points_v14_standard::{_day(day)}"


def final_key(day):
    return f"wnba_points_v14_final::{_day(day)}"


def source_key(day):
    return f"wnba_points_v14_restore_source::{_day(day)}"


def _browser_key(day):
    return f"kyre_sports_ai_wnba_points_v14::{_day(day)}"


def _component_key(day):
    return f"wnba_points_v14_local_get::{_day(day)}"


def _disk_path(day):
    return CACHE_DIR / f"wnba_points_v14_{_day(day)}.json.gz"


def _num(value, default=np.nan):
    try:
        x = float(value)
        return default if pd.isna(x) else x
    except Exception:
        return default


def _norm(value):
    try:
        return sgo1._norm(value)
    except Exception:
        return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


@st.cache_data(ttl=1800, show_spinner=False, max_entries=512)
def points_empirical_profile(day_str: str, player_id: str, player_name: str, team_id: int):
    """Return verified prior-game Points distribution for one player."""
    day_str = _day(day_str)
    tid = int(team_id or 0)
    if not tid:
        return {}
    history = prior._season_history(day_str, {tid})
    if history is None or history.empty:
        return {}

    target_id = str(player_id or "").strip()
    target_name = _norm(player_name)
    rows = []
    history = history.copy()
    history["_d"] = pd.to_datetime(history["game_date"], errors="coerce")
    history = history.sort_values("_d", ascending=False).drop_duplicates("game_id")

    for _, game in history.iterrows():
        gid = str(game.get("game_id") or "")
        gdate = str(game.get("game_date") or "")
        if not gid:
            continue
        try:
            frame = players._espn_game_summary(gid, gdate)
        except Exception:
            frame = pd.DataFrame()
        if frame is None or frame.empty:
            continue
        f = frame.copy()
        if "TEAM_ID" in f.columns:
            f = f[pd.to_numeric(f["TEAM_ID"], errors="coerce").fillna(0).astype(int).eq(tid)]
        if f.empty:
            continue

        match = pd.DataFrame()
        if target_id and "PLAYER_ID" in f.columns:
            exact = f[f["PLAYER_ID"].astype(str).eq(target_id)]
            if not exact.empty:
                match = exact
        if match.empty and target_name and "PLAYER_NAME" in f.columns:
            match = f[f["PLAYER_NAME"].map(_norm).eq(target_name)]
        if match.empty:
            continue
        r = match.iloc[0]
        pts = _num(r.get("PTS"), np.nan)
        mins = _num(r.get("MIN"), np.nan)
        if pd.isna(pts):
            continue
        rows.append({"GAME_DATE": gdate, "PTS": pts, "MIN": mins})

    log = pd.DataFrame(rows)
    if log.empty:
        return {}
    log = log.drop_duplicates("GAME_DATE", keep="first").head(30).copy()
    log["PTS"] = pd.to_numeric(log["PTS"], errors="coerce")
    log["MIN"] = pd.to_numeric(log["MIN"], errors="coerce")
    log = log.dropna(subset=["PTS"])
    if log.empty:
        return {}
    sd = float(log["PTS"].std(ddof=1)) if len(log) >= 2 else np.nan
    return {
        "games": int(len(log)),
        "pts": float(log["PTS"].mean()),
        "sd_pts": float(max(sd, 0.01)) if pd.notna(sd) else np.nan,
        "minutes": float(log["MIN"].mean()) if log["MIN"].notna().any() else np.nan,
        "source": "ESPN WNBA verified Points game summaries",
    }


def _points_distribution(proj, lineup_ready=False):
    mu = max(0.0, _num(proj.get("PROJ_PTS"), 0.0))
    day = proj.get("POINTS_SLATE_DATE") or st.session_state.get("wnba_points_date") or st.session_state.get("wnba_points_date_control") or pd.Timestamp.now().date()
    day_str = _day(day)
    profile = points_empirical_profile(
        day_str,
        str(proj.get("PLAYER_ID") or ""),
        str(proj.get("PLAYER_NAME") or ""),
        int(_num(proj.get("TEAM_ID"), 0)),
    ) or {}
    games = int(profile.get("games") or 0)

    if games >= 5:
        hist_mu = max(1.0, _num(profile.get("pts"), mu or 1.0))
        role_scale = float(np.clip((max(mu, 1.0) / hist_mu) ** 0.25, 0.82, 1.20))
        hist_sd = _num(profile.get("sd_pts"), np.nan)
        if pd.isna(hist_sd) or hist_sd <= 0:
            hist_sd = max(2.4, math.sqrt(max(hist_mu, 1.0)) * 1.20)
        sd = max(1.25, float(hist_sd) * role_scale)
        source = f"EMPIRICAL POINTS • {profile.get('source') or 'verified game log'}"
        quality = min(1.0, 0.58 + min(games, 30) / 30.0 * 0.34)
    else:
        sd = max(2.4, math.sqrt(max(mu, 1.0)) * 1.20)
        source = "FALLBACK POINTS • verified history <5 games"
        quality = 0.48

    context_q = float(np.clip(_num(proj.get("context_quality"), 0.5), 0.0, 1.0))
    role_label = str(proj.get("ROLE_LABEL") or "ACTIVE").upper()
    uncertainty = 1.0 + 0.08 * (1.0 - context_q)
    if not lineup_ready:
        uncertainty += 0.08
    if "UNCERTAIN" in role_label:
        uncertainty += 0.10
    if _num(proj.get("PROJ_MIN"), 0.0) < 15.0:
        uncertainty += 0.04
    return mu, sd * uncertainty, {
        "hist_games": games,
        "variance_source": source,
        "data_quality": quality,
        "uncertainty_mult": uncertainty,
        "hist_pts_mean": _num(profile.get("pts"), np.nan),
        "hist_pts_sd": _num(profile.get("sd_pts"), np.nan),
    }


def _prepare(day):
    projections, pairs, snap, pmeta, lineups = prior._prepare(day)
    if isinstance(projections, pd.DataFrame) and not projections.empty:
        projections = projections.copy()
        projections["POINTS_SLATE_DATE"] = _day(day)
    return projections, pairs, snap, pmeta, lineups


# Patch only the Points V1.0 execution module used by this isolated connector.
# PRA's Monte Carlo module is never altered.
base.MODEL_VERSION = MODEL_VERSION
base.MODEL_SCHEMA = MODEL_SCHEMA
base.std_key = std_key
base.final_key = final_key
base.source_key = source_key
base._browser_key = _browser_key
base._component_key = _component_key
base._disk_path = _disk_path
base._prepare = _prepare
base._points_distribution = _points_distribution

corrected_player_pool = prior.corrected_player_pool
corrected_contexts = prior.corrected_contexts
_paired_points_markets = prior._paired_points_markets
run_standard = base.run_standard
run_final = base.run_final
combined_rows = base.combined_rows
restore_if_missing = base.restore_if_missing
persist_if_ready = base.persist_if_ready
render_points_connector = base.render_points_connector
_finalist_units = prior._finalist_units

__all__ = [
    "MODEL_VERSION", "MODEL_SCHEMA", "STANDARD_SIMS", "FINAL_SIMS", "market", "sgo",
    "std_key", "final_key", "source_key", "corrected_player_pool", "corrected_contexts",
    "points_empirical_profile", "_paired_points_markets", "_prepare", "_points_distribution",
    "_finalist_units", "run_standard", "run_final", "combined_rows", "restore_if_missing",
    "persist_if_ready", "render_points_connector",
]
