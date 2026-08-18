"""WNBA Points V1.7 — production preflight with verified empirical history gate."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

import wnba_points_v14 as points
import wnba_schedule_v25 as schedule


def _load_ui_base():
    module_path = Path(__file__).with_name("wnba_points_hub_v13.py")
    spec = importlib.util.spec_from_file_location("_kyre_wnba_points_ui_base_v17", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load isolated WNBA Points UI helper.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ui = _load_ui_base()
ui.points = points
ui.schedule = schedule

MODEL_VERSION = "WNBA POINTS V1.7 • EMPIRICAL HISTORY PREFLIGHT"
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
        needed = [c for c in ("game_id", "player_key", "line") if c in current.columns]
        distributions = int(current[needed].drop_duplicates().shape[0]) if needed else 0

    st.markdown("""
<div style="border:1px solid #2f6381;background:linear-gradient(145deg,#091c2d,#071421);border-radius:20px;padding:16px;margin:8px 0 14px">
  <div style="font-size:10px;letter-spacing:1.35px;font-weight:950;color:#65dcff">KYRE SPORTS AI • WNBA POINTS • ISOLATED PRODUCTION PAGE</div>
  <div style="font-size:30px;font-weight:1000;color:white;margin-top:5px">🏀 WNBA Points Command Center — V1.7</div>
  <div style="font-size:12px;color:#93aabd;line-height:1.55;margin-top:7px">Four-game Eastern-time slate + verified current rosters + explicit player game-log variance + matchup context + SportsGameOdds. The 5M pass cannot run with a broken established-player history handoff. PRA V3.2.1 and MLB V2.1.7 remain frozen.</div>
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
        if official == teams and missing == 0 and proxy == 0:
            st.success("✅ CURRENT ROSTER GATE VERIFIED • every slate team has a compact current-roster feed.")
        elif missing == 0 and proxy > 0:
            st.warning("⚠️ ROSTER PROXY ACTIVE • the 5M pass stays locked until all current rosters are verified.")
        else:
            st.error("⛔ ROSTER GATE INCOMPLETE • one or more slate teams do not have a safe current-roster source.")
    return pool, pdiag, cdiag


def _matched_unique(day):
    try:
        projections, pairs, _, _, lineups = points._prepare(day)
    except Exception:
        return pd.DataFrame(), {}
    if not isinstance(projections, pd.DataFrame) or projections.empty or not isinstance(pairs, pd.DataFrame) or pairs.empty:
        return pd.DataFrame(), lineups if isinstance(lineups, dict) else {}
    pcols = [c for c in projections.columns]
    p = projections[pcols].copy()
    q = pairs[[c for c in ("game_id", "player_key") if c in pairs.columns]].drop_duplicates().copy()
    if len(q.columns) < 2:
        return pd.DataFrame(), lineups if isinstance(lineups, dict) else {}
    p["game_id"] = p["game_id"].astype(str)
    p["player_key"] = p["player_key"].astype(str)
    q["game_id"] = q["game_id"].astype(str)
    q["player_key"] = q["player_key"].astype(str)
    return q.merge(p, on=["game_id", "player_key"], how="inner").drop_duplicates(["game_id", "player_key"]), lineups if isinstance(lineups, dict) else {}


def _history_gate(day):
    matched, lineups = _matched_unique(day)
    if matched.empty:
        return {"expected": 0, "verified": 0, "short_sample": 0, "missing": 0, "ready": False, "sanity": []}

    expected = verified = short_sample = missing = 0
    sanity = []
    for _, row in matched.iterrows():
        gid = str(row.get("game_id") or "")
        _, _, dmeta = points._points_distribution(row, bool(lineups.get(gid, False)))
        hist_games = int(dmeta.get("hist_games") or 0)
        gp = pd.to_numeric(pd.Series([row.get("GP")]), errors="coerce").iloc[0]
        established = bool(pd.isna(gp) or float(gp) >= 5.0)
        if established:
            expected += 1
            if hist_games >= 5:
                verified += 1
            else:
                missing += 1
        else:
            short_sample += 1

        hist_mean = dmeta.get("hist_pts_mean")
        proj = pd.to_numeric(pd.Series([row.get("PROJ_PTS")]), errors="coerce").iloc[0]
        if hist_games >= 5 and pd.notna(hist_mean) and float(hist_mean) >= 6.0 and pd.notna(proj):
            ratio = float(proj) / max(float(hist_mean), 1.0)
            if ratio < 0.65 or ratio > 1.35:
                sanity.append({
                    "Player": str(row.get("PLAYER_NAME") or "Player"),
                    "Proj PTS": round(float(proj), 2),
                    "Hist PTS": round(float(hist_mean), 2),
                    "Ratio": round(ratio, 2),
                })

    return {
        "expected": expected, "verified": verified, "short_sample": short_sample,
        "missing": missing, "ready": bool(expected > 0 and missing == 0), "sanity": sanity,
    }


def _readiness_snapshot(day, pdiag):
    info = ui._readiness_snapshot(day)
    teams = int(pdiag.get("teams") or 0)
    official = int(pdiag.get("official_roster_teams") or 0)
    proxy = int(pdiag.get("proxy_roster_teams") or 0)
    missing_roster = int(pdiag.get("missing_roster_teams") or 0)
    roster_ready = bool(teams > 0 and official == teams and proxy == 0 and missing_roster == 0)
    history = _history_gate(day)
    info["roster_ready"] = roster_ready
    info["history_gate"] = history
    info["ready"] = bool(info.get("ready") and roster_ready and history.get("ready"))
    return info


def _render_integrity(info):
    h = info.get("history_gate") or {}
    st.markdown("### 🧬 Points History Integrity")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Established players", h.get("expected", 0))
    c2.metric("Verified ≥5 GP logs", f"{h.get('verified',0)}/{h.get('expected',0)}")
    c3.metric("Legit short samples", h.get("short_sample", 0))
    c4.metric("History misses", h.get("missing", 0))
    if h.get("ready"):
        st.success("✅ EMPIRICAL HISTORY GATE PASSED • established matched players have verified prior-game scoring logs.")
    else:
        st.error("⛔ EMPIRICAL HISTORY GATE NOT READY • do not run 5M while an established matched player is missing verified game-log variance.")
    sanity = h.get("sanity") or []
    if sanity:
        st.warning(f"⚠️ Projection sanity review: {len(sanity)} player(s) are >35% away from their verified scoring history mean. This does not use sportsbook lines and does not automatically change the projection.")
        with st.expander("🔎 Projection sanity review", expanded=False):
            st.dataframe(pd.DataFrame(sanity), use_container_width=True, hide_index=True)
    else:
        st.caption("✅ No extreme >35% projection-vs-verified-history deviations detected.")


def render_wnba_points_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.caption("🏀 WNBA Points V1.7 • empirical history preflight • strict current rosters • PRA V3.2.1 frozen • MLB V2.1.7 frozen")
    selected = st.date_input("WNBA Points slate date", value=ui._default_day(), key="wnba_points_date_control")
    day = ui._day_string(selected)
    st.session_state["wnba_points_date"] = day

    slate = ui._slate_snapshot(day)
    _render_header(day, slate)
    ui._render_slate(slate)
    _, pdiag, _ = _render_data_handoff(day)

    readiness = _readiness_snapshot(day, pdiag)
    ui._render_readiness(readiness)
    _render_integrity(readiness)

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
        })

    with st.expander("🧊 Freeze / isolation status", expanded=False):
        st.write(f"PRA checkpoint: `{PRA_FROZEN_BRANCH}` @ `{PRA_FROZEN_COMMIT[:12]}`")
        st.write(f"MLB checkpoint: `{MLB_FROZEN_BRANCH}`")
        st.write("Points V1.7 changes only the isolated Points history/preflight chain. Frozen PRA and MLB production modules are unchanged.")

    ui._render_production(day, readiness)
    if readiness.get("ready"):
        st.success("🚀 POINTS PREFLIGHT PASSED • run the 5,000,000 standard simulation once. Completed summaries will persist across reloads/redeploys.")
    else:
        st.info("The 5M button stays disabled until schedule, roster, projection, exact-market and established-player empirical-history gates all pass.")


__all__ = ["MODEL_VERSION", "PRA_FROZEN_BRANCH", "PRA_FROZEN_COMMIT", "MLB_FROZEN_BRANCH", "render_wnba_points_hub"]
