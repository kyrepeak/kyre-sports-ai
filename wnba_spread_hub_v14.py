"""WNBA Spread V1.4 — Step 5 independent projected score and margin.

Preserves V1.3.1 exact spread verification. Adds a market-independent team model
using date-cut season/recent scoring, venue splits, recent pace/efficiency and
verified availability. Sportsbook lines/prices do not enter the projection.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

import wnba_spread_hub_v131 as step4_integrity
import wnba_spread_projection_v14 as projection

ui = step4_integrity.base
foundation = ui.foundation
clock = ui.prior
ET = ui.ET
MODEL_VERSION = "WNBA SPREAD V1.4 • INDEPENDENT PROJECTED MARGIN"

# Keep the hardened V1.3.1 market adapter installed for Step 4.
ui._spread_market_snapshot = step4_integrity.market.spread_market_snapshot


def _fmt(value, digits=1):
    try:
        x = float(value)
        if np.isfinite(x):
            return f"{x:.{digits}f}"
    except Exception:
        pass
    return "—"


def _render_step5(day_str: str, pregame: pd.DataFrame, contexts: dict, market_ready: bool):
    st.markdown("### 🧠 Step 5 — Independent Projected Score + Margin")
    st.caption(
        "Verified team data only • season scoring matchup + L10 scoring matchup + home/road splits + "
        "recent pace/efficiency + current availability. H2H stays descriptive. Sportsbook line/price input = ZERO."
    )

    if pregame is None or pregame.empty:
        st.info("ℹ️ STEP 5 NOT APPLICABLE • no clock-safe pregame games remain.")
        return pd.DataFrame(), {"state": "N/A", "games": 0, "projected": 0, "ready": 0, "monitor": 0, "blocked": 0, "sportsbook_inputs": 0, "model_ready": False}
    if not market_ready:
        st.warning("🔒 STEP 5 LOCKED • exact current sportsbook spread coverage must pass Step 4 first. The market still never enters the projection math.")
        return pd.DataFrame(), {"state": "LOCKED", "games": int(len(pregame)), "projected": 0, "ready": 0, "monitor": 0, "blocked": 0, "sportsbook_inputs": 0, "model_ready": False}

    with st.spinner("🧠 Building market-independent WNBA projected scores + margins…"):
        frame, meta = projection.project_slate(day_str, pregame, contexts)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Games projected", f"{int(meta.get('projected',0))}/{int(meta.get('games',0))}")
    c2.metric("READY", int(meta.get("ready", 0)))
    c3.metric("MONITOR", int(meta.get("monitor", 0)))
    c4.metric("Sportsbook inputs", int(meta.get("sportsbook_inputs", 0)))

    model_ready = bool(str(meta.get("state") or "CHECK").upper() == "READY")
    if model_ready:
        st.success("✅ STEP 5 PASSED • every pregame game has an independent projected score/margin; sportsbook lines and prices were not model inputs.")
        if int(meta.get("monitor", 0)):
            st.info(f"🟦 {int(meta.get('monitor',0))} projection(s) are MONITOR because of availability/data-layer uncertainty. They remain visible for Step-6 scenario handling.")
    else:
        st.warning("⚠️ STEP 5 CHECK • at least one game cannot produce a trustworthy independent margin. Step 6 remains locked.")

    if frame is not None and not frame.empty:
        show = frame.copy()
        show["Game"] = show["away_team"].astype(str) + " @ " + show["home_team"].astype(str)
        show["Projected score"] = show.apply(
            lambda r: f"{r.get('away_team')} {_fmt(r.get('away_score'))} — {r.get('home_team')} {_fmt(r.get('home_score'))}", axis=1
        )
        show["Projected margin"] = show.apply(
            lambda r: "Even" if str(r.get("winner")) == "Even" else f"{r.get('winner')} by {_fmt(r.get('winner_margin'))}", axis=1
        )
        show["Availability adj"] = show.apply(
            lambda r: f"away -{_fmt(r.get('away_out_impact'))} / home -{_fmt(r.get('home_out_impact'))}", axis=1
        )
        cols = ["Game", "first_tip_et", "Projected score", "Projected margin", "components", "Availability adj", "state"]
        st.dataframe(
            show[cols].rename(columns={"first_tip_et":"Tip ET", "components":"Model layers", "state":"State"}),
            use_container_width=True,
            hide_index=True,
        )

        with st.expander("🔬 Step 5 projection audit — model components", expanded=False):
            audit = show.copy()
            audit["Season matchup"] = audit.apply(lambda r: f"{_fmt(r.get('season_away'))} / {_fmt(r.get('season_home'))}", axis=1)
            audit["L10 matchup"] = audit.apply(lambda r: f"{_fmt(r.get('recent_away'))} / {_fmt(r.get('recent_home'))}", axis=1)
            audit["Venue matchup"] = audit.apply(lambda r: f"{_fmt(r.get('venue_away'))} / {_fmt(r.get('venue_home'))}", axis=1)
            audit["Advanced matchup"] = audit.apply(lambda r: f"{_fmt(r.get('advanced_away'))} / {_fmt(r.get('advanced_home'))}", axis=1)
            audit["Venue samples"] = audit.apply(lambda r: f"road {int(r.get('away_road_gp',0) or 0)} / home {int(r.get('home_home_gp',0) or 0)}", axis=1)
            audit["OUT / uncertain"] = audit.apply(lambda r: f"{int(r.get('hard_out',0) or 0)} / {int(r.get('uncertain',0) or 0)}", axis=1)
            audit["Market inputs"] = audit.get("sportsbook_inputs", 0)
            st.dataframe(
                audit[["Game", "Season matchup", "L10 matchup", "Venue matchup", "Advanced matchup", "Venue samples", "OUT / uncertain", "Market inputs", "State"]],
                use_container_width=True,
                hide_index=True,
            )
            st.caption("Component values are projected away/home points before the final blend. H2H and sportsbook spreads are not projection multipliers.")

    meta = dict(meta)
    meta["model_ready"] = model_ready
    return frame, meta


def render_wnba_spread_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.markdown("## 🏀 WNBA Spread Command Center")
    st.caption(
        "V1.4 • verified slate → clock-safe pregame guard → team context → current availability → exact spread verification → "
        "independent projected score/margin. Cover probability and Monte Carlo remain OFF."
    )

    default_day = st.session_state.get("wnba_spread_v1_date") or pd.Timestamp.now(tz=ET).date()
    selected = st.date_input("Spread slate date", value=pd.to_datetime(default_day).date(), key="wnba_spread_v1_date_picker")
    st.session_state["wnba_spread_v1_date"] = selected
    day_str = foundation._day(selected)
    now_et = pd.Timestamp.now(tz=ET)

    with st.spinner("📅 Verifying WNBA spread slate + clock-safe pregame eligibility…"):
        schedule = foundation._schedule(day_str)
        pregame = clock._pregame_schedule(schedule, now_et=now_et)
        excluded = clock._excluded_schedule(schedule, now_et=now_et)

    teams = 0
    if not schedule.empty:
        tids = set()
        for col in ("away_team_id", "home_team_id"):
            if col in schedule.columns:
                tids.update(pd.to_numeric(schedule[col], errors="coerce").dropna().astype(int).tolist())
        teams = len(tids)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Slate games", int(len(schedule)))
    c2.metric("Pregame eligible", int(len(pregame)))
    c3.metric("Excluded / locked", int(len(excluded)))
    c4.metric("Model state", "STEP 5")
    st.caption(f"Pregame eligibility clock • {now_et.strftime('%Y-%m-%d %I:%M:%S %p ET')}")

    if schedule.empty:
        st.warning("No verified WNBA games were returned for this Eastern-date slate. Nothing is projected or fabricated.")
        return

    st.success(f"✅ STEP 1 PASSED • verified WNBA slate loaded for {day_str}.")
    if len(pregame):
        st.success(f"✅ PREGAME ELIGIBILITY PASSED • {len(pregame)} game(s) are still before scheduled tip and provider-safe.")
    else:
        st.info("ℹ️ No games on this slate remain pregame-eligible. Passed-tip/live/final/uncertain-tip games are locked out.")

    if not excluded.empty:
        with st.expander("🚫 Games excluded from pregame production", expanded=True):
            cols = [c for c in ["away_team", "home_team", "first_tip_et", "scheduled_tip_guard_et", "status", "status_text", "exclusion_reason"] if c in excluded.columns]
            st.dataframe(excluded[cols] if cols else excluded, use_container_width=True, hide_index=True)

    with st.spinner("📊 Building verified team form + matchup context…"):
        try:
            contexts, cdiag = foundation.context.slate_context(day_str)
        except Exception as exc:
            contexts, cdiag = {}, {"state": "CHECK", "reason": type(exc).__name__}

    context_state = str(cdiag.get("state") or "CHECK").upper()
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Context state", context_state)
    d2.metric("Records verified", f"{int(cdiag.get('records_verified',0) or 0)}/{int(cdiag.get('teams',teams) or teams)}")
    d3.metric("Advanced teams", int(cdiag.get("advanced_teams", 0) or 0))
    d4.metric("H2H samples", int(cdiag.get("h2h_samples", 0) or 0))
    if context_state == "VERIFIED":
        st.success("✅ STEP 2 PASSED • team records/recent form are verified; advanced pace/ratings are used only where real samples exist.")
    else:
        st.warning("⚠️ STEP 2 CHECK • some team context is incomplete. Missing advanced fields remain neutral/missing; nothing is invented.")

    with st.spinner("🩺 Verifying current team availability for pregame-eligible games…"):
        av = foundation._availability_snapshot(day_str, pregame)
    av_map = {str(r.get("game_id") or ""): r.to_dict() for _, r in av.iterrows()} if not av.empty else {}
    covered = int(pd.to_numeric(av.get("covered_teams", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if not av.empty else 0
    expected_coverage = int(2 * len(pregame))
    unverified = int(pd.to_numeric(av.get("unverified", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if not av.empty else 0
    a1, a2, a3, a4 = st.columns(4)
    a1.metric("Availability coverage", f"{covered}/{expected_coverage}" if expected_coverage else "0/0")
    a2.metric("Hard OUT", int(pd.to_numeric(av.get("hard_out", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if not av.empty else 0)
    a3.metric("Status uncertain", int(pd.to_numeric(av.get("uncertain", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if not av.empty else 0)
    a4.metric("Unverified players", unverified)
    availability_ready = bool(expected_coverage > 0 and covered == expected_coverage and unverified == 0)
    if availability_ready:
        st.success("✅ STEP 3 PASSED • current availability coverage is complete for every pregame-eligible game.")
    elif expected_coverage == 0:
        st.info("ℹ️ STEP 3 NOT APPLICABLE • there are no remaining pregame-eligible games on this slate.")
    else:
        st.warning("⚠️ STEP 3 CHECK • availability is not fully verified for every pregame-eligible game. Future spread production remains locked.")

    st.markdown("### 🧩 Pregame-Eligible Game Foundation")
    if pregame.empty:
        st.info("No pregame-eligible games remain to display.")
    else:
        for _, game in pregame.iterrows():
            foundation._render_game_context(game, contexts, av_map)

    foundation_ready = bool(len(pregame) and context_state == "VERIFIED" and availability_ready)
    ready_lines, step4 = ui._render_step4(day_str, pregame, foundation_ready)
    market_ready = bool(step4.get("market_ready", False))

    projected, step5 = _render_step5(day_str, pregame, contexts, market_ready)
    model_ready = bool(step5.get("model_ready", False))

    st.markdown("### 🔒 Spread Production Locks")
    locks = pd.DataFrame([
        {"Layer": "Verified slate", "State": "READY" if len(schedule) else "CHECK"},
        {"Layer": "Clock-safe pregame eligibility", "State": "READY" if len(pregame) else "NO ELIGIBLE GAMES"},
        {"Layer": "Team context", "State": "READY" if context_state == "VERIFIED" else "CHECK"},
        {"Layer": "Current availability", "State": "READY" if availability_ready else ("N/A" if not len(pregame) else "CHECK")},
        {"Layer": "Exact sportsbook spread line", "State": "READY" if market_ready else ("N/A" if not len(pregame) else "CHECK")},
        {"Layer": "Projected game margin", "State": "READY" if model_ready else ("N/A" if not len(pregame) else "CHECK")},
        {"Layer": "Cover probability / fair spread", "State": "NEXT" if model_ready else "LOCKED"},
        {"Layer": "5M Monte Carlo", "State": "OFF"},
        {"Layer": "Daily Picks connector", "State": "OFF"},
    ])
    st.dataframe(locks, use_container_width=True, hide_index=True)
    st.info(
        "V1.4 produces an independent projected score and game margin only. The sportsbook line is verified in Step 4 but is not an input to Step 5. "
        "Cover probability / fair spread is the next layer."
    )


__all__ = ["MODEL_VERSION", "_render_step5", "render_wnba_spread_hub"]
