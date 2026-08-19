"""WNBA Rebounds V1.5.5 — direct nonblocking Step 6.

This build intentionally bypasses the legacy Step-6 tracking fetch chain on normal
page loads. Steps 1-5 are rendered by the verified V1.4.1 foundation. Step 6 then
uses only already-verified Step-5 rebound form as a clearly labeled baseline so
Streamlit Cloud cannot hang on stats.nba.com / stats.wnba.com timeouts.

Important: fallback fields are NOT labeled as official rebound chances. No
sportsbook or Monte Carlo logic is introduced here.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

import wnba_rebounds_hub_v141 as base

MODEL_VERSION = "WNBA REBOUNDS V1.5.5 • DIRECT NONBLOCKING STEP 6"


def _num(value, default=np.nan):
    try:
        x = float(value)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _build_step6_baseline(step5_players: pd.DataFrame):
    if step5_players is None or step5_players.empty:
        return pd.DataFrame(), pd.DataFrame(), {
            "ready": False,
            "mode": "VERIFIED_BASELINE",
            "modeled_players": 0,
            "covered_players": 0,
            "ready_teams": 0,
            "teams": 0,
            "blockers": [],
        }

    outputs = []
    for _, row in step5_players.iterrows():
        out = row.to_dict()
        proj_min = _num(row.get("PROJ_MIN"), 0.0)
        season_gp = _num(row.get("FORM_SEASON_GP"), 0.0)
        stable36 = _num(row.get("FORM_STABILIZED_REB36"))
        season36 = _num(row.get("FORM_SEASON_REB36"))
        recent36 = _num(row.get("FORM_RAW_RECENT36"))

        covered = bool(
            season_gp >= 3
            and proj_min >= 0
            and np.isfinite(stable36)
            and stable36 >= 0
        )

        out["STEP6_SOURCE"] = "VERIFIED BOX-SCORE REBOUND BASELINE"
        out["STEP6_BASELINE_REB36"] = stable36
        out["STEP6_SEASON_REB36"] = season36
        out["STEP6_RECENT_REB36"] = recent36
        out["STEP6_MIN_SCALED_REB"] = (
            stable36 * proj_min / 36.0
            if np.isfinite(stable36) and proj_min > 0
            else np.nan
        )
        out["STEP6_BASELINE_COVERED"] = covered
        out["STEP6_SAMPLE"] = "VERIFIED BASELINE" if covered else "CHECK"

        # Explicitly leave official tracking fields unavailable. Nothing in this
        # build can be mistaken for Second Spectrum REB Chances.
        out["OPP_TRACKING_COVERED"] = False
        out["OPP_SEASON_CHANCES"] = np.nan
        out["OPP_SEASON_CHANCES36"] = np.nan
        out["OPP_L10_CHANCES"] = np.nan
        out["OPP_L10_CHANCES36"] = np.nan
        outputs.append(out)

    players = pd.DataFrame(outputs)
    modeled = players[
        pd.to_numeric(players.get("PROJ_MIN"), errors="coerce").fillna(0).ge(5.0)
    ].copy()

    team_rows = []
    if not modeled.empty:
        for team, part in modeled.groupby("TEAM_NAME", sort=False):
            total = int(len(part))
            covered = int(part["STEP6_BASELINE_COVERED"].fillna(False).astype(bool).sum())
            team_rows.append({
                "Team": team,
                "Modeled ≥5 MIN": total,
                "Baseline covered": covered,
                "State": "VERIFIED BASELINE" if total and covered == total else "CHECK",
            })
    teams = pd.DataFrame(team_rows)

    ready = bool(
        not modeled.empty
        and modeled["STEP6_BASELINE_COVERED"].fillna(False).astype(bool).all()
    )
    blockers = modeled.loc[
        ~modeled["STEP6_BASELINE_COVERED"].fillna(False).astype(bool),
        [c for c in ["PLAYER_NAME", "TEAM_NAME", "PROJ_MIN", "FORM_SEASON_GP", "FORM_STABILIZED_REB36"] if c in modeled.columns],
    ].copy() if not modeled.empty else pd.DataFrame()

    return players, teams, {
        "ready": ready,
        "mode": "VERIFIED_BASELINE",
        "modeled_players": int(len(modeled)),
        "covered_players": int(modeled["STEP6_BASELINE_COVERED"].fillna(False).astype(bool).sum()) if not modeled.empty else 0,
        "ready_teams": int(teams["State"].eq("VERIFIED BASELINE").sum()) if not teams.empty else 0,
        "teams": int(len(teams)),
        "blockers": blockers.to_dict("records") if not blockers.empty else [],
    }


def _render_step6_direct():
    records = st.session_state.get("wnba_rebounds_step5_players") or []
    frame = pd.DataFrame(records)
    players, teams, info = _build_step6_baseline(frame)

    st.session_state["wnba_rebounds_step6_players"] = players.to_dict("records") if not players.empty else []
    st.session_state["wnba_rebounds_step6_ready"] = bool(info.get("ready"))
    st.session_state["wnba_rebounds_step6_mode"] = "VERIFIED_BASELINE"

    st.markdown("## 🧲 Step 6 — Rebound Opportunity Baseline")
    st.caption(
        "Nonblocking verified fallback. Official Second Spectrum rebound-chance hosts are currently timing out from Streamlit Cloud, "
        "so this layer uses the already-verified Step-5 season/recent rebound-rate infrastructure. It is NOT official REB Chances and "
        "will be replaced automatically once a reliable tracking source is integrated."
    )

    a, b, c, d = st.columns(4)
    a.metric("Team checks", f"{info.get('ready_teams',0)}/{info.get('teams',0)}")
    b.metric("Modeled ≥5 MIN", info.get("modeled_players",0))
    c.metric("Baseline covered", info.get("covered_players",0))
    d.metric("Mode", "NONBLOCKING")

    if info.get("ready"):
        st.success(
            "✅ STEP 6 BASELINE PASSED • every modeled rotation player has verified rebound-rate infrastructure. "
            "Step 7 (opponent missed-shot environment) is unlocked. Official REB Chances remain unavailable and are not being faked."
        )
    else:
        st.error(
            "⛔ STEP 6 CHECK • at least one modeled player lacks a verified rebound baseline. Step 7 remains locked."
        )

    if not teams.empty:
        st.dataframe(teams, hide_index=True, use_container_width=True)

    with st.expander("🧲 Player rebound-opportunity baseline board"):
        if players.empty:
            st.info("No Step-6 player rows available.")
        else:
            modeled = players[
                pd.to_numeric(players.get("PROJ_MIN"), errors="coerce").fillna(0).ge(5.0)
            ].copy()
            cols = [c for c in [
                "PLAYER_NAME", "TEAM_NAME", "PROJ_MIN", "FORM_SEASON_GP",
                "STEP6_SEASON_REB36", "STEP6_RECENT_REB36", "STEP6_BASELINE_REB36",
                "STEP6_MIN_SCALED_REB", "STEP6_SOURCE", "STEP6_SAMPLE",
            ] if c in modeled.columns]
            st.dataframe(modeled[cols], hide_index=True, use_container_width=True)

    if info.get("blockers"):
        with st.expander("🔎 Step-6 blockers"):
            st.dataframe(pd.DataFrame(info["blockers"]), hide_index=True, use_container_width=True)

    with st.expander("🛰️ Official tracking status"):
        st.warning(
            "NBA Stats and legacy WNBA Stats tracking endpoints are bypassed on normal page loads because Streamlit Cloud is timing out. "
            "No network request to those hosts is made by V1.5.5, so this page should load immediately."
        )

    st.markdown("## 🧱 Rebounds Build Order — Current")
    statuses = ["✅ LIVE"] * 5 + (["✅ BASELINE", "➡️ NEXT"] if info.get("ready") else ["⚠️ ACTIVE / CHECK", "🔒 LOCKED"])
    layers = [
        "Verified daily WNBA slate",
        "Current rosters + injuries/status",
        "Projected minutes + rotation",
        "Offensive/defensive rebound role",
        "Recent + season rebound form",
        "Rebound chances/opportunities",
        "Opponent missed-shot environment",
    ]
    st.dataframe(
        pd.DataFrame({"Step": list(range(1,8)), "Layer": layers, "Status": statuses}),
        hide_index=True,
        use_container_width=True,
    )


def render_wnba_rebounds_hub(*args, **kwargs):
    # Render only the verified Steps 1-5 foundation. V1.5/V1.5.1 tracking code is
    # never imported or called from this route, eliminating the 12-second x 4
    # timeout chain seen in Streamlit Cloud diagnostics.
    out = base.render_wnba_rebounds_hub(*args, **kwargs)
    if st.session_state.get("wnba_rebounds_step5_ready"):
        _render_step6_direct()
    else:
        st.info("Step 6 remains locked until Step 5 is verified.")
    st.caption("⚡ V1.5.5 direct fast path active • no stats.nba.com/stats.wnba.com calls on normal page load.")
    return out


__all__ = ["MODEL_VERSION", "render_wnba_rebounds_hub"]
