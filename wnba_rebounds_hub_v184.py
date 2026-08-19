"""WNBA Rebounds V1.8.4 — Step 5 cold-start coverage stabilization.

Repairs the reboot-only regression where Step 4 is fully VERIFIED for every
modeled player, but the fast Step-5 season/L10 reconciliation marks a few players
CHECK after a cold start.

Rules:
- Never guess rebound data.
- Only repair a Step-5 blocker when Step 4 already verified that same PLAYER_ID
  with >=3 component-valid OREB/DREB games, positive verified minutes, and a
  finite rebound rate.
- Reuse that verified Step-4 history as the baseline/recent fallback when the
  fast Step-5 player-pool lookup is sparse.
- Add zero new network requests.
- Preserve V1.8.3 Step-9 opponent/zero-competition repairs.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

import wnba_rebounds_hub_v141 as step5
import wnba_rebounds_hub_v183 as base

MODEL_VERSION = "WNBA REBOUNDS V1.8.4 • STEP 5 COLD-START COVERAGE STABILIZATION"

# Capture the genuine V1.4.1 function once. This avoids calling through a symbol
# that we temporarily replace during render (and therefore avoids recursion).
_ORIGINAL_STEP5_FORM_141 = step5._build_step5_form_141


def _finite(value):
    try:
        return bool(np.isfinite(float(value)))
    except Exception:
        return False


def _num(value, default=np.nan):
    try:
        x = float(value)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _repair_verified_step4_row(row: pd.Series) -> pd.Series:
    r = row.copy()
    if _num(r.get("PROJ_MIN"), 0.0) < 5.0 or bool(r.get("_FORM_COVERED_141")):
        return r

    role_gp = int(_num(r.get("REB_ROLE_GP"), 0) or 0)
    role_min_total = _num(r.get("REB_ROLE_MIN"), np.nan)
    role_reb36 = _num(r.get("REB36"), np.nan)
    role_reb_total = _num(r.get("REB_L10_TOTAL"), np.nan)

    role_verified = bool(
        role_gp >= 3
        and _finite(role_min_total)
        and float(role_min_total) > 0
        and _finite(role_reb36)
        and float(role_reb36) >= 0
    )
    if not role_verified:
        return r

    avg_min = float(role_min_total) / float(role_gp)
    avg_reb = (
        float(role_reb_total) / float(role_gp)
        if _finite(role_reb_total)
        else float(role_reb36) * avg_min / 36.0
    )

    season_gp = int(_num(r.get("FORM_SEASON_GP"), 0) or 0)
    season36 = _num(r.get("FORM_SEASON_REB36"), np.nan)
    if season_gp < 3 or not _finite(season36):
        r["FORM_SEASON_GP"] = role_gp
        r["FORM_SEASON_MIN"] = avg_min
        r["FORM_SEASON_REB"] = avg_reb
        r["FORM_SEASON_REB36"] = float(role_reb36)
        r["FORM_BASELINE_SOURCE"] = "VERIFIED STEP-4 PLAYER_ID OREB/DREB HISTORY"

    l10_gp = int(_num(r.get("FORM_L10_GP"), 0) or 0)
    l10_36 = _num(r.get("FORM_L10_REB36"), np.nan)
    if l10_gp < 3 or not _finite(l10_36):
        r["FORM_L10_GP"] = min(10, role_gp)
        r["FORM_L10_REB"] = avg_reb
        r["FORM_L10_REB36"] = float(role_reb36)
        r["FORM_RECENT_SOURCE"] = "VERIFIED STEP-4 PLAYER_ID OREB/DREB HISTORY"

    l5_gp = int(_num(r.get("FORM_L5_GP"), 0) or 0)
    l5_36 = _num(r.get("FORM_L5_REB36"), np.nan)
    if l5_gp < 3 or not _finite(l5_36):
        r["FORM_L5_GP"] = min(5, role_gp)
        r["FORM_L5_REB"] = avg_reb
        r["FORM_L5_REB36"] = float(role_reb36)

    stabilized, raw_recent, capped_recent = step5.base._stabilized_form_rate(
        r.get("FORM_SEASON_REB36"),
        r.get("FORM_L10_REB36"),
        r.get("FORM_L5_REB36"),
        r.get("FORM_L3_REB36"),
        r.get("FORM_SEASON_GP"),
    )
    r["FORM_STABILIZED_REB36"] = stabilized
    r["FORM_RAW_RECENT36"] = raw_recent
    r["FORM_CAPPED_RECENT36"] = capped_recent

    s = _num(r.get("FORM_SEASON_REB36"), np.nan)
    if _finite(s) and float(s) > 0 and _finite(stabilized):
        trend_pct = 100.0 * (float(stabilized) / float(s) - 1.0)
        r["FORM_TREND_PCT"] = trend_pct
        r["FORM_TREND"] = "UP" if trend_pct >= 4.0 else "DOWN" if trend_pct <= -4.0 else "STEADY"

    baseline_verified = int(_num(r.get("FORM_SEASON_GP"), 0) or 0) >= 3 and _finite(r.get("FORM_SEASON_REB36"))
    recent_verified = int(_num(r.get("FORM_L10_GP"), 0) or 0) >= 3 and _finite(r.get("FORM_L10_REB36"))
    stable_verified = _finite(r.get("FORM_STABILIZED_REB36"))
    if baseline_verified and recent_verified and stable_verified:
        r["_FORM_COVERED_141"] = True
        r["FORM_FALLBACK_USED"] = True
        r["FORM_SAMPLE"] = "VERIFIED • STEP-4 COLD-START FALLBACK"
        r["FORM_COLDSTART_REPAIRED"] = True
    return r


def _rebuild_summary(players: pd.DataFrame, original_info: dict):
    repaired = players.copy()
    repaired["PROJ_MIN"] = pd.to_numeric(repaired.get("PROJ_MIN"), errors="coerce").fillna(0.0)
    modeled = repaired[repaired["PROJ_MIN"].ge(5.0)].copy()
    if not modeled.empty:
        covered_series = modeled.get("_FORM_COVERED_141", pd.Series(False, index=modeled.index)).fillna(False).astype(bool)
        modeled["_COVERED_184"] = covered_series

    team_rows = []
    if not modeled.empty:
        for team_name, part in modeled.groupby("TEAM_NAME", sort=False):
            total = int(len(part))
            covered = int(part["_COVERED_184"].sum())
            fallbacks = int(part.get("FORM_FALLBACK_USED", pd.Series(False, index=part.index)).fillna(False).astype(bool).sum())
            cold_repairs = int(part.get("FORM_COLDSTART_REPAIRED", pd.Series(False, index=part.index)).fillna(False).astype(bool).sum())
            team_rows.append({
                "Team": team_name,
                "Modeled ≥5 MIN": total,
                "Form covered": covered,
                "PLAYER_ID fallbacks": fallbacks,
                "Cold-start repairs": cold_repairs,
                "State": "VERIFIED" if total > 0 and covered == total else "CHECK",
            })
    teams = pd.DataFrame(team_rows)

    team_count = int(teams["Team"].nunique()) if not teams.empty else 0
    ready_teams = int(teams["State"].eq("VERIFIED").sum()) if not teams.empty else 0
    covered_players = int(modeled["_COVERED_184"].sum()) if not modeled.empty else 0
    ready = bool(team_count > 0 and ready_teams == team_count and covered_players == len(modeled))

    blockers = []
    if not modeled.empty:
        bad = modeled[~modeled["_COVERED_184"]]
        for _, r in bad.iterrows():
            blockers.append({
                "Player": str(r.get("PLAYER_NAME") or "Player"),
                "Team": str(r.get("TEAM_NAME") or ""),
                "Proj MIN": round(_num(r.get("PROJ_MIN"), 0.0), 2),
                "Season GP": int(_num(r.get("FORM_SEASON_GP"), 0) or 0),
                "L10 GP": int(_num(r.get("FORM_L10_GP"), 0) or 0),
                "Role GP": int(_num(r.get("REB_ROLE_GP"), 0) or 0),
                "Role REB36": _num(r.get("REB36"), np.nan),
                "Baseline source": str(r.get("FORM_BASELINE_SOURCE") or "—"),
                "Recent source": str(r.get("FORM_RECENT_SOURCE") or "—"),
            })

    info = dict(original_info or {})
    info.update({
        "ready": ready,
        "teams": team_count,
        "ready_teams": ready_teams,
        "modeled_players": int(len(modeled)),
        "covered_players": covered_players,
        "blockers": blockers,
        "cold_start_repairs": int(modeled.get("FORM_COLDSTART_REPAIRED", pd.Series(False, index=modeled.index)).fillna(False).astype(bool).sum()) if not modeled.empty else 0,
        "repair_version": "V1.8.4 STEP5 COLD-START STABILIZATION",
        "performance_mode": "ZERO NEW NETWORK • STEP4 VERIFIED HISTORY REUSE",
    })
    return repaired, teams, info


def _build_step5_form_184(step4_players: pd.DataFrame, day: str, slate: pd.DataFrame):
    players, teams, info = _ORIGINAL_STEP5_FORM_141(step4_players, day, slate)
    if players is None or players.empty:
        return players, teams, info
    repaired = players.apply(_repair_verified_step4_row, axis=1)
    return _rebuild_summary(repaired, info)


def render_wnba_rebounds_hub(*args, **kwargs):
    old_step5 = step5._build_step5_form_141
    step5._build_step5_form_141 = _build_step5_form_184
    try:
        out = base.render_wnba_rebounds_hub(*args, **kwargs)
    finally:
        step5._build_step5_form_141 = old_step5

    records = st.session_state.get("wnba_rebounds_step5_players") or []
    if records:
        frame = pd.DataFrame(records)
        modeled = frame[pd.to_numeric(frame.get("PROJ_MIN"), errors="coerce").fillna(0.0).ge(5.0)].copy()
        repaired_count = int(modeled.get("FORM_COLDSTART_REPAIRED", pd.Series(False, index=modeled.index)).fillna(False).astype(bool).sum()) if not modeled.empty else 0
        st.caption(
            "⚡ V1.8.4 Step-5 cold-start stabilization • "
            f"{repaired_count} verified Step-4 fallback row(s) reused • "
            "zero new network requests • no guessed rebound data."
        )
    return out


def __getattr__(name):
    return getattr(base, name)


__all__ = ["MODEL_VERSION", "render_wnba_rebounds_hub"]
