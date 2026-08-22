"""WNBA Game Total V1.2 — Step 5 independent projected game total.

Preserves Game Total V1.1 Steps 1-4 exactly and adds Step 5 only.
Step 5 reuses the verified market-independent WNBA projected-score engine and
sums the away/home score projections into one independent full-game total.
Sportsbook totals/prices remain an upstream coverage/freshness gate only and are
not accepted by the projection engine. H2H remains descriptive only.

No Over/Under probability, fair total, Monte Carlo, final grading, ranking or
Daily Picks output is introduced here.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

import wnba_game_total_hub_v11 as prior
import wnba_spread_projection_v14 as score_model

MODEL_VERSION = "WNBA GAME TOTAL V1.2 • INDEPENDENT PROJECTED GAME TOTAL"
ET = prior.ET
foundation = prior.foundation
clock = prior.clock
spread_current = prior.spread_current


def _num(value, default=np.nan):
    try:
        x = float(value)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _fmt(value, digits=1):
    x = _num(value, np.nan)
    return "—" if pd.isna(x) else f"{x:.{digits}f}"


def _projected_total_board(day_str: str, pregame: pd.DataFrame, contexts: dict):
    empty_meta = {
        "state": "N/A",
        "games": int(len(pregame) if isinstance(pregame, pd.DataFrame) else 0),
        "covered_games": 0,
        "rows": 0,
        "ready": 0,
        "monitor": 0,
        "blocked": 0,
        "sportsbook_inputs": 0,
        "model_ready": False,
    }
    if pregame is None or pregame.empty:
        return pd.DataFrame(), empty_meta

    projected, proj_meta = score_model.project_slate(day_str, pregame, contexts)
    if projected is None or projected.empty:
        meta = dict(empty_meta)
        meta.update({"state": "CHECK", "blocked": int(len(pregame))})
        return pd.DataFrame(), meta

    rows = []
    covered = set()
    game_ids = set(pregame.get("game_id", pd.Series(dtype=object)).astype(str).tolist())

    for _, r in projected.iterrows():
        gid = str(r.get("game_id") or "")
        state = str(r.get("state") or "BLOCKED").upper()
        away_score = _num(r.get("away_score"), np.nan)
        home_score = _num(r.get("home_score"), np.nan)
        if state == "BLOCKED" or not np.isfinite(away_score) or not np.isfinite(home_score):
            continue

        total = float(away_score + home_score)
        if not np.isfinite(total) or total <= 0:
            continue

        row = dict(r)
        row["projected_total"] = total
        row["season_total_component"] = (
            _num(r.get("season_away"), np.nan) + _num(r.get("season_home"), np.nan)
            if np.isfinite(_num(r.get("season_away"), np.nan)) and np.isfinite(_num(r.get("season_home"), np.nan))
            else np.nan
        )
        row["recent_total_component"] = (
            _num(r.get("recent_away"), np.nan) + _num(r.get("recent_home"), np.nan)
            if np.isfinite(_num(r.get("recent_away"), np.nan)) and np.isfinite(_num(r.get("recent_home"), np.nan))
            else np.nan
        )
        row["venue_total_component"] = (
            _num(r.get("venue_away"), np.nan) + _num(r.get("venue_home"), np.nan)
            if np.isfinite(_num(r.get("venue_away"), np.nan)) and np.isfinite(_num(r.get("venue_home"), np.nan))
            else np.nan
        )
        row["advanced_total_component"] = (
            _num(r.get("advanced_away"), np.nan) + _num(r.get("advanced_home"), np.nan)
            if np.isfinite(_num(r.get("advanced_away"), np.nan)) and np.isfinite(_num(r.get("advanced_home"), np.nan))
            else np.nan
        )
        row["sportsbook_inputs"] = 0
        row["h2h_weight"] = 0.0
        row["projection_method"] = "market-independent away score + home score"
        rows.append(row)
        covered.add(gid)

    frame = pd.DataFrame(rows)
    states = frame.get("state", pd.Series(dtype=object)).astype(str).str.upper() if not frame.empty else pd.Series(dtype=object)
    ready = int(states.eq("READY").sum()) if not frame.empty else 0
    monitor = int(states.eq("MONITOR").sum()) if not frame.empty else 0
    blocked = int(len(game_ids - covered))
    model_ready = bool(game_ids and game_ids.issubset(covered) and blocked == 0)
    meta = {
        "state": "READY" if model_ready else "CHECK",
        "games": int(len(game_ids)),
        "covered_games": int(len(game_ids & covered)),
        "rows": int(len(frame)),
        "ready": ready,
        "monitor": monitor,
        "blocked": blocked,
        "sportsbook_inputs": 0,
        "model_ready": model_ready,
        "projection_state": str((proj_meta or {}).get("state") or "CHECK"),
        "history_games": int((proj_meta or {}).get("history_games", 0) or 0),
    }
    return frame, meta


def _render_step5(day_str: str, pregame: pd.DataFrame, contexts: dict, market_ready: bool):
    st.markdown("### 🧠 Step 5 — Independent Projected Game Total")
    st.caption(
        "Verified team data only • season + L10 offense/defense + road/home splits + recent pace/efficiency + exact-day availability. "
        "The Step-4 sportsbook total is an upstream gate only; sportsbook total/price inputs = ZERO and H2H weight = 0%."
    )

    if pregame is None or pregame.empty:
        st.info("ℹ️ STEP 5 NOT APPLICABLE • no clock-safe pregame games remain.")
        return pd.DataFrame(), {"state":"N/A","games":0,"covered_games":0,"rows":0,"ready":0,"monitor":0,"blocked":0,"sportsbook_inputs":0,"model_ready":False}

    if not market_ready:
        st.warning(
            "🔒 STEP 5 LOCKED • exact current sportsbook Game Total coverage must pass Step 4 first. "
            "Those market values still do not enter the projected-total math."
        )
        return pd.DataFrame(), {"state":"LOCKED","games":int(len(pregame)),"covered_games":0,"rows":0,"ready":0,"monitor":0,"blocked":0,"sportsbook_inputs":0,"model_ready":False}

    with st.spinner("🧠 Building market-independent WNBA projected game totals…"):
        board, meta = _projected_total_board(day_str, pregame, contexts)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Games projected", f"{int(meta.get('covered_games',0))}/{int(meta.get('games',0))}")
    c2.metric("READY", int(meta.get("ready", 0)))
    c3.metric("MONITOR", int(meta.get("monitor", 0)))
    c4.metric("Sportsbook inputs", int(meta.get("sportsbook_inputs", 0)))

    model_ready = bool(meta.get("model_ready", False))
    if model_ready:
        st.success(
            "✅ STEP 5 PASSED • every pregame game has an independent projected score and full-game total; sportsbook totals and prices did not change the projection."
        )
        if int(meta.get("monitor", 0)):
            st.info(
                f"🟦 {int(meta.get('monitor', 0))} game(s) are MONITOR because an upstream verified projection is carrying availability/data-layer uncertainty."
            )
    else:
        st.warning("⚠️ STEP 5 CHECK • at least one pregame game cannot produce a trustworthy independent projected total. Step 6 remains locked.")

    if board is not None and not board.empty:
        show = board.copy()
        show["Game"] = show["away_team"].astype(str) + " @ " + show["home_team"].astype(str)
        show["Projected score"] = show.apply(
            lambda r: f"{r.get('away_team')} {_fmt(r.get('away_score'))} — {r.get('home_team')} {_fmt(r.get('home_score'))}", axis=1
        )
        show["Projected total"] = show["projected_total"].map(_fmt)
        show["State"] = show["state"].astype(str).str.upper()
        st.dataframe(
            show[["Game", "first_tip_et", "Projected score", "Projected total", "State"]].rename(columns={"first_tip_et":"Tip ET"}),
            use_container_width=True,
            hide_index=True,
        )

        with st.expander("🔬 Step 5 projection audit — model components", expanded=False):
            audit = board.copy()
            audit["Game"] = audit["away_team"].astype(str) + " @ " + audit["home_team"].astype(str)
            for src, dst in [
                ("season_total_component", "Season total"),
                ("recent_total_component", "L10 total"),
                ("venue_total_component", "Venue total"),
                ("advanced_total_component", "Advanced total"),
                ("away_out_impact", "Away OUT impact"),
                ("home_out_impact", "Home OUT impact"),
            ]:
                audit[dst] = audit[src].map(_fmt) if src in audit.columns else "—"
            cols = ["Game", "Season total", "L10 total", "Venue total", "Advanced total", "Away OUT impact", "Home OUT impact", "components", "state", "reason"]
            cols = [c for c in cols if c in audit.columns]
            st.dataframe(audit[cols], use_container_width=True, hide_index=True)
            st.caption("Component totals are pre-final-blend views. H2H and sportsbook totals are not projection multipliers.")

    return board, meta


def render_wnba_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.markdown("## 🧮 WNBA Game Total Command Center")
    st.caption(
        "V1.2 • verified slate → clock-safe pregame guard → total-scoring team context → exact-day availability → exact sportsbook total → independent projected game total. "
        "Over/Under probability, fair total and Monte Carlo remain OFF."
    )

    default_day = st.session_state.get("wnba_game_total_v1_date") or pd.Timestamp.now(tz=ET).date()
    selected = st.date_input("Game Total slate date", value=pd.to_datetime(default_day).date(), key="wnba_game_total_v1_date_picker")
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
        with st.expander("🚫 Games excluded from Game Total pregame production", expanded=False):
            cols = [c for c in ["away_team", "home_team", "first_tip_et", "scheduled_tip_guard_et", "status", "status_text", "exclusion_reason"] if c in excluded.columns]
            st.dataframe(excluded[cols] if cols else excluded, use_container_width=True, hide_index=True)

    with st.spinner("📊 Building verified total-scoring team context…"):
        try:
            contexts, cdiag = foundation.context.slate_context(day_str)
        except Exception as exc:
            contexts, cdiag = {}, {"state":"CHECK","reason":type(exc).__name__}

    context_state = str(cdiag.get("state") or "CHECK").upper()
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Context state", context_state)
    d2.metric("Records verified", f"{int(cdiag.get('records_verified',0) or 0)}/{int(cdiag.get('teams',teams) or teams)}")
    d3.metric("Advanced teams", int(cdiag.get("advanced_teams",0) or 0))
    d4.metric("H2H samples", int(cdiag.get("h2h_samples",0) or 0))
    if context_state == "VERIFIED":
        st.success("✅ STEP 2 PASSED • scoring form/defense/recent pace are verified; advanced ratings are used only where real samples exist.")
    else:
        st.warning("⚠️ STEP 2 CHECK • some total-scoring context is incomplete. Missing advanced fields remain neutral/missing; nothing is invented.")

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
        st.warning("⚠️ STEP 3 CHECK • availability is not fully verified for every pregame-eligible game. Future Game Total production remains locked.")

    st.markdown("### 🧩 Pregame-Eligible Game Total Foundation")
    if pregame.empty:
        st.info("No pregame-eligible games remain to display.")
    else:
        for _, game in pregame.iterrows():
            prior.prior._render_game_context(game, contexts, av_map)

    foundation_ready = bool(len(pregame) and context_state == "VERIFIED" and availability_ready)
    market_rows, market_meta = prior._render_step4(day_str, pregame, foundation_ready)
    market_ready = bool(market_meta.get("market_ready", False))
    projection_rows, projection_meta = _render_step5(day_str, pregame, contexts, market_ready)
    projection_ready = bool(projection_meta.get("model_ready", False))

    st.session_state["wnba_game_total_v1_day"] = day_str
    st.session_state["wnba_game_total_v1_foundation_ready"] = foundation_ready
    st.session_state["wnba_game_total_v1_schedule"] = schedule.to_dict("records")
    st.session_state["wnba_game_total_v1_pregame"] = pregame.to_dict("records")
    st.session_state["wnba_game_total_v1_availability"] = av.to_dict("records") if not av.empty else []
    st.session_state["wnba_game_total_v11_market_rows"] = market_rows.to_dict("records") if isinstance(market_rows, pd.DataFrame) and not market_rows.empty else []
    st.session_state["wnba_game_total_v11_market_meta"] = dict(market_meta)
    st.session_state["wnba_game_total_v11_market_ready"] = market_ready
    st.session_state["wnba_game_total_v12_projection_rows"] = projection_rows.to_dict("records") if isinstance(projection_rows, pd.DataFrame) and not projection_rows.empty else []
    st.session_state["wnba_game_total_v12_projection_meta"] = dict(projection_meta)
    st.session_state["wnba_game_total_v12_projection_ready"] = projection_ready

    st.markdown("### 🔒 Game Total Production Locks")
    locks = pd.DataFrame([
        {"Layer":"Verified slate","State":"READY" if len(schedule) else "CHECK"},
        {"Layer":"Clock-safe pregame eligibility","State":"READY" if len(pregame) else "NO ELIGIBLE GAMES"},
        {"Layer":"Total-scoring team context","State":"READY" if context_state == "VERIFIED" else "CHECK"},
        {"Layer":"Current availability","State":"READY" if availability_ready else ("N/A" if expected_coverage == 0 else "CHECK")},
        {"Layer":"Exact sportsbook game total","State":"READY" if market_ready else ("N/A" if not len(pregame) else "CHECK")},
        {"Layer":"Independent projected game total","State":"READY" if projection_ready else ("NEXT" if market_ready else "LOCKED")},
        {"Layer":"Over/Under probability / fair total","State":"NEXT" if projection_ready else "LOCKED"},
        {"Layer":"5M Monte Carlo","State":"OFF"},
        {"Layer":"Final Game Total grading","State":"OFF"},
        {"Layer":"Daily Picks connector","State":"OFF"},
    ])
    st.dataframe(locks, use_container_width=True, hide_index=True)
    st.info(
        "V1.2 makes no Game Total pick. Step 5 creates a market-independent projected full-game total only. "
        "Line-specific Over/Under probability and fair total are the next layer; Monte Carlo, grading and Daily Picks remain OFF."
    )
