"""WNBA Game Total V1.3 — Step 6 line-specific O/U probability + fair total.

Preserves Game Total V1.2 Steps 1-5 exactly and adds Step 6 only. Step 6 keeps the
Step-5 projected total frozen, estimates uncertainty from date-cut empirical team
and league game-total variance, then evaluates every exact Step-4 same-book total.
Sportsbook lines/prices are comparison thresholds only and cannot move the model
mean or variance. Integer lines receive explicit push probability.

No Monte Carlo, final grading/ranking, staking or Daily Picks output is introduced.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

import wnba_game_total_hub_v12 as prior
import wnba_game_total_probability_v13 as total_probability

MODEL_VERSION = "WNBA GAME TOTAL V1.3 • O/U PROBABILITY + FAIR TOTAL"
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


def _fmt_pct(value, digits=1):
    x = _num(value, np.nan)
    return "—" if pd.isna(x) else f"{100.0*x:.{digits}f}%"


def _fmt_odds(value):
    x = _num(value, np.nan)
    return "—" if pd.isna(x) else f"{int(round(x)):+d}"


def _render_step6(day_str: str, pregame: pd.DataFrame, projection_rows: pd.DataFrame, market_rows: pd.DataFrame, projection_ready: bool):
    st.markdown("### 📊 Step 6 — Over/Under Probability + Fair Total")
    st.caption(
        "Analytical pre-Monte-Carlo layer • Step-5 projected total stays frozen. Date-cut empirical team/league game-total variance sets uncertainty; "
        "the verified Step-4 sportsbook total is only the O/U threshold. Integer totals receive explicit push probability."
    )

    if pregame is None or pregame.empty:
        st.info("ℹ️ STEP 6 NOT APPLICABLE • no clock-safe pregame games remain.")
        return pd.DataFrame(), {"state":"N/A","games":0,"covered_games":0,"rows":0,"ready":0,"monitor":0,"blocked":0,"model_ready":False}

    if not projection_ready:
        st.warning("🔒 STEP 6 LOCKED • every pregame game must have a trustworthy independent Step-5 projected total first.")
        return pd.DataFrame(), {"state":"LOCKED","games":int(len(pregame)),"covered_games":0,"rows":0,"ready":0,"monitor":0,"blocked":0,"model_ready":False}

    with st.spinner("📊 Building line-specific WNBA Game Total probabilities…"):
        board, meta = total_probability.probability_board(day_str, pregame, projection_rows, market_rows)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Game coverage", f"{int(meta.get('covered_games',0))}/{int(meta.get('games',0))}")
    c2.metric("Probability rows", int(meta.get("rows", 0)))
    c3.metric("READY", int(meta.get("ready", 0)))
    c4.metric("MONITOR", int(meta.get("monitor", 0)))

    model_ready = bool(meta.get("model_ready", False))
    if model_ready:
        st.success(
            "✅ STEP 6 PASSED • every pregame game has a full-game total distribution, fair total and line-specific O/U probabilities without changing the Step-5 projection."
        )
        if int(meta.get("monitor", 0)):
            st.info(
                f"🟦 {int(meta.get('monitor',0))} row(s) carry MONITOR because of upstream or short-sample uncertainty. The flag must carry forward to Monte Carlo/final grading."
            )
    else:
        st.warning("⚠️ STEP 6 CHECK • at least one pregame game lacks a trustworthy probability row. Step 7 remains locked.")

    if board is not None and not board.empty:
        show = board.copy()
        show["Game"] = show["away_team"].astype(str) + " @ " + show["home_team"].astype(str)
        show["Market total"] = show["market_total"].map(_fmt)
        show["Fair total"] = show["fair_total"].map(_fmt)
        show["Over"] = show["over"].map(_fmt_pct)
        show["Under"] = show["under"].map(_fmt_pct)
        show["Push"] = show["push"].map(_fmt_pct)
        show["Over fair odds"] = show["over_fair_odds"].map(_fmt_odds)
        show["Under fair odds"] = show["under_fair_odds"].map(_fmt_odds)
        show["State"] = show["state"].astype(str).str.upper()
        st.dataframe(
            show[["Game","first_tip_et","book","Market total","Fair total","Over","Under","Push","Over fair odds","Under fair odds","State"]].rename(
                columns={"first_tip_et":"Tip ET","book":"Book"}
            ),
            use_container_width=True,
            hide_index=True,
        )

        with st.expander("🧮 Step 6 probability audit — variance + no-vig comparison", expanded=False):
            audit = board.copy()
            audit["Game"] = audit["away_team"].astype(str) + " @ " + audit["home_team"].astype(str)
            audit["Sigma"] = audit["sigma"].map(lambda x: _fmt(x,2))
            audit["80% range"] = audit.apply(lambda r: f"{_fmt(r.get('total_low80'))}–{_fmt(r.get('total_high80'))}", axis=1)
            audit["Over model no-push"] = audit["over_no_push"].map(_fmt_pct)
            audit["Under model no-push"] = audit["under_no_push"].map(_fmt_pct)
            audit["Over market no-vig"] = audit["over_market_novig"].map(_fmt_pct)
            audit["Under market no-vig"] = audit["under_market_novig"].map(_fmt_pct)
            audit["Over edge"] = audit["over_edge_pp"].map(lambda x: "—" if pd.isna(_num(x,np.nan)) else f"{_num(x):+.1f} pp")
            audit["Under edge"] = audit["under_edge_pp"].map(lambda x: "—" if pd.isna(_num(x,np.nan)) else f"{_num(x):+.1f} pp")
            cols = ["Game","book","market_total","fair_total","Sigma","80% range","Over model no-push","Under model no-push","Over market no-vig","Under market no-vig","Over edge","Under edge","away_total_games","home_total_games","league_total_games","sigma_source","projection_state","state"]
            cols = [c for c in cols if c in audit.columns]
            st.dataframe(audit[cols], use_container_width=True, hide_index=True)
            st.caption("Fair total equals the frozen Step-5 independent mean. Market no-vig is comparison-only and never feeds back into projection or variance.")

    return board, meta


def render_wnba_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.markdown("## 🧮 WNBA Game Total Command Center")
    st.caption(
        "V1.3 • verified slate → clock-safe pregame guard → total-scoring team context → exact-day availability → exact sportsbook total → "
        "independent projected total → line-specific O/U probability + fair total. 5M Monte Carlo remains OFF."
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
    c4.metric("Model state", "STEP 6")
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
            cols = [c for c in ["away_team","home_team","first_tip_et","scheduled_tip_guard_et","status","status_text","exclusion_reason"] if c in excluded.columns]
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
            prior.prior.prior._render_game_context(game, contexts, av_map)

    foundation_ready = bool(len(pregame) and context_state == "VERIFIED" and availability_ready)
    market_rows, market_meta = prior.prior._render_step4(day_str, pregame, foundation_ready)
    market_ready = bool(market_meta.get("market_ready", False))
    projection_rows, projection_meta = prior._render_step5(day_str, pregame, contexts, market_ready)
    projection_ready = bool(projection_meta.get("model_ready", False))
    probability_rows, probability_meta = _render_step6(day_str, pregame, projection_rows, market_rows, projection_ready)
    probability_ready = bool(probability_meta.get("model_ready", False))

    st.session_state["wnba_game_total_v1_day"] = day_str
    st.session_state["wnba_game_total_v1_foundation_ready"] = foundation_ready
    st.session_state["wnba_game_total_v1_schedule"] = schedule.to_dict("records")
    st.session_state["wnba_game_total_v1_pregame"] = pregame.to_dict("records")
    st.session_state["wnba_game_total_v1_availability"] = av.to_dict("records") if not av.empty else []
    st.session_state["wnba_game_total_v11_market_rows"] = market_rows.to_dict("records") if isinstance(market_rows,pd.DataFrame) and not market_rows.empty else []
    st.session_state["wnba_game_total_v11_market_meta"] = dict(market_meta)
    st.session_state["wnba_game_total_v11_market_ready"] = market_ready
    st.session_state["wnba_game_total_v12_projection_rows"] = projection_rows.to_dict("records") if isinstance(projection_rows,pd.DataFrame) and not projection_rows.empty else []
    st.session_state["wnba_game_total_v12_projection_meta"] = dict(projection_meta)
    st.session_state["wnba_game_total_v12_projection_ready"] = projection_ready
    st.session_state["wnba_game_total_v13_probability_rows"] = probability_rows.to_dict("records") if isinstance(probability_rows,pd.DataFrame) and not probability_rows.empty else []
    st.session_state["wnba_game_total_v13_probability_meta"] = dict(probability_meta)
    st.session_state["wnba_game_total_v13_probability_ready"] = probability_ready

    st.markdown("### 🔒 Game Total Production Locks")
    locks = pd.DataFrame([
        {"Layer":"Verified slate","State":"READY" if len(schedule) else "CHECK"},
        {"Layer":"Clock-safe pregame eligibility","State":"READY" if len(pregame) else "NO ELIGIBLE GAMES"},
        {"Layer":"Total-scoring team context","State":"READY" if context_state == "VERIFIED" else "CHECK"},
        {"Layer":"Current availability","State":"READY" if availability_ready else ("N/A" if expected_coverage == 0 else "CHECK")},
        {"Layer":"Exact sportsbook game total","State":"READY" if market_ready else ("N/A" if not len(pregame) else "CHECK")},
        {"Layer":"Independent projected game total","State":"READY" if projection_ready else ("NEXT" if market_ready else "LOCKED")},
        {"Layer":"Over/Under probability / fair total","State":"READY" if probability_ready else ("NEXT" if projection_ready else "LOCKED")},
        {"Layer":"5M Monte Carlo","State":"NEXT" if probability_ready else "OFF"},
        {"Layer":"Final Game Total grading","State":"OFF"},
        {"Layer":"Daily Picks connector","State":"OFF"},
    ])
    st.dataframe(locks, use_container_width=True, hide_index=True)
    st.info(
        "V1.3 makes no Game Total pick. Step 6 evaluates the frozen independent total against exact sportsbook thresholds and produces analytical O/U probabilities + fair odds. "
        "The actual 5,000,000-draw Monte Carlo is the next production layer; grading and Daily Picks remain OFF."
    )
