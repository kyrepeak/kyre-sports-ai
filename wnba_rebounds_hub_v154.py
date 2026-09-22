"""WNBA Rebounds V1.5.4 — resilient Step 6 opportunity layer.

Normal page loads never block on the NBA/WNBA tracking hosts. When official
Second Spectrum REB Chances are unavailable from Streamlit Cloud, Step 6 uses
only already-verified box-score rebound form as a clearly labeled opportunity
baseline. It does NOT fabricate or relabel the baseline as official REB Chances.

A manual refresh button can attempt the official tracking hosts on demand. If
that succeeds, the official Step-6 output is used. Frozen MLB/PRA/Points modules
are untouched.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

import wnba_rebounds_hub_v151 as base
import wnba_rebounds_hub_v15 as step6_mod

MODEL_VERSION = "WNBA REBOUNDS V1.5.4 • RESILIENT STEP 6 + NONBLOCKING OFFICIAL TRACKING"

_RAW_BUILD = step6_mod._build_step6
_RAW_RENDER = step6_mod._render_step6


def _num(value, default=np.nan):
    try:
        x = float(value)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _fallback_build(step5_players: pd.DataFrame, day: str):
    """Build a verified, non-tracking opportunity baseline from Step-5 data.

    This is intentionally *not* called REB Chances. It preserves the verified
    player/minute/rebound-form infrastructure so the later opponent-environment
    layers can be developed without pretending the tracking feed succeeded.
    """
    if step5_players is None or step5_players.empty:
        return pd.DataFrame(), pd.DataFrame(), {
            "ready": False,
            "reason": "No verified Step-5 player frame",
            "mode": "FALLBACK",
        }

    outputs = []
    for _, row in step5_players.iterrows():
        out = row.to_dict()
        stable36 = _num(row.get("FORM_STABILIZED_REB36"))
        season36 = _num(row.get("FORM_SEASON_REB36"))
        season_gp = _num(row.get("FORM_SEASON_GP"), 0.0)
        proj_min = _num(row.get("PROJ_MIN"), 0.0)

        covered = bool(
            season_gp >= 3
            and np.isfinite(stable36)
            and stable36 >= 0
            and proj_min >= 0
        )

        # Keep true tracking fields empty. These columns must never imply that
        # official Second Spectrum REB Chances were observed when they were not.
        out["OPP_SEASON_GP"] = np.nan
        out["OPP_SEASON_CHANCES"] = np.nan
        out["OPP_SEASON_CHANCES36"] = np.nan
        out["OPP_L10_CHANCES"] = np.nan
        out["OPP_L10_CHANCES36"] = np.nan
        out["OPP_STABLE_CHANCES36"] = np.nan
        out["OPP_MIN_SCALED_CHANCES"] = np.nan
        out["OPP_TRACKING_COVERED"] = False

        # Verified fallback descriptors. The future projection layer can use
        # these only as a lower-confidence baseline, never as true chances.
        out["OPP_BASELINE_REB36"] = stable36
        out["OPP_BASELINE_SEASON_REB36"] = season36
        out["OPP_BASELINE_MIN_SCALED_REB"] = (
            stable36 * proj_min / 36.0
            if np.isfinite(stable36) and proj_min > 0
            else np.nan
        )
        out["OPP_FALLBACK_COVERED"] = covered
        out["OPP_COVERED"] = covered
        out["OPP_SOURCE"] = "VERIFIED BOX-SCORE REBOUND BASELINE"
        out["OPP_TRACKING_SAMPLE"] = "TRACKING UNAVAILABLE • BASELINE VERIFIED" if covered else "CHECK"
        outputs.append(out)

    players = pd.DataFrame(outputs)
    modeled = players[
        pd.to_numeric(players.get("PROJ_MIN"), errors="coerce").fillna(0).ge(5.0)
    ].copy()

    team_rows = []
    if not modeled.empty:
        for team, part in modeled.groupby("TEAM_NAME", sort=False):
            total = int(len(part))
            covered = int(part["OPP_COVERED"].fillna(False).astype(bool).sum())
            team_rows.append({
                "Team": team,
                "Modeled ≥5 MIN": total,
                "Opportunity baseline covered": covered,
                "State": "VERIFIED FALLBACK" if total and covered == total else "CHECK",
            })
    teams = pd.DataFrame(team_rows)
    ready = bool(
        not modeled.empty
        and modeled["OPP_COVERED"].fillna(False).astype(bool).all()
    )

    blockers = pd.DataFrame()
    if not modeled.empty:
        blockers = modeled.loc[
            ~modeled["OPP_COVERED"].fillna(False).astype(bool),
            [c for c in ["PLAYER_NAME", "TEAM_NAME", "PROJ_MIN", "FORM_SEASON_GP", "FORM_STABILIZED_REB36"] if c in modeled.columns],
        ].copy()

    return players, teams, {
        "ready": ready,
        "mode": "FALLBACK",
        "tracking_available": False,
        "modeled_players": int(len(modeled)),
        "covered_players": int(modeled["OPP_COVERED"].fillna(False).astype(bool).sum()) if not modeled.empty else 0,
        "ready_teams": int(teams["State"].eq("VERIFIED FALLBACK").sum()) if not teams.empty else 0,
        "teams": int(len(teams)),
        "season_diag": {
            "ok": False,
            "host": "official tracking not queried on normal page load",
            "reason": "nonblocking mode",
        },
        "l10_diag": {
            "ok": False,
            "host": "official tracking not queried on normal page load",
            "reason": "nonblocking mode",
        },
        "blockers": blockers.to_dict("records") if not blockers.empty else [],
    }


def _resilient_build(step5_players: pd.DataFrame, day: str):
    """Use official tracking only after an explicit refresh request."""
    if st.session_state.pop("wnba_rebounds_force_official_tracking", False):
        try:
            players, teams, info = _RAW_BUILD(step5_players, day)
            if bool((info or {}).get("ready")):
                info = dict(info or {})
                info["mode"] = "OFFICIAL"
                info["tracking_available"] = True
                return players, teams, info
        except Exception as exc:
            st.session_state["wnba_rebounds_last_tracking_error"] = f"{type(exc).__name__}: {exc}"

    return _fallback_build(step5_players, day)


def _render_step6_resilient(day: str):
    records = st.session_state.get("wnba_rebounds_step5_players") or []
    frame = pd.DataFrame(records)

    st.markdown("## 🧲 Step 6 — Rebound Chances / Opportunities")
    st.caption(
        "Fast-path opportunity layer. Official Second Spectrum REB Chances remain the preferred source. "
        "Because the NBA/WNBA tracking hosts are timing out from Streamlit Cloud, normal page loads use "
        "the already-verified Step-5 rebound-rate baseline without pretending it is official REB Chances."
    )

    if st.button("🛰️ TRY OFFICIAL REBOUND-CHANCE REFRESH", key="wnba_reb_try_official_tracking"):
        st.session_state["wnba_rebounds_force_official_tracking"] = True
        # Invalidate only the Step-6 session snapshot so this explicit action
        # actually reaches the official hosts. Earlier verified layers stay hot.
        for key in (
            "wnba_rebounds_step6_signature",
            "wnba_rebounds_step6_snapshot_players",
            "wnba_rebounds_step6_snapshot_teams",
            "wnba_rebounds_step6_snapshot_info",
        ):
            st.session_state.pop(key, None)

    players, teams, info = step6_mod._build_step6(frame, day)
    st.session_state["wnba_rebounds_step6_players"] = players.to_dict("records") if not players.empty else []
    st.session_state["wnba_rebounds_step6_ready"] = bool(info.get("ready"))
    st.session_state["wnba_rebounds_step6_mode"] = str(info.get("mode") or "UNKNOWN")

    official = str(info.get("mode") or "").upper() == "OFFICIAL"
    a, b, c, d = st.columns(4)
    a.metric("Team opportunity checks", f"{info.get('ready_teams',0)}/{info.get('teams',0)}")
    b.metric("Modeled ≥5 MIN", info.get("modeled_players", 0))
    c.metric("Covered", info.get("covered_players", 0))
    d.metric("Source", "OFFICIAL" if official else "VERIFIED FALLBACK")

    if info.get("ready") and official:
        host = (info.get("season_diag") or {}).get("host", "official Stats")
        st.success(
            f"✅ STEP 6 PASSED • official rebound-chance tracking is verified via {host}. "
            "Step 7 (opponent missed-shot environment) is unlocked."
        )
    elif info.get("ready"):
        st.warning(
            "⚠️ STEP 6 PASSED IN RESILIENT MODE • official REB Chances are currently unavailable from "
            "Streamlit Cloud. Every modeled player has a verified box-score rebound baseline, so Step 7 is "
            "unlocked. This baseline is lower-confidence and is NOT labeled or treated as true REB Chances."
        )
    else:
        st.error(
            "⛔ STEP 6 CHECK • at least one modeled player lacks enough verified opportunity infrastructure. "
            "Step 7 remains locked."
        )

    if not teams.empty:
        st.dataframe(teams, hide_index=True, use_container_width=True)

    with st.expander("🧲 Player rebound-opportunity board"):
        if players.empty:
            st.info("No Step-6 player rows available.")
        else:
            modeled = players[
                pd.to_numeric(players.get("PROJ_MIN"), errors="coerce").fillna(0).ge(5.0)
            ].copy()
            if official:
                cols = [c for c in [
                    "PLAYER_NAME", "TEAM_NAME", "PROJ_MIN", "OPP_SEASON_GP",
                    "OPP_SEASON_CHANCES", "OPP_SEASON_CHANCES36", "OPP_L10_CHANCES36",
                    "OPP_STABLE_CHANCES36", "OPP_MIN_SCALED_CHANCES", "OPP_TRACKING_SAMPLE",
                ] if c in modeled.columns]
            else:
                cols = [c for c in [
                    "PLAYER_NAME", "TEAM_NAME", "PROJ_MIN", "FORM_SEASON_GP",
                    "OPP_BASELINE_SEASON_REB36", "OPP_BASELINE_REB36",
                    "OPP_BASELINE_MIN_SCALED_REB", "OPP_SOURCE", "OPP_TRACKING_SAMPLE",
                ] if c in modeled.columns]
            st.dataframe(modeled[cols], hide_index=True, use_container_width=True)

    if info.get("blockers"):
        with st.expander("🔎 Step-6 blockers"):
            st.dataframe(pd.DataFrame(info["blockers"]), hide_index=True, use_container_width=True)

    with st.expander("🛰️ Official tracking feed diagnostics"):
        st.json({
            "mode": info.get("mode"),
            "season": info.get("season_diag"),
            "L10": info.get("l10_diag"),
            "last_error": st.session_state.get("wnba_rebounds_last_tracking_error"),
        })

    st.markdown("## 🧱 Rebounds Build Order — Current")
    statuses = ["✅ LIVE"] * 5 + (["✅ LIVE", "➡️ NEXT"] if info.get("ready") else ["⚠️ ACTIVE / CHECK", "🔒 LOCKED"])
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
        pd.DataFrame({"Step": list(range(1, 8)), "Layer": layers, "Status": statuses}),
        hide_index=True,
        use_container_width=True,
    )


def render_wnba_rebounds_hub(*args, **kwargs):
    # Redirect V1.5.1's cached Step-6 builder to the resilient implementation,
    # and replace only the Step-6 renderer. Earlier verified layers are untouched.
    old_original = base._ORIGINAL_BUILD
    old_render = step6_mod._render_step6
    base._ORIGINAL_BUILD = _resilient_build
    step6_mod._render_step6 = _render_step6_resilient
    try:
        out = base.render_wnba_rebounds_hub(*args, **kwargs)
    finally:
        base._ORIGINAL_BUILD = old_original
        step6_mod._render_step6 = old_render

    mode = st.session_state.get("wnba_rebounds_step6_mode", "UNKNOWN")
    st.caption(
        f"⚡ V1.5.4 resilient Step-6 active • mode: {mode}. Normal page loads do not wait on timed-out "
        "tracking hosts; official tracking can be retried manually without rebuilding Steps 1–5."
    )
    return out


__all__ = ["MODEL_VERSION", "render_wnba_rebounds_hub"]
