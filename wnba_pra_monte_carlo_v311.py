"""WNBA PRA V3.1.1 — empirical covariance handoff hotfix.

WNBA-only. MLB V2.1.7 remains frozen.

V3.1 correctly executed the requested Monte Carlo counts, but diagnostics exposed
that active players rebuilt through the ESPN roster/game-summary fallback could
miss the older WNBA-Stats player_game_log ID path and therefore fall back to an
independent P/R/A covariance matrix.

This module preserves the entire V3.1 simulation/grading engine and replaces only
its empirical-distribution handoff:
1) keep the existing player-id empirical profile when it returns >=5 games;
2) otherwise reconstruct that player's prior-season-to-date WNBA game log from
   verified ESPN WNBA game summaries using team + normalized player name (or ESPN
   player id when available);
3) compute sample PTS/REB/AST standard deviations and correlations from those
   actual prior games;
4) use FALLBACK INDEPENDENT only when neither verified path yields >=5 games.

Sportsbook prices never alter means/covariance. No MLB file/model is changed.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
import streamlit as st

import wnba_pra_monte_carlo_v31 as base
import wnba_players_v25 as players
import wnba_sportsgameodds_v1 as sgo

MODEL_VERSION = "PRA V3.1.1 STEP 8 MC"
STANDARD_SIMS = base.STANDARD_SIMS
FINAL_SIMS = base.FINAL_SIMS


def _num(value, default=np.nan):
    try:
        x = float(value)
        return default if pd.isna(x) else x
    except Exception:
        return default


def _norm(value):
    try:
        return sgo._norm(value)
    except Exception:
        return "".join(ch for ch in str(value or "").lower() if ch.isalnum())


def _corr(frame: pd.DataFrame, a: str, b: str) -> float:
    if frame is None or frame.empty or a not in frame.columns or b not in frame.columns:
        return 0.0
    x = pd.to_numeric(frame[a], errors="coerce")
    y = pd.to_numeric(frame[b], errors="coerce")
    mask = x.notna() & y.notna()
    if int(mask.sum()) < 5:
        return 0.0
    xv, yv = x[mask], y[mask]
    if float(xv.std(ddof=1) or 0.0) <= 1e-9 or float(yv.std(ddof=1) or 0.0) <= 1e-9:
        return 0.0
    try:
        return float(np.clip(xv.corr(yv), -0.75, 0.75))
    except Exception:
        return 0.0


@st.cache_data(ttl=1800, show_spinner=False, max_entries=256)
def _espn_profile(day_str: str, player_id: str, player_name: str, team_id: int):
    """Build an empirical P/R/A profile from verified ESPN WNBA summaries."""
    selected = pd.to_datetime(day_str)
    season = int(selected.year)
    try:
        schedule = players._espn_season_schedule(season)
    except Exception:
        schedule = pd.DataFrame()
    if schedule is None or schedule.empty:
        return {}

    s = schedule.copy()
    dates = pd.to_datetime(s.get("game_date"), errors="coerce")
    before = dates < selected
    final = s.get("status", pd.Series(index=s.index, dtype=object)).astype(str).str.upper().eq("FINAL")
    away = pd.to_numeric(s.get("away_team_id"), errors="coerce").fillna(0).astype(int)
    home = pd.to_numeric(s.get("home_team_id"), errors="coerce").fillna(0).astype(int)
    team_mask = away.eq(int(team_id)) | home.eq(int(team_id))
    hist = s.loc[before & final & team_mask].copy().sort_values("game_date", ascending=False)
    if hist.empty:
        return {}

    target_name = _norm(player_name)
    target_id = str(player_id or "").strip()
    rows = []
    # A season is small; cached ESPN summary calls make this cheap after the
    # selected-player-pool/context layers have already touched the games.
    for _, game in hist.iterrows():
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
            f = f[pd.to_numeric(f["TEAM_ID"], errors="coerce").fillna(0).astype(int).eq(int(team_id))]
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
        reb = _num(r.get("REB"), np.nan)
        ast = _num(r.get("AST"), np.nan)
        mins = _num(r.get("MIN"), np.nan)
        if any(pd.isna(v) for v in (pts, reb, ast)):
            continue
        rows.append({"GAME_DATE": gdate, "PTS": pts, "REB": reb, "AST": ast, "MIN": mins})

    log = pd.DataFrame(rows)
    if len(log) < 5:
        return {}
    # Cap to the most recent 30 games to keep covariance reflective of the
    # current season role while still providing a stable sample.
    log = log.head(30).copy()
    for c in ("PTS", "REB", "AST", "MIN"):
        log[c] = pd.to_numeric(log[c], errors="coerce")
    log = log.dropna(subset=["PTS", "REB", "AST"])
    if len(log) < 5:
        return {}

    pra = log["PTS"] + log["REB"] + log["AST"]
    return {
        "games": int(len(log)),
        "pts": float(log["PTS"].mean()),
        "reb": float(log["REB"].mean()),
        "ast": float(log["AST"].mean()),
        "pra": float(pra.mean()),
        "sd_pts": float(max(log["PTS"].std(ddof=1), 0.01)),
        "sd_reb": float(max(log["REB"].std(ddof=1), 0.01)),
        "sd_ast": float(max(log["AST"].std(ddof=1), 0.01)),
        "corr_pr": _corr(log, "PTS", "REB"),
        "corr_pa": _corr(log, "PTS", "AST"),
        "corr_ra": _corr(log, "REB", "AST"),
        "source": "ESPN WNBA verified game summaries",
    }


def _profile_for_projection(proj):
    # Keep the existing ID-based route when healthy.
    try:
        profile = base.step6._empirical_for_player(proj.get("PLAYER_ID")) or {}
    except Exception:
        profile = {}
    if int(profile.get("games") or 0) >= 5:
        out = dict(profile)
        out["source"] = str(out.get("source") or "existing WNBA player game log")
        return out

    day = st.session_state.get("wnba_pra_v2_date") or pd.Timestamp.now().date()
    day_str = pd.to_datetime(day).strftime("%Y-%m-%d")
    return _espn_profile(
        day_str,
        str(proj.get("PLAYER_ID") or ""),
        str(proj.get("PLAYER_NAME") or ""),
        int(_num(proj.get("TEAM_ID"), 0)),
    )


def _component_distribution_v311(proj, lineup_ready=False):
    means = np.asarray([
        max(0.0, _num(proj.get("PROJ_PTS"), 0.0)),
        max(0.0, _num(proj.get("PROJ_REB"), 0.0)),
        max(0.0, _num(proj.get("PROJ_AST"), 0.0)),
    ], dtype=float)

    profile = _profile_for_projection(proj) or {}
    games = int(profile.get("games") or 0)

    if games >= 5:
        sds = np.asarray([
            max(1.25, _num(profile.get("sd_pts"), 2.8)),
            max(0.90, _num(profile.get("sd_reb"), 1.8)),
            max(0.80, _num(profile.get("sd_ast"), 1.6)),
        ], dtype=float)
        cpr = float(np.clip(_num(profile.get("corr_pr"), 0.0), -0.75, 0.75))
        cpa = float(np.clip(_num(profile.get("corr_pa"), 0.0), -0.75, 0.75))
        cra = float(np.clip(_num(profile.get("corr_ra"), 0.0), -0.75, 0.75))
        corr = np.asarray([[1.0,cpr,cpa],[cpr,1.0,cra],[cpa,cra,1.0]], dtype=float)
        src = str(profile.get("source") or "verified empirical game log")
        source = f"EMPIRICAL CORRELATED • {src}"
        quality = min(1.0, 0.58 + min(games, 30) / 30.0 * 0.34)
    else:
        sds = np.asarray([
            max(2.4, math.sqrt(max(means[0], 1.0)) * 1.20),
            max(1.5, math.sqrt(max(means[1], 1.0)) * 1.10),
            max(1.3, math.sqrt(max(means[2], 1.0)) * 1.12),
        ], dtype=float)
        corr = np.eye(3, dtype=float)
        source = "FALLBACK INDEPENDENT • no verified >=5-game log"
        quality = 0.48

    context_q = float(np.clip(_num(proj.get("context_quality"), 0.5), 0.0, 1.0))
    role_label = str(proj.get("ROLE_LABEL") or "ACTIVE").upper()
    uncertainty_mult = 1.0 + 0.08 * (1.0 - context_q)
    if not lineup_ready:
        uncertainty_mult += 0.08
    if "UNCERTAIN" in role_label:
        uncertainty_mult += 0.10
    if _num(proj.get("PROJ_MIN"), 0.0) < 15.0:
        uncertainty_mult += 0.04
    sds = sds * uncertainty_mult

    cov = corr * np.outer(sds, sds)
    cov = base._nearest_psd(cov)
    return means, cov, {
        "hist_games": games,
        "variance_source": source,
        "data_quality": quality,
        "uncertainty_mult": float(uncertainty_mult),
        "component_sd_pts": float(math.sqrt(cov[0,0])),
        "component_sd_reb": float(math.sqrt(cov[1,1])),
        "component_sd_ast": float(math.sqrt(cov[2,2])),
    }


def _install():
    # base._market_rows resolves this global at execution time, so replacing the
    # single distribution builder preserves every other tested V3.1 behavior.
    base._component_distribution = _component_distribution_v311


def run_standard(day, progress=None):
    _install()
    return base.run_standard(day, progress=progress)


def run_final(day, standard_rows, progress=None):
    _install()
    return base.run_final(day, standard_rows, progress=progress)


def render_monte_carlo(day):
    _install()
    day_key = pd.to_datetime(day).strftime("%Y-%m-%d")
    migration_key = f"wnba_pra_v311_empirical_migrated::{day_key}"
    if not st.session_state.get(migration_key):
        # Old 5M results used the exposed fallback covariance; force one clean
        # rerun instead of silently displaying them under the hotfix label.
        st.session_state.pop(f"wnba_pra_v31_standard::{day_key}", None)
        st.session_state.pop(f"wnba_pra_v31_final::{day_key}", None)
        st.session_state[migration_key] = True
    st.info(
        "🧬 V3.1.1 empirical covariance fix active: verified player-id logs are used first; "
        "ESPN WNBA game-summary logs are the fallback before any independent variance is allowed."
    )
    return base.render_monte_carlo(day)


__all__ = ["MODEL_VERSION","STANDARD_SIMS","FINAL_SIMS","run_standard","run_final","render_monte_carlo"]
