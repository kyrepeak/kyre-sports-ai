"""WNBA Rebounds V1.5 — Step 6 verified rebound chances / opportunities.

Extends V1.4.1. Uses official WNBA/NBA Stats player-tracking Rebounding data
(Second Spectrum) when available. This layer is opportunity infrastructure only:
no sportsbook line, final rebound projection, Monte Carlo, or pick grading.
"""
from __future__ import annotations

import math
import re
import unicodedata
from typing import Any

import numpy as np
import pandas as pd
import requests
import streamlit as st

import wnba_rebounds_hub_v141 as base

MODEL_VERSION = "WNBA REBOUNDS V1.5 • STEP 6 VERIFIED REBOUND CHANCES / OPPORTUNITIES"

TRACKING_URL = "https://stats.wnba.com/stats/leaguedashptstats"
TRACKING_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://www.wnba.com",
    "Referer": "https://www.wnba.com/",
    "Connection": "keep-alive",
}


def _num(v: Any, default=np.nan):
    try:
        x = float(v)
        return default if not np.isfinite(x) else x
    except Exception:
        return default


def _norm_name(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    return re.sub(r"[^a-z0-9]", "", text)


def _results_to_frame(payload: dict) -> pd.DataFrame:
    sets = payload.get("resultSets") or payload.get("resultSet") or []
    if isinstance(sets, dict):
        sets = [sets]
    for rs in sets:
        headers = rs.get("headers") or []
        rows = rs.get("rowSet") or []
        if headers:
            return pd.DataFrame(rows, columns=headers)
    return pd.DataFrame()


@st.cache_data(ttl=900, show_spinner=False, max_entries=24)
def _fetch_tracking(season: int, last_n: int) -> tuple[pd.DataFrame, dict]:
    params = {
        "College": "", "Conference": "", "Country": "", "DateFrom": "", "DateTo": "",
        "Division": "", "DraftPick": "", "DraftYear": "", "GameScope": "", "Height": "",
        "LastNGames": int(last_n), "LeagueID": "10", "Location": "", "Month": "0",
        "OpponentTeamID": "0", "Outcome": "", "PORound": "0", "PerMode": "PerGame",
        "PlayerExperience": "", "PlayerOrTeam": "Player", "PlayerPosition": "",
        "PtMeasureType": "Rebounding", "Season": str(int(season)), "SeasonSegment": "",
        "SeasonType": "Regular Season", "StarterBench": "", "TeamID": "0",
        "VsConference": "", "VsDivision": "", "Weight": "",
    }
    try:
        r = requests.get(TRACKING_URL, params=params, headers=TRACKING_HEADERS, timeout=18)
        r.raise_for_status()
        frame = _results_to_frame(r.json())
        return frame, {"ok": not frame.empty, "status": r.status_code, "rows": int(len(frame)), "last_n": int(last_n)}
    except Exception as exc:
        return pd.DataFrame(), {"ok": False, "error": f"{type(exc).__name__}: {exc}", "last_n": int(last_n)}


def _col(frame: pd.DataFrame, *names: str):
    if frame is None or frame.empty:
        return None
    lookup = {str(c).upper(): c for c in frame.columns}
    for name in names:
        if name.upper() in lookup:
            return lookup[name.upper()]
    return None


def _prepare_tracking(frame: pd.DataFrame, prefix: str) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame()
    f = frame.copy()
    pid = _col(f, "PLAYER_ID")
    name = _col(f, "PLAYER_NAME")
    gp = _col(f, "GP")
    mins = _col(f, "MIN")
    reb = _col(f, "REB")
    chances = _col(f, "REB_CHANCES")
    chance_pct = _col(f, "REB_CHANCE_PCT")
    contested = _col(f, "CONTESTED_REB")
    contested_pct = _col(f, "CONTESTED_REB_PCT")
    deferred = _col(f, "REB_CHANCES_DEFERRED", "DEFERRED_REB_CHANCES")
    adjusted_pct = _col(f, "ADJUSTED_REB_CHANCE_PCT")
    distance = _col(f, "AVG_REB_DIST", "AVG_REB_DISTANCE")
    if chances is None or mins is None:
        return pd.DataFrame()
    out = pd.DataFrame(index=f.index)
    out["PLAYER_ID"] = pd.to_numeric(f[pid], errors="coerce") if pid else np.nan
    out["NAME_KEY"] = f[name].map(_norm_name) if name else ""
    out[f"{prefix}_GP"] = pd.to_numeric(f[gp], errors="coerce") if gp else np.nan
    out[f"{prefix}_MIN"] = pd.to_numeric(f[mins], errors="coerce")
    out[f"{prefix}_REB"] = pd.to_numeric(f[reb], errors="coerce") if reb else np.nan
    out[f"{prefix}_CHANCES"] = pd.to_numeric(f[chances], errors="coerce")
    out[f"{prefix}_CHANCE_PCT"] = pd.to_numeric(f[chance_pct], errors="coerce") if chance_pct else np.nan
    out[f"{prefix}_CONTESTED"] = pd.to_numeric(f[contested], errors="coerce") if contested else np.nan
    out[f"{prefix}_CONTESTED_PCT"] = pd.to_numeric(f[contested_pct], errors="coerce") if contested_pct else np.nan
    out[f"{prefix}_DEFERRED"] = pd.to_numeric(f[deferred], errors="coerce") if deferred else np.nan
    out[f"{prefix}_ADJ_CHANCE_PCT"] = pd.to_numeric(f[adjusted_pct], errors="coerce") if adjusted_pct else np.nan
    out[f"{prefix}_AVG_DIST"] = pd.to_numeric(f[distance], errors="coerce") if distance else np.nan
    out[f"{prefix}_CHANCES36"] = np.where(out[f"{prefix}_MIN"].gt(0), 36.0 * out[f"{prefix}_CHANCES"] / out[f"{prefix}_MIN"], np.nan)
    return out


def _lookup(track: pd.DataFrame, row: pd.Series):
    if track is None or track.empty:
        return None
    pid = pd.to_numeric(pd.Series([row.get("PLAYER_ID")]), errors="coerce").iloc[0]
    if pd.notna(pid):
        hit = track[pd.to_numeric(track["PLAYER_ID"], errors="coerce").eq(float(pid))]
        if not hit.empty:
            return hit.iloc[0]
    key = _norm_name(row.get("PLAYER_NAME"))
    hit = track[track["NAME_KEY"].eq(key)]
    return hit.iloc[0] if not hit.empty else None


def _build_step6(step5_players: pd.DataFrame, day: str):
    if step5_players is None or step5_players.empty:
        return pd.DataFrame(), pd.DataFrame(), {"ready": False, "reason": "No verified Step-5 player frame"}
    season = pd.to_datetime(day).year
    season_raw, season_diag = _fetch_tracking(season, 0)
    l10_raw, l10_diag = _fetch_tracking(season, 10)
    season_t = _prepare_tracking(season_raw, "OPP_SEASON")
    l10_t = _prepare_tracking(l10_raw, "OPP_L10")

    outputs = []
    for _, row in step5_players.iterrows():
        out = row.to_dict()
        sr = _lookup(season_t, row)
        lr = _lookup(l10_t, row)
        for prefix, src in (("OPP_SEASON", sr), ("OPP_L10", lr)):
            for suffix in ("GP", "MIN", "REB", "CHANCES", "CHANCE_PCT", "CONTESTED", "CONTESTED_PCT", "DEFERRED", "ADJ_CHANCE_PCT", "AVG_DIST", "CHANCES36"):
                out[f"{prefix}_{suffix}"] = src.get(f"{prefix}_{suffix}") if src is not None else np.nan

        s36 = _num(out.get("OPP_SEASON_CHANCES36"))
        l36 = _num(out.get("OPP_L10_CHANCES36"))
        if np.isfinite(s36) and s36 > 0:
            recent = l36 if np.isfinite(l36) and l36 > 0 else s36
            recent_capped = float(np.clip(recent, 0.75 * s36, 1.25 * s36))
            stable36 = 0.70 * s36 + 0.30 * recent_capped
        else:
            recent_capped = np.nan
            stable36 = l36 if np.isfinite(l36) else np.nan
        out["OPP_CAPPED_L10_CHANCES36"] = recent_capped
        out["OPP_STABLE_CHANCES36"] = stable36
        proj_min = _num(row.get("PROJ_MIN"), 0.0)
        out["OPP_MIN_SCALED_CHANCES"] = stable36 * proj_min / 36.0 if np.isfinite(stable36) and proj_min > 0 else np.nan
        sgp = _num(out.get("OPP_SEASON_GP"), 0)
        lgp = _num(out.get("OPP_L10_GP"), 0)
        covered = bool(sgp >= 3 and np.isfinite(s36) and s36 > 0)
        out["OPP_TRACKING_COVERED"] = covered
        out["OPP_TRACKING_SAMPLE"] = "VERIFIED" if covered else "CHECK"
        outputs.append(out)

    players = pd.DataFrame(outputs)
    modeled = players[pd.to_numeric(players.get("PROJ_MIN"), errors="coerce").fillna(0).ge(5.0)].copy()
    rows = []
    if not modeled.empty:
        for team, part in modeled.groupby("TEAM_NAME", sort=False):
            total = len(part)
            covered = int(part["OPP_TRACKING_COVERED"].fillna(False).astype(bool).sum())
            rows.append({"Team": team, "Modeled ≥5 MIN": int(total), "Tracking covered": covered, "State": "VERIFIED" if total and covered == total else "CHECK"})
    teams = pd.DataFrame(rows)
    ready = bool(not modeled.empty and modeled["OPP_TRACKING_COVERED"].fillna(False).astype(bool).all())
    blockers = modeled.loc[~modeled["OPP_TRACKING_COVERED"].fillna(False).astype(bool), [c for c in ["PLAYER_NAME", "TEAM_NAME", "PROJ_MIN", "OPP_SEASON_GP", "OPP_SEASON_CHANCES", "OPP_SEASON_CHANCES36"] if c in modeled.columns]].copy() if not modeled.empty else pd.DataFrame()
    info = {
        "ready": ready,
        "modeled_players": int(len(modeled)),
        "covered_players": int(modeled["OPP_TRACKING_COVERED"].fillna(False).astype(bool).sum()) if not modeled.empty else 0,
        "ready_teams": int(teams["State"].eq("VERIFIED").sum()) if not teams.empty else 0,
        "teams": int(len(teams)),
        "season_diag": season_diag,
        "l10_diag": l10_diag,
        "blockers": blockers.to_dict("records") if not blockers.empty else [],
    }
    return players, teams, info


def _render_step6(day: str):
    records = st.session_state.get("wnba_rebounds_step5_players") or []
    frame = pd.DataFrame(records)
    st.markdown("## 🧲 Step 6 — Rebound Chances / Opportunities")
    st.caption("Official WNBA player-tracking Rebounding layer. REB Chances are tracking opportunities, not a sportsbook-derived proxy. Recent opportunity movement is capped ±25% before a 70/30 season/L10 stabilization. This does not yet predict final rebounds.")
    players, teams, info = _build_step6(frame, day)
    st.session_state["wnba_rebounds_step6_players"] = players.to_dict("records") if not players.empty else []
    st.session_state["wnba_rebounds_step6_ready"] = bool(info.get("ready"))

    a,b,c,d = st.columns(4)
    a.metric("Team opportunity checks", f"{info.get('ready_teams',0)}/{info.get('teams',0)}")
    b.metric("Modeled ≥5 MIN", info.get("modeled_players",0))
    c.metric("Tracking covered", info.get("covered_players",0))
    d.metric("Minimum tracking sample", "3 GP")

    if info.get("ready"):
        st.success("✅ STEP 6 PASSED • every modeled rotation player has a verified official rebound-chance sample. Step 7 (opponent missed-shot environment) is unlocked.")
    else:
        diag = info.get("season_diag") or {}
        if not diag.get("ok"):
            st.error("⛔ STEP 6 CHECK • official WNBA tracking feed is unavailable/empty right now. Step 7 remains locked; no proxy data is being substituted.")
        else:
            st.error("⛔ STEP 6 CHECK • at least one modeled player lacks a ≥3-game official rebound-chance sample. Step 7 remains locked; nothing is guessed.")

    if not teams.empty:
        st.dataframe(teams, hide_index=True, use_container_width=True)
    with st.expander("🧲 Player rebound-opportunity board"):
        if players.empty:
            st.info("No Step-6 player rows available.")
        else:
            modeled = players[pd.to_numeric(players.get("PROJ_MIN"), errors="coerce").fillna(0).ge(5.0)].copy()
            cols = [c for c in ["PLAYER_NAME","TEAM_NAME","PROJ_MIN","OPP_SEASON_GP","OPP_SEASON_CHANCES","OPP_SEASON_CHANCES36","OPP_L10_CHANCES","OPP_L10_CHANCES36","OPP_STABLE_CHANCES36","OPP_MIN_SCALED_CHANCES","OPP_SEASON_CHANCE_PCT","OPP_SEASON_CONTESTED","OPP_SEASON_AVG_DIST","OPP_TRACKING_SAMPLE"] if c in modeled.columns]
            st.dataframe(modeled[cols], hide_index=True, use_container_width=True)
    if info.get("blockers"):
        with st.expander("🔎 Step-6 blockers"):
            st.dataframe(pd.DataFrame(info["blockers"]), hide_index=True, use_container_width=True)
    with st.expander("🛰️ Official tracking feed diagnostics"):
        st.json({"season": info.get("season_diag"), "L10": info.get("l10_diag")})

    st.markdown("## 🧱 Rebounds Build Order — Current")
    statuses = ["✅ LIVE"]*5 + (["✅ LIVE", "➡️ NEXT"] if info.get("ready") else ["⚠️ ACTIVE / CHECK", "🔒 LOCKED"])
    layers = [
        "Verified daily WNBA slate", "Current rosters + injuries/status", "Projected minutes + rotation",
        "Offensive/defensive rebound role", "Recent + season rebound form", "Rebound chances/opportunities",
        "Opponent missed-shot environment"
    ]
    st.dataframe(pd.DataFrame({"Step": list(range(1,8)), "Layer": layers, "Status": statuses}), hide_index=True, use_container_width=True)


def render_wnba_rebounds_hub(*args, **kwargs):
    out = base.render_wnba_rebounds_hub(*args, **kwargs)
    if st.session_state.get("wnba_rebounds_step5_ready"):
        day = st.session_state.get("wnba_rebounds_slate_date") or pd.Timestamp.now(tz="US/Eastern").strftime("%Y-%m-%d")
        _render_step6(str(day))
    else:
        st.info("Step 6 remains locked until Step 5 is verified.")
    return out


__all__ = ["MODEL_VERSION", "render_wnba_rebounds_hub"]
