"""WNBA Spread V1.0 — isolated pregame spread foundation.

This module is intentionally separate from PRA, Points, Rebounds, Assists, Daily
Picks and MLB. It establishes the verified data foundation for a future WNBA
spread production model without changing any existing model or connector.

V1.0 provides:
- Step 1: official/verified WNBA slate for the selected Eastern date;
- Step 2: descriptive team-strength context (record, L10/L5, PF/PA, pace,
  ORTG/DRTG when verified, and H2H history);
- Step 3: current injury/availability verification and explicit starter counts.

No sportsbook spread line, projected margin, cover probability, fair spread, or
Monte Carlo result is produced yet. Those layers will be added only after this
foundation is verified in the deployed app.
"""
from __future__ import annotations

from datetime import date
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import streamlit as st

import wnba_availability_v33 as availability
import wnba_context_v26 as context

MODEL_VERSION = "WNBA SPREAD V1.0 • VERIFIED SLATE + TEAM CONTEXT + AVAILABILITY"
ET = ZoneInfo("America/New_York")


def _day(value=None) -> str:
    if value is None:
        value = st.session_state.get("wnba_spread_v1_date") or pd.Timestamp.now(tz=ET).date()
    return pd.to_datetime(value).strftime("%Y-%m-%d")


def _num(value, default=np.nan):
    try:
        x = float(value)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _fmt(value, digits=1, fallback="—"):
    x = _num(value, np.nan)
    if pd.isna(x):
        return fallback
    return f"{x:.{digits}f}"


def _record(obj: dict) -> str:
    gp = int(_num((obj or {}).get("GP"), 0) or 0)
    w = int(_num((obj or {}).get("W"), 0) or 0)
    l = int(_num((obj or {}).get("L"), 0) or 0)
    return f"{w}-{l}" if gp else "—"


def _recent(obj: dict, n: int) -> str:
    if n == 10:
        w = int(_num((obj or {}).get("L10_W"), 0) or 0)
        l = int(_num((obj or {}).get("L10_L"), 0) or 0)
    else:
        w = int(_num((obj or {}).get("L5_W"), 0) or 0)
        l = int(_num((obj or {}).get("L5_L"), 0) or 0)
    return f"{w}-{l}" if (w + l) else "—"


def _schedule(day_str: str) -> pd.DataFrame:
    try:
        frame = availability.schedule_for_date(day_str)
    except Exception:
        frame = pd.DataFrame()
    if not isinstance(frame, pd.DataFrame):
        frame = pd.DataFrame()
    return frame.copy().reset_index(drop=True)


def _active_schedule(schedule: pd.DataFrame) -> pd.DataFrame:
    if schedule.empty:
        return schedule.copy()
    status = schedule.get(
        "status",
        schedule.get("status_text", pd.Series("", index=schedule.index)),
    ).astype(str).str.upper()
    return schedule.loc[~status.str.contains("FINAL", na=False)].copy().reset_index(drop=True)


def _availability_snapshot(day_str: str, schedule: pd.DataFrame):
    try:
        stats = availability.player_form_table()
    except Exception:
        stats = pd.DataFrame()

    rows = []
    for _, game in schedule.iterrows():
        gid = str(game.get("game_id") or "")
        away_id = int(_num(game.get("away_team_id"), 0) or 0)
        home_id = int(_num(game.get("home_team_id"), 0) or 0)
        try:
            av = availability.availability_for_game(game, stats)
        except Exception as exc:
            av = {"players": pd.DataFrame(), "starter_counts": {}, "team_status_coverage": {}, "source": f"unavailable • {type(exc).__name__}"}

        players = av.get("players")
        if not isinstance(players, pd.DataFrame):
            players = pd.DataFrame()
        designations = players.get("DESIGNATION", pd.Series(dtype=object)).astype(str).str.upper() if not players.empty else pd.Series(dtype=object)
        hard_out = int(designations.isin(set(availability.OUT_STATUSES)).sum()) if not designations.empty else 0
        uncertain = int(designations.isin(set(availability.UNCERTAIN_STATUSES)).sum()) if not designations.empty else 0
        unverified = int(designations.eq("STATUS UNVERIFIED").sum()) if not designations.empty else 0
        starters = av.get("starter_counts") or {}
        coverage = av.get("team_status_coverage") or {}

        rows.append({
            "game_id": gid,
            "away": str(game.get("away_team") or "Away"),
            "home": str(game.get("home_team") or "Home"),
            "away_id": away_id,
            "home_id": home_id,
            "away_starters": int(starters.get(away_id, 0) or 0),
            "home_starters": int(starters.get(home_id, 0) or 0),
            "covered_teams": int(bool(coverage.get(away_id))) + int(bool(coverage.get(home_id))),
            "hard_out": hard_out,
            "uncertain": uncertain,
            "unverified": unverified,
            "source": str(av.get("source") or "—"),
        })
    return pd.DataFrame(rows)


def _render_game_context(game, contexts: dict, av_map: dict):
    gid = str(game.get("game_id") or "")
    away_name = str(game.get("away_team") or "Away")
    home_name = str(game.get("home_team") or "Home")
    tip = str(game.get("first_tip_et") or game.get("game_time_et") or game.get("start_time_et") or "—")
    venue = str(game.get("venue") or "Venue TBD")
    status = str(game.get("status") or game.get("status_text") or "Scheduled")

    ctx = contexts.get(gid) or {}
    away = ctx.get("away") or {}
    home = ctx.get("home") or {}
    h2h = ctx.get("h2h") or {}
    av = av_map.get(gid) or {}

    st.markdown(f"#### {away_name} @ {home_name}")
    st.caption(f"{tip} ET • {venue} • {status}")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"{away_name} record", _record(away), f"L10 {_recent(away, 10)}")
    c2.metric(f"{home_name} record", _record(home), f"L10 {_recent(home, 10)}")
    c3.metric("L10 net scoring", f"{_fmt(away.get('L10_DIFF'))} / {_fmt(home.get('L10_DIFF'))}", "away / home")
    c4.metric("H2H sample", int(_num(h2h.get("GAMES"), 0) or 0), f"current-season {int(_num(h2h.get('CURRENT_GAMES'),0) or 0)}")

    table = pd.DataFrame([
        {
            "Team": away_name,
            "Season PF": _fmt(away.get("PF")),
            "Season PA": _fmt(away.get("PA")),
            "Season Diff": _fmt(away.get("DIFF")),
            "L10 PF": _fmt(away.get("L10_PF")),
            "L10 PA": _fmt(away.get("L10_PA")),
            "L10 Diff": _fmt(away.get("L10_DIFF")),
            "Pace L10": _fmt(away.get("PACE_L10")),
            "ORTG L10": _fmt(away.get("ORTG_L10")),
            "DRTG L10": _fmt(away.get("DRTG_L10")),
            "Adv GP": int(_num(away.get("ADV_GAMES"), 0) or 0),
        },
        {
            "Team": home_name,
            "Season PF": _fmt(home.get("PF")),
            "Season PA": _fmt(home.get("PA")),
            "Season Diff": _fmt(home.get("DIFF")),
            "L10 PF": _fmt(home.get("L10_PF")),
            "L10 PA": _fmt(home.get("L10_PA")),
            "L10 Diff": _fmt(home.get("L10_DIFF")),
            "Pace L10": _fmt(home.get("PACE_L10")),
            "ORTG L10": _fmt(home.get("ORTG_L10")),
            "DRTG L10": _fmt(home.get("DRTG_L10")),
            "Adv GP": int(_num(home.get("ADV_GAMES"), 0) or 0),
        },
    ])
    st.dataframe(table, use_container_width=True, hide_index=True)

    a1, a2, a3, a4 = st.columns(4)
    a1.metric("Status coverage", f"{int(av.get('covered_teams', 0) or 0)}/2 teams")
    a2.metric("Hard OUT", int(av.get("hard_out", 0) or 0))
    a3.metric("Status uncertain", int(av.get("uncertain", 0) or 0))
    a4.metric("Starters confirmed", f"{int(av.get('away_starters',0) or 0)} / {int(av.get('home_starters',0) or 0)}", "away / home")

    if int(av.get("unverified", 0) or 0) > 0:
        st.warning(f"⚠️ {int(av.get('unverified',0))} player availability row(s) are unverified for this game. Future spread production must fail closed until resolved.")
    elif int(av.get("covered_teams", 0) or 0) == 2:
        st.success("✅ Current availability coverage verified for both teams.")
    else:
        st.warning("⚠️ Team availability coverage is incomplete. No spread projection will be permitted from an incomplete state.")

    with st.expander("H2H context — descriptive only", expanded=False):
        st.write({
            "sample_games": int(_num(h2h.get("GAMES"), 0) or 0),
            "away_wins": int(_num(h2h.get("AWAY_W"), 0) or 0),
            "home_wins": int(_num(h2h.get("HOME_W"), 0) or 0),
            "avg_total": None if pd.isna(_num(h2h.get("AVG_TOTAL"), np.nan)) else round(float(h2h.get("AVG_TOTAL")), 1),
            "away_avg_margin": None if pd.isna(_num(h2h.get("AWAY_MARGIN"), np.nan)) else round(float(h2h.get("AWAY_MARGIN")), 1),
            "used_as_projection_multiplier": False,
        })
    st.divider()


def render_wnba_spread_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.markdown("## 🏀 WNBA Spread Command Center")
    st.caption(
        "V1.0 foundation • verified slate → team strength/context → current availability. "
        "Sportsbook spread, projected margin and Monte Carlo are intentionally OFF until the foundation is verified."
    )

    default_day = st.session_state.get("wnba_spread_v1_date") or pd.Timestamp.now(tz=ET).date()
    selected = st.date_input(
        "Spread slate date",
        value=pd.to_datetime(default_day).date(),
        key="wnba_spread_v1_date_picker",
    )
    st.session_state["wnba_spread_v1_date"] = selected
    day_str = _day(selected)

    with st.spinner("📅 Verifying WNBA spread slate…"):
        schedule = _schedule(day_str)
        active = _active_schedule(schedule)

    teams = 0
    if not schedule.empty:
        team_ids = set()
        for col in ("away_team_id", "home_team_id"):
            if col in schedule.columns:
                team_ids.update(pd.to_numeric(schedule[col], errors="coerce").dropna().astype(int).tolist())
        teams = len(team_ids)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Slate games", int(len(schedule)))
    c2.metric("Active games", int(len(active)))
    c3.metric("Teams", int(teams))
    c4.metric("Model state", "FOUNDATION")

    if schedule.empty:
        st.warning("No verified WNBA games were returned for this Eastern-date slate. Nothing is projected or fabricated.")
        return

    st.success(f"✅ STEP 1 PASSED • verified WNBA slate loaded for {day_str}.")

    with st.spinner("📊 Building verified team form + matchup context…"):
        try:
            contexts, cdiag = context.slate_context(day_str)
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

    with st.spinner("🩺 Verifying current team availability…"):
        av = _availability_snapshot(day_str, active)
    av_map = {str(r.get("game_id") or ""): r.to_dict() for _, r in av.iterrows()} if not av.empty else {}

    covered = int(pd.to_numeric(av.get("covered_teams", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if not av.empty else 0
    expected_coverage = int(2 * len(active))
    unverified = int(pd.to_numeric(av.get("unverified", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if not av.empty else 0
    a1, a2, a3, a4 = st.columns(4)
    a1.metric("Availability coverage", f"{covered}/{expected_coverage}" if expected_coverage else "0/0")
    a2.metric("Hard OUT", int(pd.to_numeric(av.get("hard_out", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if not av.empty else 0)
    a3.metric("Status uncertain", int(pd.to_numeric(av.get("uncertain", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()) if not av.empty else 0)
    a4.metric("Unverified players", unverified)

    availability_ready = bool(expected_coverage > 0 and covered == expected_coverage and unverified == 0)
    if availability_ready:
        st.success("✅ STEP 3 PASSED • current availability coverage is complete for every active game.")
    else:
        st.warning("⚠️ STEP 3 CHECK • availability is not fully verified for every active game. Future spread production will remain locked until this passes.")

    st.markdown("### 🧩 Verified Game-by-Game Foundation")
    for _, game in active.iterrows():
        _render_game_context(game, contexts, av_map)

    st.markdown("### 🔒 Spread Production Locks")
    locks = pd.DataFrame([
        {"Layer": "Verified slate", "State": "READY" if len(active) else "CHECK"},
        {"Layer": "Team context", "State": "READY" if state == "VERIFIED" else "CHECK"},
        {"Layer": "Current availability", "State": "READY" if availability_ready else "CHECK"},
        {"Layer": "Exact sportsbook spread line", "State": "NEXT"},
        {"Layer": "Projected game margin", "State": "NEXT"},
        {"Layer": "Cover probability / fair spread", "State": "NEXT"},
        {"Layer": "5M Monte Carlo", "State": "OFF"},
        {"Layer": "Daily Picks connector", "State": "OFF"},
    ])
    st.dataframe(locks, use_container_width=True, hide_index=True)
    st.info("V1.0 does not make a spread pick. This page is the verified foundation we will build the production spread engine on top of.")


__all__ = ["MODEL_VERSION", "render_wnba_spread_hub"]
