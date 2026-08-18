"""WNBA Points V1.5 — clean four-game page with corrected player/context handoff."""
from __future__ import annotations

import pandas as pd
import streamlit as st

import wnba_points_hub_v13 as ui
import wnba_points_v12 as points
import wnba_schedule_v25 as schedule

MODEL_VERSION = "WNBA POINTS V1.5 • FULL 4-GAME PREFLIGHT"
PRA_FROZEN_BRANCH = ui.PRA_FROZEN_BRANCH
PRA_FROZEN_COMMIT = ui.PRA_FROZEN_COMMIT
MLB_FROZEN_BRANCH = ui.MLB_FROZEN_BRANCH

# Patch only the isolated Points page globals.
ui.points = points
ui.schedule = schedule


def _render_header(day, slate):
    current = points.combined_rows(day)
    distributions = 0
    if isinstance(current, pd.DataFrame) and not current.empty:
        distributions = int(current[["game_id", "player_key", "line"]].drop_duplicates().shape[0])

    st.markdown("""
<div style="border:1px solid #2f6381;background:linear-gradient(145deg,#091c2d,#071421);border-radius:20px;padding:16px;margin:8px 0 14px">
  <div style="font-size:10px;letter-spacing:1.35px;font-weight:950;color:#65dcff">KYRE SPORTS AI • WNBA POINTS • ISOLATED PRODUCTION PAGE</div>
  <div style="font-size:30px;font-weight:1000;color:white;margin-top:5px">🏀 WNBA Points Command Center — V1.5</div>
  <div style="font-size:12px;color:#93aabd;line-height:1.55;margin-top:7px">One corrected four-game slate now drives schedule, current players, matchup context, availability, SportsGameOdds matching and simulation readiness. PRA V3.2.1 and MLB V2.1.7 remain frozen.</div>
</div>
""", unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Slate games", slate["total"])
    c2.metric("Upcoming", slate["upcoming"])
    c3.metric("Points market players", 0 if slate["pairs"].empty else int(slate["pairs"]["player_key"].nunique()))
    c4.metric("5M distributions", distributions)

    diag = slate.get("diag") or {}
    state = str(diag.get("state") or "UNKNOWN").upper()
    if state in {"VERIFIED", "VERIFIED_SINGLE_SOURCE", "VERIFIED_OFF_DAY"}:
        st.success(f"✅ Verified WNBA slate • {day} • all {slate['total']} game(s) shown • slate date = Eastern Time")
    else:
        st.warning(f"⚠️ WNBA schedule state: {state}")
    counts = diag.get("source_selected_counts") or {}
    if counts:
        st.caption("🧭 Schedule cross-check — " + " • ".join(f"{name}: {count}" for name, count in counts.items()))


def _render_data_handoff(day):
    try:
        pool, pdiag = points.corrected_player_pool(day)
    except Exception as exc:
        pool, pdiag = pd.DataFrame(), {"state": "ERROR", "error": str(exc)}
    try:
        contexts, cdiag = points.corrected_contexts(day)
    except Exception as exc:
        contexts, cdiag = {}, {"state": "ERROR", "error": str(exc)}

    with st.expander("🧩 Four-game data handoff", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Slate teams", pdiag.get("teams", 0))
        c2.metric("Current player rows", 0 if pool is None else len(pool))
        c3.metric("Context teams", cdiag.get("teams", 0))
        c4.metric("Context games", cdiag.get("games", 0))
        st.caption(f"Player source: {pdiag.get('source','—')} • Context state: {cdiag.get('state','—')}")


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.caption("🏀 WNBA Points V1.5 • full 4-game handoff • PRA V3.2.1 frozen • SportsGameOdds WNBA • MLB V2.1.7 frozen")

    selected = st.date_input("WNBA Points slate date", value=ui._default_day(), key="wnba_points_date_control")
    day = ui._day_string(selected)
    st.session_state["wnba_points_date"] = day

    slate = ui._slate_snapshot(day)
    _render_header(day, slate)
    ui._render_slate(slate)
    _render_data_handoff(day)

    readiness = ui._readiness_snapshot(day)
    ui._render_readiness(readiness)

    with st.expander("🧭 Schedule verification details", expanded=False):
        diag = slate.get("diag") or {}
        st.write({
            "slate_date": day,
            "timezone_rule": diag.get("timezone_rule") or "America/New_York",
            "verified_games": diag.get("games"),
            "teams": diag.get("teams"),
            "source_selected_counts": diag.get("source_selected_counts"),
            "chosen_source": diag.get("chosen_source"),
            "confirming_sources": diag.get("confirming_sources"),
            "rejected_single_source_matchups": diag.get("rejected_single_source_matchups"),
        })

    with st.expander("🧊 Freeze / isolation status", expanded=False):
        st.write(f"PRA checkpoint: `{PRA_FROZEN_BRANCH}` @ `{PRA_FROZEN_COMMIT[:12]}`")
        st.write(f"MLB checkpoint: `{MLB_FROZEN_BRANCH}`")
        st.write("Points owns its corrected schedule/player/context adapters. Frozen PRA and MLB production modules are unchanged.")

    ui._render_production(day, readiness)
    st.caption("Validate the four-game Points preflight first. Only after coverage, 5M diagnostics, persistence and decision gates pass will Points feed the shared WNBA Daily Master Card.")


__all__ = ["MODEL_VERSION", "PRA_FROZEN_BRANCH", "PRA_FROZEN_COMMIT", "MLB_FROZEN_BRANCH", "render_wnba_points_hub"]
