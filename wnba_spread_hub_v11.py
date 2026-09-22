"""WNBA Spread V1.1 — pregame eligibility guard on the verified V1.0 foundation.

V1.1 preserves every V1.0 data source and descriptive calculation, but fixes one
important production-boundary issue: LIVE / in-progress games are no longer
counted as pregame-eligible spread games. The full verified slate remains visible,
while only official pregame statuses may advance toward sportsbook spread grading
and future Monte Carlo.

No spread projection, sportsbook grading, cover probability, or Monte Carlo math
is introduced here.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

import wnba_spread_hub_v10 as base

MODEL_VERSION = "WNBA SPREAD V1.1 • VERIFIED FOUNDATION + PREGAME ELIGIBILITY GUARD"
ET = base.ET


def _status_series(schedule: pd.DataFrame) -> pd.Series:
    if schedule is None or schedule.empty:
        return pd.Series(dtype=object)
    return schedule.get(
        "status",
        schedule.get("status_text", pd.Series("", index=schedule.index)),
    ).astype(str).str.upper().str.strip()


def _pregame_schedule(schedule: pd.DataFrame) -> pd.DataFrame:
    """Return only games still eligible for a pregame spread model."""
    if schedule is None or schedule.empty:
        return pd.DataFrame(columns=getattr(schedule, "columns", None))
    status = _status_series(schedule)
    blocked = (
        status.str.contains("FINAL", na=False)
        | status.str.contains("LIVE", na=False)
        | status.str.contains("IN PROGRESS", na=False)
        | status.str.contains("IN_PROGRESS", na=False)
        | status.str.contains("HALFTIME", na=False)
        | status.str.contains("END OF", na=False)
        | status.str.match(r"^(Q[1-4]|OT|[1-4](ST|ND|RD|TH))\b", na=False)
    )
    return schedule.loc[~blocked].copy().reset_index(drop=True)


def _excluded_schedule(schedule: pd.DataFrame) -> pd.DataFrame:
    if schedule is None or schedule.empty:
        return pd.DataFrame(columns=getattr(schedule, "columns", None))
    pre = _pregame_schedule(schedule)
    keep_ids = set(pre.get("game_id", pd.Series(dtype=object)).astype(str).tolist())
    if "game_id" not in schedule.columns:
        return schedule.iloc[0:0].copy()
    return schedule.loc[~schedule["game_id"].astype(str).isin(keep_ids)].copy().reset_index(drop=True)


def render_wnba_spread_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.markdown("## 🏀 WNBA Spread Command Center")
    st.caption(
        "V1.1 foundation • verified slate → PRE-GAME eligibility guard → team strength/context → current availability. "
        "LIVE/final games are display-only and can never enter the future pregame spread model."
    )

    default_day = st.session_state.get("wnba_spread_v1_date") or pd.Timestamp.now(tz=ET).date()
    selected = st.date_input(
        "Spread slate date",
        value=pd.to_datetime(default_day).date(),
        key="wnba_spread_v1_date_picker",
    )
    st.session_state["wnba_spread_v1_date"] = selected
    day_str = base._day(selected)

    with st.spinner("📅 Verifying WNBA spread slate + pregame eligibility…"):
        schedule = base._schedule(day_str)
        pregame = _pregame_schedule(schedule)
        excluded = _excluded_schedule(schedule)

    teams = 0
    if not schedule.empty:
        team_ids = set()
        for col in ("away_team_id", "home_team_id"):
            if col in schedule.columns:
                team_ids.update(pd.to_numeric(schedule[col], errors="coerce").dropna().astype(int).tolist())
        teams = len(team_ids)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Slate games", int(len(schedule)))
    c2.metric("Pregame eligible", int(len(pregame)))
    c3.metric("Excluded live/final", int(len(excluded)))
    c4.metric("Model state", "FOUNDATION")

    if schedule.empty:
        st.warning("No verified WNBA games were returned for this Eastern-date slate. Nothing is projected or fabricated.")
        return

    st.success(f"✅ STEP 1 PASSED • verified WNBA slate loaded for {day_str}.")
    if len(pregame):
        st.success(f"✅ PREGAME ELIGIBILITY PASSED • {len(pregame)} game(s) remain eligible for future pregame spread production.")
    else:
        st.info("ℹ️ No games on this slate remain pregame-eligible. LIVE/final games are intentionally excluded from future pregame spread production.")

    if not excluded.empty:
        with st.expander("🚫 Games excluded from pregame production", expanded=False):
            cols = [c for c in ["away_team", "home_team", "first_tip_et", "status", "status_text"] if c in excluded.columns]
            show = excluded[cols].copy() if cols else excluded.copy()
            st.dataframe(show, use_container_width=True, hide_index=True)

    with st.spinner("📊 Building verified team form + matchup context…"):
        try:
            contexts, cdiag = base.context.slate_context(day_str)
        except Exception as exc:
            contexts, cdiag = {}, {"state": "CHECK", "reason": type(exc).__name__}

    state = str(cdiag.get("state") or "CHECK").upper()
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Context state", state)
    d2.metric("Records verified", f"{int(cdiag.get('records_verified',0) or 0)}/{int(cdiag.get('teams',teams) or teams)}")
    d3.metric("Advanced teams", int(cdiag.get("advanced_teams", 0) or 0))
    d4.metric("H2H samples", int(cdiag.get("h2h_samples", 0) or 0))

    if state == "VERIFIED":
        st.success("✅ STEP 2 PASSED • team records/recent form are verified; advanced pace/ratings are used only where real samples exist.")
    else:
        st.warning("⚠️ STEP 2 CHECK • some team context is incomplete. Missing advanced fields remain neutral/missing; nothing is invented.")

    with st.spinner("🩺 Verifying current team availability for pregame-eligible games…"):
        av = base._availability_snapshot(day_str, pregame)
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
            base._render_game_context(game, contexts, av_map)

    st.markdown("### 🔒 Spread Production Locks")
    foundation_ready = bool(len(pregame) and state == "VERIFIED" and availability_ready)
    locks = pd.DataFrame([
        {"Layer": "Verified slate", "State": "READY" if len(schedule) else "CHECK"},
        {"Layer": "Pregame eligibility", "State": "READY" if len(pregame) else "NO ELIGIBLE GAMES"},
        {"Layer": "Team context", "State": "READY" if state == "VERIFIED" else "CHECK"},
        {"Layer": "Current availability", "State": "READY" if availability_ready else ("N/A" if not len(pregame) else "CHECK")},
        {"Layer": "Exact sportsbook spread line", "State": "NEXT" if foundation_ready else "LOCKED"},
        {"Layer": "Projected game margin", "State": "NEXT" if foundation_ready else "LOCKED"},
        {"Layer": "Cover probability / fair spread", "State": "NEXT" if foundation_ready else "LOCKED"},
        {"Layer": "5M Monte Carlo", "State": "OFF"},
        {"Layer": "Daily Picks connector", "State": "OFF"},
    ])
    st.dataframe(locks, use_container_width=True, hide_index=True)
    st.info(
        "V1.1 still makes no spread pick. It only guarantees that future pregame spread math can never accidentally consume a LIVE/final game."
    )


__all__ = ["MODEL_VERSION", "render_wnba_spread_hub"]
