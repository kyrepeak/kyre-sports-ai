"""WNBA Spread V1.5 — Step 6 cover probability + fair spread.

Preserves Steps 1-5 and adds an analytical probability layer only after the exact
sportsbook line and the independent projected margin have both passed. Step 6
uses date-cut empirical team/league margin dispersion, explicit push handling on
integer spreads, fair odds, fair spreads, and no-vig market comparison.

No Monte Carlo is run here. The sportsbook line/price is a comparison threshold,
never an input to the Step-5 projected margin.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

import wnba_spread_hub_v14 as prior
import wnba_spread_probability_v15 as probability

foundation = prior.foundation
clock = prior.clock
ui = prior.ui
ET = prior.ET
MODEL_VERSION = "WNBA SPREAD V1.5 • COVER PROBABILITY + FAIR SPREAD"

# Re-assert the hardened Step-4 adapter used by V1.4.
ui._spread_market_snapshot = prior.step4_integrity.market.spread_market_snapshot


def _fmt(value, digits=1):
    return prior._fmt(value, digits)


def _fmt_pct(value, digits=1):
    try:
        x = float(value)
        if np.isfinite(x):
            return f"{100.0*x:.{digits}f}%"
    except Exception:
        pass
    return "—"


def _fmt_line(value):
    try:
        x = float(value)
        if np.isfinite(x):
            return f"{x:+.1f}"
    except Exception:
        pass
    return "—"


def _fmt_odds(value):
    try:
        x = float(value)
        if np.isfinite(x):
            return f"{int(round(x)):+d}"
    except Exception:
        pass
    return "—"


def _render_step6(day_str: str, pregame: pd.DataFrame, projected: pd.DataFrame, ready_lines: pd.DataFrame, model_ready: bool):
    st.markdown("### 📈 Step 6 — Cover Probability + Fair Spread")
    st.caption(
        "Analytical pre-Monte-Carlo layer • Step-5 projected margin stays fixed. Date-cut empirical team/league margin variance "
        "sets uncertainty; the verified Step-4 spread is only the cover threshold. Integer lines receive explicit push probability."
    )

    if pregame is None or pregame.empty:
        st.info("ℹ️ STEP 6 NOT APPLICABLE • no clock-safe pregame games remain.")
        return pd.DataFrame(), {"state":"N/A", "games":0, "covered_games":0, "rows":0, "model_ready":False}
    if not model_ready:
        st.warning("🔒 STEP 6 LOCKED • every pregame game must have a trustworthy independent Step-5 margin first.")
        return pd.DataFrame(), {"state":"LOCKED", "games":int(len(pregame)), "covered_games":0, "rows":0, "model_ready":False}
    if ready_lines is None or ready_lines.empty:
        st.warning("🔒 STEP 6 LOCKED • no current exact Step-4 sportsbook spread pairs are available for comparison.")
        return pd.DataFrame(), {"state":"LOCKED", "games":int(len(pregame)), "covered_games":0, "rows":0, "model_ready":False}

    with st.spinner("📈 Converting independent margins into analytical cover probabilities…"):
        board, meta = probability.probability_board(day_str, pregame, projected, ready_lines)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Game coverage", f"{int(meta.get('covered_games',0))}/{int(meta.get('games',0))}")
    c2.metric("Probability rows", int(meta.get("rows",0)))
    c3.metric("READY", int(meta.get("ready",0)))
    c4.metric("MONITOR", int(meta.get("monitor",0)))

    prob_ready = bool(meta.get("model_ready", False))
    if prob_ready:
        st.success("✅ STEP 6 PASSED • every pregame game has a cover distribution, fair spread and fair odds without changing the Step-5 projected margin.")
        if int(meta.get("monitor", 0)):
            st.info(f"🟦 {int(meta.get('monitor',0))} book-row probability result(s) are MONITOR because of short-sample or upstream uncertainty. Step 7 must retain those flags.")
    else:
        st.warning("⚠️ STEP 6 CHECK • at least one pregame game lacks a trustworthy empirical margin distribution. 5M remains locked.")

    if board is not None and not board.empty:
        show = board.copy()
        show["Game"] = show["away_team"].astype(str) + " @ " + show["home_team"].astype(str)
        show["Market"] = show.apply(
            lambda r: f"{r.get('away_team')} {_fmt_line(r.get('away_spread'))} / {r.get('home_team')} {_fmt_line(r.get('home_spread'))}", axis=1
        )
        show["Fair spread"] = show.apply(
            lambda r: f"{r.get('away_team')} {_fmt_line(r.get('fair_away_spread'))} / {r.get('home_team')} {_fmt_line(r.get('fair_home_spread'))}", axis=1
        )
        show["Away cover"] = show["away_cover"].map(_fmt_pct)
        show["Home cover"] = show["home_cover"].map(_fmt_pct)
        show["Push"] = show["push"].map(_fmt_pct)
        show["Margin σ"] = show["sigma"].map(lambda x: _fmt(x,1))
        show["80% margin range"] = show.apply(lambda r: f"{_fmt(r.get('margin_low80'),1)} to {_fmt(r.get('margin_high80'),1)} home margin", axis=1)
        st.dataframe(
            show[["Game", "first_tip_et", "book", "Market", "Fair spread", "Away cover", "Home cover", "Push", "Margin σ", "state"]].rename(
                columns={"first_tip_et":"Tip ET", "book":"Book", "state":"State"}
            ),
            use_container_width=True,
            hide_index=True,
        )

        with st.expander("🧮 Step 6 probability audit — fair odds + no-vig comparison", expanded=False):
            audit = show.copy()
            audit["Away fair odds"] = audit["away_fair_odds"].map(_fmt_odds)
            audit["Home fair odds"] = audit["home_fair_odds"].map(_fmt_odds)
            audit["Away no-vig mkt"] = audit["away_market_novig"].map(_fmt_pct)
            audit["Home no-vig mkt"] = audit["home_market_novig"].map(_fmt_pct)
            audit["Away model no-push"] = audit["away_no_push"].map(_fmt_pct)
            audit["Home model no-push"] = audit["home_no_push"].map(_fmt_pct)
            audit["Away edge"] = audit["away_edge_pp"].map(lambda x: "—" if pd.isna(x) else f"{float(x):+.1f} pp")
            audit["Home edge"] = audit["home_edge_pp"].map(lambda x: "—" if pd.isna(x) else f"{float(x):+.1f} pp")
            audit["Margin sample"] = audit.apply(
                lambda r: f"away {int(r.get('away_margin_games',0) or 0)} / home {int(r.get('home_margin_games',0) or 0)} / league {int(r.get('league_margin_games',0) or 0)}", axis=1
            )
            st.dataframe(
                audit[[
                    "Game", "Book", "Away fair odds", "Home fair odds",
                    "Away model no-push", "Home model no-push", "Away no-vig mkt", "Home no-vig mkt",
                    "Away edge", "Home edge", "Margin sample", "80% margin range", "State",
                ]],
                use_container_width=True,
                hide_index=True,
            )
            st.caption(
                "Fair odds use model cover probability normalized for pushes. Market no-vig probability uses only the same-book two-sided prices. "
                "These comparisons do not feed back into the projected margin. Step 6 is analytical; 5M Monte Carlo remains OFF."
            )

        # Useful handoff for Step 7 while remaining page-local and read-only to all other markets.
        st.session_state["wnba_spread_v15_probability_board"] = board.copy()
        st.session_state["wnba_spread_v15_probability_date"] = str(day_str)

    meta = dict(meta)
    meta["model_ready"] = prob_ready
    return board, meta


def render_wnba_spread_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.markdown("## 🏀 WNBA Spread Command Center")
    st.caption(
        "V1.5 • verified slate → clock-safe pregame guard → team context → availability → exact spread → independent margin → "
        "cover probability/fair spread. 5M Monte Carlo remains OFF."
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

    projected, step5 = prior._render_step5(day_str, pregame, contexts, market_ready)
    margin_ready = bool(step5.get("model_ready", False))

    probability_board, step6 = _render_step6(day_str, pregame, projected, ready_lines, margin_ready)
    probability_ready = bool(step6.get("model_ready", False))

    st.markdown("### 🔒 Spread Production Locks")
    locks = pd.DataFrame([
        {"Layer": "Verified slate", "State": "READY" if len(schedule) else "CHECK"},
        {"Layer": "Clock-safe pregame eligibility", "State": "READY" if len(pregame) else "NO ELIGIBLE GAMES"},
        {"Layer": "Team context", "State": "READY" if context_state == "VERIFIED" else "CHECK"},
        {"Layer": "Current availability", "State": "READY" if availability_ready else ("N/A" if not len(pregame) else "CHECK")},
        {"Layer": "Exact sportsbook spread line", "State": "READY" if market_ready else ("N/A" if not len(pregame) else "CHECK")},
        {"Layer": "Projected game margin", "State": "READY" if margin_ready else ("N/A" if not len(pregame) else "CHECK")},
        {"Layer": "Cover probability / fair spread", "State": "READY" if probability_ready else ("N/A" if not len(pregame) else "CHECK")},
        {"Layer": "5M Monte Carlo", "State": "NEXT" if probability_ready else "OFF"},
        {"Layer": "Daily Picks connector", "State": "OFF"},
    ], columns=["Layer", "State"])
    st.dataframe(locks, use_container_width=True, hide_index=True)
    st.info(
        "V1.5 adds analytical cover probability, push probability, fair odds and fair spread. The Step-5 mean remains market-independent. "
        "No simulation has been run; 5M Monte Carlo is Step 7."
    )


__all__ = ["MODEL_VERSION", "_render_step6", "render_wnba_spread_hub"]
