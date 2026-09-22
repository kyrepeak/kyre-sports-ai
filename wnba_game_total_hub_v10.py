"""WNBA Game Total V1.0 — isolated pregame foundation.

This page is intentionally separate from PRA, Points, Rebounds, Assists, Spread,
Moneyline, Daily Picks and MLB. It establishes the verified data foundation for
a future WNBA full-game Total production model without changing any existing
source model, simulation, connector or saved production payload.

V1.0 provides:
- Step 1: verified WNBA slate for the selected Eastern date;
- a clock-safe pregame eligibility guard using provider state + scheduled tip;
- Step 2: descriptive total-scoring environment (season/L10 PF+PA, recent pace,
  ORTG/DRTG where verified, venue context and descriptive H2H average total);
- Step 3: exact-day current injury/availability verification.

No sportsbook total, projected game total, Over/Under probability, fair odds,
no-vig edge, Monte Carlo result, recommendation, ranking or Daily Picks payload
is produced. Those layers remain explicitly locked until this foundation is
verified in the deployed app.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

# Reuse only the already-verified low-level WNBA foundation/clock/availability
# adapters. No Moneyline projection, market, simulation, grading or connector
# output is read or modified by this page.
import wnba_moneyline_hub_v10 as prior

ET = prior.ET
foundation = prior.foundation
clock = prior.clock
spread_current = prior.spread_current
MODEL_VERSION = "WNBA GAME TOTAL V1.0 • VERIFIED PREGAME FOUNDATION"


def _num(value, default=np.nan):
    return prior._num(value, default)


def _fmt(value, digits=1, fallback="—"):
    return prior._fmt(value, digits, fallback)


def _record(obj: dict) -> str:
    return prior._record(obj)


def _recent(obj: dict, n: int = 10) -> str:
    return prior._recent(obj, n)


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
    st.caption(f"{tip} • {venue} • {status}")

    season_total_env = np.nan
    l10_total_env = np.nan
    try:
        season_vals = [
            _num(away.get("PF")), _num(away.get("PA")),
            _num(home.get("PF")), _num(home.get("PA")),
        ]
        if all(np.isfinite(x) for x in season_vals):
            # Average the two independent offense-vs-defense total views.
            season_total_env = (
                season_vals[0] + season_vals[3] + season_vals[2] + season_vals[1]
            ) / 2.0
        l10_vals = [
            _num(away.get("L10_PF")), _num(away.get("L10_PA")),
            _num(home.get("L10_PF")), _num(home.get("L10_PA")),
        ]
        if all(np.isfinite(x) for x in l10_vals):
            l10_total_env = (
                l10_vals[0] + l10_vals[3] + l10_vals[2] + l10_vals[1]
            ) / 2.0
    except Exception:
        pass

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(f"{away_name} record", _record(away), f"L10 {_recent(away, 10)}")
    c2.metric(f"{home_name} record", _record(home), f"L10 {_recent(home, 10)}")
    c3.metric("Scoring environment", f"{_fmt(season_total_env)} / {_fmt(l10_total_env)}", "season / L10")
    c4.metric(
        "H2H avg total",
        _fmt(h2h.get("AVG_TOTAL")),
        f"{int(_num(h2h.get('GAMES'), 0) or 0)} game sample",
    )

    table = pd.DataFrame([
        {
            "Team": away_name,
            "Season PF": _fmt(away.get("PF")),
            "Season PA": _fmt(away.get("PA")),
            "L10 PF": _fmt(away.get("L10_PF")),
            "L10 PA": _fmt(away.get("L10_PA")),
            "Pace L10": _fmt(away.get("PACE_L10")),
            "ORTG L10": _fmt(away.get("ORTG_L10")),
            "DRTG L10": _fmt(away.get("DRTG_L10")),
            "Adv GP": int(_num(away.get("ADV_GAMES"), 0) or 0),
        },
        {
            "Team": home_name,
            "Season PF": _fmt(home.get("PF")),
            "Season PA": _fmt(home.get("PA")),
            "L10 PF": _fmt(home.get("L10_PF")),
            "L10 PA": _fmt(home.get("L10_PA")),
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
    a4.metric(
        "Starters confirmed",
        f"{int(av.get('away_starters', 0) or 0)} / {int(av.get('home_starters', 0) or 0)}",
        "away / home",
    )

    if int(av.get("unverified", 0) or 0) > 0:
        st.warning(
            f"⚠️ {int(av.get('unverified', 0))} player availability row(s) are unverified for this game. "
            "Future Game Total production must fail closed until resolved."
        )
    elif int(av.get("covered_teams", 0) or 0) == 2:
        st.success("✅ Current availability coverage verified for both teams.")
    else:
        st.warning("⚠️ Team availability coverage is incomplete. No Game Total projection will be permitted from an incomplete state.")

    with st.expander("H2H total context — descriptive only", expanded=False):
        avg_total = _num(h2h.get("AVG_TOTAL"), np.nan)
        st.write({
            "sample_games": int(_num(h2h.get("GAMES"), 0) or 0),
            "current_season_games": int(_num(h2h.get("CURRENT_GAMES"), 0) or 0),
            "avg_total": None if pd.isna(avg_total) else round(float(avg_total), 1),
            "used_as_projection_multiplier": False,
            "sportsbook_total_used": False,
        })
    st.divider()


def render_wnba_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.markdown("## 🧮 WNBA Game Total Command Center")
    st.caption(
        "V1.0 foundation • verified slate → provider-state + scheduled-tip clock guard → total-scoring team context → "
        "exact-day current availability. Sportsbook total, independent projected total and Monte Carlo are intentionally OFF "
        "until the foundation is verified."
    )

    default_day = st.session_state.get("wnba_game_total_v1_date") or pd.Timestamp.now(tz=ET).date()
    selected = st.date_input(
        "Game Total slate date",
        value=pd.to_datetime(default_day).date(),
        key="wnba_game_total_v1_date_picker",
    )
    st.session_state["wnba_game_total_v1_date"] = selected
    day_str = pd.to_datetime(selected).strftime("%Y-%m-%d")
    now_et = pd.Timestamp.now(tz=ET)

    with st.spinner("📅 Verifying WNBA Game Total slate + clock-safe pregame eligibility…"):
        schedule = foundation._schedule(day_str)
        pregame = clock._pregame_schedule(schedule, now_et=now_et)
        excluded = clock._excluded_schedule(schedule, now_et=now_et)

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
    c3.metric("Excluded / locked", int(len(excluded)))
    c4.metric("Model state", "FOUNDATION")
    st.caption(f"Pregame eligibility clock • {now_et.strftime('%Y-%m-%d %I:%M:%S %p ET')}")

    if schedule.empty:
        st.warning("No verified WNBA games were returned for this Eastern-date slate. Nothing is projected or fabricated.")
        return

    st.success(f"✅ STEP 1 PASSED • verified WNBA slate loaded for {day_str}.")
    if len(pregame):
        st.success(
            f"✅ PREGAME ELIGIBILITY PASSED • {len(pregame)} game(s) are still before scheduled tip and provider-safe."
        )
    else:
        st.info(
            "ℹ️ No games on this slate remain pregame-eligible. Passed-tip/live/final/uncertain-tip games are locked out."
        )

    if not excluded.empty:
        with st.expander("🚫 Games excluded from Game Total pregame production", expanded=False):
            cols = [c for c in [
                "away_team", "home_team", "first_tip_et", "scheduled_tip_guard_et",
                "status", "status_text", "exclusion_reason",
            ] if c in excluded.columns]
            st.dataframe(excluded[cols] if cols else excluded, use_container_width=True, hide_index=True)

    with st.spinner("📊 Building verified total-scoring team context…"):
        try:
            contexts, cdiag = foundation.context.slate_context(day_str)
        except Exception as exc:
            contexts, cdiag = {}, {"state": "CHECK", "reason": type(exc).__name__}

    context_state = str(cdiag.get("state") or "CHECK").upper()
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Context state", context_state)
    d2.metric("Records verified", f"{int(cdiag.get('records_verified', 0) or 0)}/{int(cdiag.get('teams', teams) or teams)}")
    d3.metric("Advanced teams", int(cdiag.get("advanced_teams", 0) or 0))
    d4.metric("H2H samples", int(cdiag.get("h2h_samples", 0) or 0))

    if context_state == "VERIFIED":
        st.success(
            "✅ STEP 2 PASSED • scoring form/defense/recent pace are verified; advanced ratings are used only where real samples exist."
        )
    else:
        st.warning(
            "⚠️ STEP 2 CHECK • some total-scoring context is incomplete. Missing advanced fields remain neutral/missing; nothing is invented."
        )

    with st.spinner("🩺 Verifying exact-day current team availability for pregame-eligible games…"):
        av = spread_current._availability_snapshot_exact_day(day_str, pregame)
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
        st.warning(
            "⚠️ STEP 3 CHECK • availability is not fully verified for every pregame-eligible game. Future Game Total production remains locked."
        )

    st.markdown("### 🧩 Pregame-Eligible Game Total Foundation")
    if pregame.empty:
        st.info("No pregame-eligible games remain to display.")
    else:
        for _, game in pregame.iterrows():
            _render_game_context(game, contexts, av_map)

    foundation_ready = bool(len(pregame) and context_state == "VERIFIED" and availability_ready)
    st.session_state["wnba_game_total_v1_day"] = day_str
    st.session_state["wnba_game_total_v1_foundation_ready"] = foundation_ready
    st.session_state["wnba_game_total_v1_schedule"] = schedule.to_dict("records")
    st.session_state["wnba_game_total_v1_pregame"] = pregame.to_dict("records")
    st.session_state["wnba_game_total_v1_availability"] = av.to_dict("records") if not av.empty else []

    st.markdown("### 🔒 Game Total Production Locks")
    locks = pd.DataFrame([
        {"Layer": "Verified slate", "State": "READY" if len(schedule) else "CHECK"},
        {"Layer": "Clock-safe pregame eligibility", "State": "READY" if len(pregame) else "NO ELIGIBLE GAMES"},
        {"Layer": "Total-scoring team context", "State": "READY" if context_state == "VERIFIED" else "CHECK"},
        {"Layer": "Current availability", "State": "READY" if availability_ready else ("N/A" if expected_coverage == 0 else "CHECK")},
        {"Layer": "Exact sportsbook game total", "State": "NEXT" if foundation_ready else "LOCKED"},
        {"Layer": "Independent projected game total", "State": "NEXT" if foundation_ready else "LOCKED"},
        {"Layer": "Over/Under probability / fair total", "State": "LOCKED"},
        {"Layer": "5M Monte Carlo", "State": "OFF"},
        {"Layer": "Final Game Total grading", "State": "OFF"},
        {"Layer": "Daily Picks connector", "State": "OFF"},
    ])
    st.dataframe(locks, use_container_width=True, hide_index=True)
    st.info(
        "V1.0 makes no Game Total pick. This page only verifies the pregame foundation. Sportsbook totals, independent projected total, "
        "Over/Under probabilities, fair odds and Monte Carlo remain OFF until the next verified layer is added."
    )
