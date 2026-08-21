"""WNBA Spread V1.6 — Step 7 actual 5M Monte Carlo + final spread grading.

Preserves Steps 1-6. The Step-7 button runs exactly 5,000,000 discrete final-margin
draws per game in bounded batches, reusing the same game outcomes across books.
Results are accepted only for the exact current Step-6 snapshot fingerprint.
Daily Picks remains OFF until Step 8.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

import wnba_spread_hub_v151 as step6_ui
import wnba_spread_monte_carlo_v16 as monte

base = step6_ui.base
foundation = base.foundation
clock = base.clock
ui = base.ui
ET = base.ET
MODEL_VERSION = "WNBA SPREAD V1.6 • 5M MONTE CARLO + FINAL GRADING"

# Preserve the hardened Step-4 market adapter and repaired Step-6 renderer.
ui._spread_market_snapshot = base.prior.step4_integrity.market.spread_market_snapshot
base._render_step6 = step6_ui._render_step6


def _fmt(value, digits=1):
    return base._fmt(value, digits)


def _fmt_pct(value, digits=1):
    return base._fmt_pct(value, digits)


def _fmt_line(value):
    return base._fmt_line(value)


def _fmt_odds(value):
    return base._fmt_odds(value)


def _fmt_ev(value):
    try:
        x = float(value)
        if np.isfinite(x):
            return f"{100.0*x:+.1f}%"
    except Exception:
        pass
    return "—"


def _render_step7(day_str: str, pregame: pd.DataFrame, board: pd.DataFrame, probability_ready: bool):
    st.markdown("### 🎲 Step 7 — 5,000,000 Monte Carlo + Final Spread Grading")
    st.caption(
        "Exactly 5,000,000 discrete final-margin outcomes per game • 20 × 250,000 streaming batches • "
        "same simulated game outcomes reused across books • explicit pushes • deterministic snapshot seed • convergence audit."
    )

    if pregame is None or pregame.empty:
        st.info("ℹ️ STEP 7 NOT APPLICABLE • no clock-safe pregame games remain.")
        return pd.DataFrame(), pd.DataFrame(), {"state":"N/A", "model_ready":False}
    if not probability_ready or board is None or board.empty:
        st.warning("🔒 STEP 7 LOCKED • Step 6 must pass for every pregame game before the 5M button unlocks.")
        return pd.DataFrame(), pd.DataFrame(), {"state":"LOCKED", "model_ready":False}

    fingerprint = monte.board_fingerprint(day_str, board)
    saved_detail = st.session_state.get("wnba_spread_v16_mc_detail")
    saved_final = st.session_state.get("wnba_spread_v16_mc_final")
    saved_meta = st.session_state.get("wnba_spread_v16_mc_meta") or {}
    saved_date = str(st.session_state.get("wnba_spread_v16_mc_date") or "")
    saved_fp = str(saved_meta.get("fingerprint") or "")
    saved_valid = bool(
        saved_date == str(day_str) and saved_fp == fingerprint
        and isinstance(saved_detail, pd.DataFrame) and not saved_detail.empty
        and isinstance(saved_final, pd.DataFrame)
    )

    if saved_date and (saved_date != str(day_str) or (saved_fp and saved_fp != fingerprint)):
        st.warning("🛡️ Previous Spread 5M result is from a different date/line/projection snapshot and is not being reused.")

    run = st.button(
        "🚀 RUN SPREAD 5,000,000 MONTE CARLO",
        key="wnba_spread_v16_run_5m",
        use_container_width=True,
        type="primary",
    )

    detail = saved_detail if saved_valid else pd.DataFrame()
    final = saved_final if saved_valid else pd.DataFrame()
    meta = dict(saved_meta) if saved_valid else {}

    if run:
        progress = st.progress(0.0, text="Starting 5M spread simulation…")
        status = st.empty()

        def _progress(done, total):
            frac = min(1.0, max(0.0, float(done) / max(1, int(total))))
            progress.progress(frac, text=f"Spread Monte Carlo • {done}/{total} batches")
            status.caption(f"Completed {done * monte.BATCH_SIZE:,} of {max(1, int(total)) * monte.BATCH_SIZE:,} streamed game-draw slots")

        with st.spinner("🎲 Running actual 5,000,000-draw WNBA spread simulation…"):
            detail, final, meta = monte.run_monte_carlo(day_str, board, progress_callback=_progress)
        progress.progress(1.0, text="Spread 5M Monte Carlo complete")
        status.empty()

        st.session_state["wnba_spread_v16_mc_detail"] = detail.copy() if isinstance(detail, pd.DataFrame) else pd.DataFrame()
        st.session_state["wnba_spread_v16_mc_final"] = final.copy() if isinstance(final, pd.DataFrame) else pd.DataFrame()
        st.session_state["wnba_spread_v16_mc_meta"] = dict(meta or {})
        st.session_state["wnba_spread_v16_mc_date"] = str(day_str)

    if not isinstance(detail, pd.DataFrame) or detail.empty:
        st.info("Run the 5M pass once. No simulation result is fabricated before the button is pressed.")
        return pd.DataFrame(), pd.DataFrame(), {"state":"READY_TO_RUN", "model_ready":False, "fingerprint":fingerprint}

    mc_ready = bool(str(meta.get("state") or "CHECK").upper() == "READY")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Games simulated", f"{int(meta.get('covered_games',0))}/{int(meta.get('games',0))}")
    c2.metric("5M-converged rows", f"{int(meta.get('converged_rows',0))}/{int(meta.get('rows',0))}")
    c3.metric("Qualified games", int(meta.get("qualified_games",0)))
    c4.metric("Simulation", f"{int(meta.get('simulations_per_game',0)):,} / game")

    if mc_ready:
        st.success("✅ STEP 7 PASSED • every exact spread row completed 5M, met convergence checks, and retained the frozen Step-5/Step-6 snapshot.")
    else:
        st.warning("⚠️ STEP 7 CHECK • at least one row failed the simulation/convergence contract. Step 8 remains locked.")

    st.caption(
        f"Run: {meta.get('run_at_et','—')} • seed {meta.get('seed','—')} • "
        f"{int(meta.get('batches',0))} batches × {int(meta.get('batch_size',0)):,} • "
        f"total unique game draws {int(meta.get('total_game_draws',0)):,}"
    )

    show = detail.copy()
    show["Game"] = show["away_team"].astype(str) + " @ " + show["home_team"].astype(str)
    show["Book"] = show["book"].astype(str)
    show["Market"] = show.apply(
        lambda r: f"{r.get('away_team')} {_fmt_line(r.get('away_spread'))} / {r.get('home_team')} {_fmt_line(r.get('home_spread'))}", axis=1
    )
    show["MC away"] = show["mc_away_no_push"].map(_fmt_pct)
    show["MC home"] = show["mc_home_no_push"].map(_fmt_pct)
    show["Push"] = show["mc_push"].map(_fmt_pct)
    show["Best side"] = show.apply(lambda r: f"{r.get('best_side')} {_fmt_line(r.get('best_spread'))}", axis=1)
    show["Best cover"] = show["best_cover_no_push"].map(_fmt_pct)
    show["Edge"] = show["best_edge_pp"].map(lambda x: "—" if pd.isna(x) else f"{float(x):+.1f} pp")
    show["Converged"] = show["converged"].map(lambda x: "PASS" if bool(x) else "CHECK")
    st.dataframe(
        show[["Game", "Book", "Market", "MC away", "MC home", "Push", "Best side", "Best cover", "Edge", "grade", "Converged"]].rename(columns={"grade":"Grade"}),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("#### 🏆 Final Spread Production Grading — one candidate per game")
    st.caption("No forced plays. QUALIFIED requires ≥55% MC no-push cover probability, ≥+3.0 percentage-point no-vig edge, READY convergence, and positive EV when a valid price exists.")
    if isinstance(final, pd.DataFrame) and not final.empty:
        card = final.copy()
        card["Game"] = card["away_team"].astype(str) + " @ " + card["home_team"].astype(str)
        card["Exact book"] = card["book"].astype(str)
        card["Candidate"] = card.apply(lambda r: f"{r.get('best_side')} {_fmt_line(r.get('best_spread'))} ({_fmt_odds(r.get('best_price'))})", axis=1)
        card["MC cover"] = card["best_cover_no_push"].map(_fmt_pct)
        card["MC fair odds"] = card.apply(
            lambda r: _fmt_odds(r.get("mc_home_fair_odds") if str(r.get("best_side")) == str(r.get("home_team")) else r.get("mc_away_fair_odds")), axis=1
        )
        card["No-vig edge"] = card["best_edge_pp"].map(lambda x: "—" if pd.isna(x) else f"{float(x):+.1f} pp")
        card["EV"] = card["best_ev"].map(_fmt_ev)
        st.dataframe(
            card[["Game", "Exact book", "Candidate", "MC cover", "MC fair odds", "No-vig edge", "EV", "grade"]].rename(columns={"grade":"Grade"}),
            use_container_width=True,
            hide_index=True,
        )

    with st.expander("🧪 Step 7 Monte Carlo convergence audit", expanded=False):
        audit = show.copy()
        audit["MC SE"] = audit["mc_se_pp"].map(lambda x: "—" if pd.isna(x) else f"{float(x):.3f} pp")
        audit["Max batch dev"] = audit["max_batch_deviation_pp"].map(lambda x: "—" if pd.isna(x) else f"{float(x):.3f} pp")
        audit["vs Step 6"] = audit["analytic_delta_pp"].map(lambda x: "—" if pd.isna(x) else f"{float(x):.3f} pp")
        audit["Sim mean margin"] = audit["simulated_mean_home_margin"].map(lambda x: _fmt(x,3))
        audit["Target mean"] = audit["projected_home_margin"].map(lambda x: _fmt(x,3))
        audit["Sim σ"] = audit["simulated_margin_sd"].map(lambda x: _fmt(x,3))
        audit["Target σ"] = audit["sigma"].map(lambda x: _fmt(x,3))
        audit["Sims"] = audit["simulation_count"].map(lambda x: f"{int(x):,}")
        st.dataframe(
            audit[["Game", "Book", "Sims", "seed", "MC SE", "Max batch dev", "vs Step 6", "Sim mean margin", "Target mean", "Sim σ", "Target σ", "Converged"]].rename(columns={"seed":"Seed"}),
            use_container_width=True,
            hide_index=True,
        )
        contract = meta.get("convergence_contract") or {}
        st.caption(
            f"Convergence requires MC SE ≤ {contract.get('max_mc_se_pp', monte.MAX_MC_SE_PP):.2f} pp, "
            f"max batch deviation ≤ {contract.get('max_batch_deviation_pp', monte.MAX_BATCH_DEVIATION_PP):.2f} pp, "
            f"and |5M − Step 6 analytical| ≤ {contract.get('max_analytic_delta_pp', monte.MAX_ANALYTIC_DELTA_PP):.2f} pp."
        )

    meta = dict(meta)
    meta["model_ready"] = mc_ready
    return detail, final, meta


def render_wnba_spread_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.markdown("## 🏀 WNBA Spread Command Center")
    st.caption(
        "V1.6 • verified slate → clock-safe pregame guard → team context → availability → exact spread → independent margin → "
        "analytical probability → actual 5M Monte Carlo + final grading. Daily Picks remains OFF until Step 8."
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
    c4.metric("Model state", "STEP 7")
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
            contexts, cdiag = {}, {"state":"CHECK", "reason":type(exc).__name__}

    context_state = str(cdiag.get("state") or "CHECK").upper()
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Context state", context_state)
    d2.metric("Records verified", f"{int(cdiag.get('records_verified',0) or 0)}/{int(cdiag.get('teams',teams) or teams)}")
    d3.metric("Advanced teams", int(cdiag.get("advanced_teams",0) or 0))
    d4.metric("H2H samples", int(cdiag.get("h2h_samples",0) or 0))
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

    projected, step5 = base.prior._render_step5(day_str, pregame, contexts, market_ready)
    margin_ready = bool(step5.get("model_ready", False))

    probability_board, step6 = step6_ui._render_step6(day_str, pregame, projected, ready_lines, margin_ready)
    probability_ready = bool(step6.get("model_ready", False))

    mc_detail, mc_final, step7 = _render_step7(day_str, pregame, probability_board, probability_ready)
    mc_ready = bool(step7.get("model_ready", False))

    st.markdown("### 🔒 Spread Production Locks")
    locks = pd.DataFrame([
        {"Layer":"Verified slate", "State":"READY" if len(schedule) else "CHECK"},
        {"Layer":"Clock-safe pregame eligibility", "State":"READY" if len(pregame) else "NO ELIGIBLE GAMES"},
        {"Layer":"Team context", "State":"READY" if context_state == "VERIFIED" else "CHECK"},
        {"Layer":"Current availability", "State":"READY" if availability_ready else ("N/A" if not len(pregame) else "CHECK")},
        {"Layer":"Exact sportsbook spread line", "State":"READY" if market_ready else ("N/A" if not len(pregame) else "CHECK")},
        {"Layer":"Projected game margin", "State":"READY" if margin_ready else ("N/A" if not len(pregame) else "CHECK")},
        {"Layer":"Cover probability / fair spread", "State":"READY" if probability_ready else ("N/A" if not len(pregame) else "CHECK")},
        {"Layer":"5M Monte Carlo", "State":"READY" if mc_ready else ("RUN 5M" if probability_ready else "LOCKED")},
        {"Layer":"Daily Picks connector", "State":"NEXT" if mc_ready else "OFF"},
    ])
    st.dataframe(locks[["Layer", "State"]], use_container_width=True, hide_index=True)
    st.info(
        "V1.6 completes the independent pregame Spread production model through actual 5M simulation and one-candidate-per-game grading. "
        "Nothing is sent to Daily Picks yet; Step 8 is the read-only connector + final production guard."
    )


__all__ = ["MODEL_VERSION", "_render_step7", "render_wnba_spread_hub"]
