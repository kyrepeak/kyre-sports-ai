"""WNBA Points V1.6 — clean four-game command center with strict roster gate."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import streamlit as st

import wnba_points_v13 as points
import wnba_schedule_v25 as schedule


def _load_ui_base():
    module_path = Path(__file__).with_name("wnba_points_hub_v13.py")
    spec = importlib.util.spec_from_file_location("_kyre_wnba_points_ui_base_v16", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load isolated WNBA Points UI helper.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ui = _load_ui_base()
ui.points = points
ui.schedule = schedule

MODEL_VERSION = "WNBA POINTS V1.6 • STRICT ROSTER PREFLIGHT"
PRA_FROZEN_BRANCH = ui.PRA_FROZEN_BRANCH
PRA_FROZEN_COMMIT = ui.PRA_FROZEN_COMMIT
MLB_FROZEN_BRANCH = ui.MLB_FROZEN_BRANCH


def _player_diag(day):
    try:
        pool, diag = points.corrected_player_pool(day)
    except Exception as exc:
        return pd.DataFrame(), {"state": "ERROR", "error": f"{type(exc).__name__}: {exc}"}
    return pool if isinstance(pool, pd.DataFrame) else pd.DataFrame(), diag if isinstance(diag, dict) else {}


def _render_header(day, slate):
    current = points.combined_rows(day)
    distributions = 0
    if isinstance(current, pd.DataFrame) and not current.empty:
        distributions = int(current[["game_id", "player_key", "line"]].drop_duplicates().shape[0])

    st.markdown("""
<div style="border:1px solid #2f6381;background:linear-gradient(145deg,#091c2d,#071421);border-radius:20px;padding:16px;margin:8px 0 14px">
  <div style="font-size:10px;letter-spacing:1.35px;font-weight:950;color:#65dcff">KYRE SPORTS AI • WNBA POINTS • ISOLATED PRODUCTION PAGE</div>
  <div style="font-size:30px;font-weight:1000;color:white;margin-top:5px">🏀 WNBA Points Command Center — V1.6</div>
  <div style="font-size:12px;color:#93aabd;line-height:1.55;margin-top:7px">Four-game Eastern-time slate + strict current-roster gate + matchup context + SportsGameOdds. Historical players cannot enter the Points model just because they appeared earlier in the season. PRA V3.2.1 and MLB V2.1.7 remain frozen.</div>
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
    pool, pdiag = _player_diag(day)
    try:
        _, cdiag = points.corrected_contexts(day)
    except Exception as exc:
        cdiag = {"state": "ERROR", "error": f"{type(exc).__name__}: {exc}"}

    teams = int(pdiag.get("teams") or 0)
    official = int(pdiag.get("official_roster_teams") or 0)
    proxy = int(pdiag.get("proxy_roster_teams") or 0)
    missing = int(pdiag.get("missing_roster_teams") or 0)

    with st.expander("🧩 Four-game data handoff", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Slate teams", teams)
        c2.metric("Current roster players", len(pool))
        c3.metric("Official roster teams", f"{official}/{teams}" if teams else "0/0")
        c4.metric("Context games", int(cdiag.get("games") or 0))
        st.caption(
            f"Roster coverage: {official + proxy}/{teams} • official {official} • recent proxy {proxy} • missing {missing} • "
            f"context teams {cdiag.get('teams',0)}/{teams} • player source: {pdiag.get('source','—')}"
        )
        if official == teams and missing == 0:
            st.success("✅ CURRENT ROSTER GATE VERIFIED • every slate team has a compact current-roster feed.")
        elif missing == 0 and proxy > 0:
            st.warning("⚠️ ROSTER PROXY ACTIVE • historical season-wide players are blocked, but at least one team is using a recent-active proxy. 5M stays locked until current rosters are verified.")
        else:
            st.error("⛔ ROSTER GATE INCOMPLETE • one or more slate teams do not have a safe current-roster source.")
        if pdiag.get("error"):
            st.error(str(pdiag.get("error")))
        if cdiag.get("error"):
            st.error(str(cdiag.get("error")))

    return pool, pdiag, cdiag


def _readiness_snapshot(day, pdiag):
    info = ui._readiness_snapshot(day)
    teams = int(pdiag.get("teams") or 0)
    official = int(pdiag.get("official_roster_teams") or 0)
    proxy = int(pdiag.get("proxy_roster_teams") or 0)
    missing = int(pdiag.get("missing_roster_teams") or 0)
    roster_ready = bool(teams > 0 and official == teams and proxy == 0 and missing == 0)
    info["roster_ready"] = roster_ready
    info["roster_teams"] = teams
    info["official_roster_teams"] = official
    info["proxy_roster_teams"] = proxy
    info["missing_roster_teams"] = missing
    if not roster_ready:
        info["ready"] = False
        if not info.get("error"):
            info["error"] = (
                f"Current-roster gate not fully verified: official {official}/{teams}, "
                f"proxy {proxy}, missing {missing}."
            )
    return info


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.caption("🏀 WNBA Points V1.6 • strict current-roster gate • 4-game ET slate • PRA V3.2.1 frozen • MLB V2.1.7 frozen")

    selected = st.date_input("WNBA Points slate date", value=ui._default_day(), key="wnba_points_date_control")
    day = ui._day_string(selected)
    st.session_state["wnba_points_date"] = day

    slate = ui._slate_snapshot(day)
    _render_header(day, slate)
    ui._render_slate(slate)
    _, pdiag, _ = _render_data_handoff(day)

    readiness = _readiness_snapshot(day, pdiag)
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
        st.write("Points V1.6 owns its schedule/player/context adapters. Frozen PRA and MLB production modules are unchanged.")

    ui._render_production(day, readiness)
    st.caption("The Points 5M button unlocks only after the four-game slate, exact Points markets, projection coverage and strict current-roster gate all pass.")


__all__ = ["MODEL_VERSION", "render_wnba_points_hub"]
