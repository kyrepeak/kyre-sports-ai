"""WNBA Game Total V1.4 — Step 7 actual 5M Monte Carlo.

Preserves Game Total V1.3 Steps 1-6 exactly and adds Step 7 only. The Step-7 button
runs exactly 5,000,000 integer-valued full-game total outcomes per unique game in
20 bounded 250,000-draw batches. One simulated game stream is reused across every
sportsbook total row for that game. Step-5 mean and Step-6 empirical sigma stay
frozen; sportsbook total/price inputs remain zero inside the simulation.

No final Game Total grading/ranking, staking or Daily Picks output is introduced.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

import wnba_game_total_hub_v13 as step6
import wnba_game_total_monte_carlo_v14 as monte

step5 = step6.prior
step4 = step5.prior
base = step4.prior

MODEL_VERSION = "WNBA GAME TOTAL V1.4 • 5M MONTE CARLO"
ET = step6.ET
foundation = step6.foundation
clock = step6.clock
spread_current = step6.spread_current


def _num(value, default=np.nan):
    try:
        x = float(value)
        return x if np.isfinite(x) else default
    except Exception:
        return default


def _fmt(value, digits=1):
    x = _num(value, np.nan)
    return "—" if not np.isfinite(x) else f"{x:.{digits}f}"


def _fmt_pct(value, digits=1):
    x = _num(value, np.nan)
    return "—" if not np.isfinite(x) else f"{100.0*x:.{digits}f}%"


def _fmt_pp(value, digits=2):
    x = _num(value, np.nan)
    return "—" if not np.isfinite(x) else f"{x:.{digits}f} pp"


def _fmt_price(value):
    x = _num(value, np.nan)
    return "—" if not np.isfinite(x) else f"{int(round(x)):+d}"


def _render_step7(day_str: str, probability_rows: pd.DataFrame, probability_ready: bool):
    st.markdown("### 🎲 Step 7 — 5,000,000 Monte Carlo + Convergence / Sensitivity")
    st.caption(
        "Exactly 5,000,000 market-independent integer full-game total outcomes per unique game • "
        "20 × 250,000 streaming batches • same game outcomes reused across books • deterministic snapshot seed • "
        "±5% projected-total sensitivity • sportsbook simulation input = ZERO."
    )

    if not probability_ready or probability_rows is None or probability_rows.empty:
        st.warning("🔒 STEP 7 LOCKED • Step 6 must pass for every pregame game before the 5M button unlocks.")
        return pd.DataFrame(), {"state": "LOCKED", "simulation_ready": False}

    fingerprint = monte.board_fingerprint(day_str, probability_rows)
    saved_records = st.session_state.get("wnba_game_total_v14_mc_records") or []
    saved_meta = st.session_state.get("wnba_game_total_v14_mc_meta") or {}
    saved_day = str(st.session_state.get("wnba_game_total_v14_mc_day") or "")
    saved_fp = str(saved_meta.get("fingerprint") or "")
    saved_detail = pd.DataFrame(saved_records) if isinstance(saved_records, list) else pd.DataFrame()
    saved_valid = bool(
        saved_day == str(day_str)
        and saved_fp == fingerprint
        and not saved_detail.empty
    )

    if saved_day and not saved_valid:
        st.warning("🛡️ Previous Game Total 5M result belongs to a different date/line/price/model snapshot and is not being reused.")

    run = st.button(
        "🚀 RUN GAME TOTAL 5,000,000 MONTE CARLO",
        key="wnba_game_total_v14_run_5m",
        use_container_width=True,
        type="primary",
    )

    detail = saved_detail.copy() if saved_valid else pd.DataFrame()
    meta = dict(saved_meta) if saved_valid else {}

    if run:
        progress = st.progress(0.0, text="Starting Game Total 5M simulation…")
        status = st.empty()

        def _progress(done, total):
            frac = min(1.0, max(0.0, float(done) / max(1, int(total))))
            progress.progress(frac, text=f"Game Total Monte Carlo • {done}/{total} batches")
            status.caption(
                f"Completed {done * monte.BATCH_SIZE:,} of {max(1, int(total)) * monte.BATCH_SIZE:,} streamed game-draw slots"
            )

        with st.spinner("🎲 Running actual 5,000,000-draw WNBA Game Total simulation…"):
            detail, meta = monte.run_monte_carlo(day_str, probability_rows, progress_callback=_progress)
        progress.progress(1.0, text="Game Total 5M Monte Carlo complete")
        status.empty()

        st.session_state["wnba_game_total_v14_mc_records"] = detail.to_dict("records") if isinstance(detail, pd.DataFrame) and not detail.empty else []
        st.session_state["wnba_game_total_v14_mc_meta"] = dict(meta or {})
        st.session_state["wnba_game_total_v14_mc_day"] = str(day_str)

    if detail is None or detail.empty:
        st.info("Run the 5M pass once. No simulation result is fabricated before the button is pressed.")
        return pd.DataFrame(), {"state": "READY_TO_RUN", "simulation_ready": False, "fingerprint": fingerprint}

    simulation_ready = bool(meta.get("simulation_ready", False))
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Games simulated", f"{int(meta.get('covered_games', 0))}/{int(meta.get('games', 0))}")
    c2.metric("Converged rows", f"{int(meta.get('converged_rows', 0))}/{int(meta.get('rows', 0))}")
    c3.metric("Trials / game", f"{int(meta.get('simulations_per_game', 0)):,}")
    c4.metric("Sportsbook sim inputs", int(meta.get("sportsbook_simulation_inputs", 0)))

    if simulation_ready:
        st.success(
            "✅ STEP 7 PASSED • every pregame game completed exactly 5,000,000 simulations and met the convergence contract; "
            "the frozen Step-5 total distribution was preserved across all sportsbook comparisons."
        )
    else:
        st.warning("⚠️ STEP 7 CHECK • at least one game/row failed the 5M convergence contract. Final grading remains locked.")

    st.caption(
        f"Run: {meta.get('run_at_et', '—')} • snapshot seed {meta.get('seed', '—')} • "
        f"{int(meta.get('batches', 0))} batches × {int(meta.get('batch_size', 0)):,} • "
        f"total unique game draws {int(meta.get('total_game_draws', 0)):,}"
    )

    show = detail.copy()
    show["Game"] = show["away_team"].astype(str) + " @ " + show["home_team"].astype(str)
    show["Book"] = show["book"].astype(str)
    show["Market total"] = show["market_total"].map(_fmt)
    show["MC over"] = show["mc_over_prob"].map(_fmt_pct)
    show["MC under"] = show["mc_under_prob"].map(_fmt_pct)
    show["Push"] = show["mc_push_prob"].map(_fmt_pct)
    show["MC over fair"] = show["mc_over_fair_odds"].map(_fmt_price)
    show["MC under fair"] = show["mc_under_fair_odds"].map(_fmt_price)
    show["Over edge"] = show["mc_over_edge_pp"].map(lambda x: "—" if not np.isfinite(_num(x)) else f"{float(x):+.1f} pp")
    show["Under edge"] = show["mc_under_edge_pp"].map(lambda x: "—" if not np.isfinite(_num(x)) else f"{float(x):+.1f} pp")
    show["State"] = show["mc_state"].astype(str)
    show["Converged"] = show["converged"].map(lambda x: "PASS" if bool(x) else "CHECK")
    st.dataframe(
        show[[
            "Game", "Book", "Market total", "MC over", "MC under", "Push",
            "MC over fair", "MC under fair", "Over edge", "Under edge", "State", "Converged",
        ]],
        use_container_width=True,
        hide_index=True,
    )

    with st.expander("🧪 Step 7 Monte Carlo convergence audit", expanded=False):
        audit = show.copy()
        audit["Sims"] = audit["simulation_count"].map(lambda x: f"{int(x):,}")
        audit["MC SE"] = audit["mc_se_pp"].map(_fmt_pp)
        audit["Max batch dev"] = audit["max_batch_deviation_pp"].map(_fmt_pp)
        audit["vs Step 6"] = audit["analytic_delta_pp"].map(_fmt_pp)
        audit["Sim mean"] = audit["simulated_mean_total"].map(lambda x: _fmt(x, 3))
        audit["Target mean"] = audit["projected_total"].map(lambda x: _fmt(x, 3))
        audit["Sim σ"] = audit["simulated_total_sd"].map(lambda x: _fmt(x, 3))
        audit["Target σ"] = audit["sigma"].map(lambda x: _fmt(x, 3))
        st.dataframe(
            audit[["Game", "Book", "Sims", "seed", "MC SE", "Max batch dev", "vs Step 6", "Sim mean", "Target mean", "Sim σ", "Target σ", "Converged"]].rename(columns={"seed": "Seed"}),
            use_container_width=True,
            hide_index=True,
        )
        contract = meta.get("convergence_contract") or {}
        st.caption(
            f"Convergence requires MC SE ≤ {contract.get('max_mc_se_pp', monte.MAX_MC_SE_PP):.2f} pp, "
            f"max batch deviation ≤ {contract.get('max_batch_deviation_pp', monte.MAX_BATCH_DEVIATION_PP):.2f} pp, "
            f"and |5M − Step-6 analytical probability| ≤ {contract.get('max_analytic_delta_pp', monte.MAX_ANALYTIC_DELTA_PP):.2f} pp."
        )

    with st.expander("🎚️ Step 7 ±5% projected-total sensitivity", expanded=False):
        sens = show.copy()
        sens["Base Over"] = sens["mc_over_no_push"].map(_fmt_pct)
        sens["Low-mean Over"] = sens["sensitivity_low_over_prob"].map(_fmt_pct)
        sens["High-mean Over"] = sens["sensitivity_high_over_prob"].map(_fmt_pct)
        sens["Base Under"] = sens["mc_under_no_push"].map(_fmt_pct)
        sens["Low-mean Under"] = sens["sensitivity_low_under_prob"].map(_fmt_pct)
        sens["High-mean Under"] = sens["sensitivity_high_under_prob"].map(_fmt_pct)
        sens["Probability span"] = sens["sensitivity_span_pp"].map(_fmt_pp)
        sens["Mean range"] = sens.apply(
            lambda r: f"{_fmt(r.get('sensitivity_low_mean'),2)} → {_fmt(r.get('sensitivity_high_mean'),2)}", axis=1
        )
        st.dataframe(
            sens[["Game", "Book", "Market total", "Base Over", "Low-mean Over", "High-mean Over", "Base Under", "Low-mean Under", "High-mean Under", "Probability span", "Mean range", "State"]],
            use_container_width=True,
            hide_index=True,
        )
        st.caption("Sensitivity reuses the identical random shocks and shifts only the frozen projected total mean by ±5%. Sportsbook prices are not used.")

    meta = dict(meta)
    meta["simulation_ready"] = simulation_ready
    return detail, meta


def render_wnba_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.markdown("## 🧮 WNBA Game Total Command Center")
    st.caption(
        "V1.4 • verified slate → clock-safe pregame guard → total-scoring team context → exact-day availability → exact sportsbook total → "
        "independent projected total → line-specific O/U probability + fair total → actual 5M Monte Carlo. Final grading remains OFF."
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
            base._render_game_context(game, contexts, av_map)

    foundation_ready = bool(len(pregame) and context_state == "VERIFIED" and availability_ready)
    market_rows, market_meta = step4._render_step4(day_str, pregame, foundation_ready)
    market_ready = bool(market_meta.get("market_ready", False))
    projection_rows, projection_meta = step5._render_step5(day_str, pregame, contexts, market_ready)
    projection_ready = bool(projection_meta.get("model_ready", False))
    probability_rows, probability_meta = step6._render_step6(day_str, pregame, projection_rows, market_rows, projection_ready)
    probability_ready = bool(probability_meta.get("model_ready", False))
    mc_rows, mc_meta = _render_step7(day_str, probability_rows, probability_ready)
    simulation_ready = bool(mc_meta.get("simulation_ready", False))

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
    st.session_state["wnba_game_total_v14_mc_rows"] = mc_rows.to_dict("records") if isinstance(mc_rows,pd.DataFrame) and not mc_rows.empty else []
    st.session_state["wnba_game_total_v14_mc_ready"] = simulation_ready

    st.markdown("### 🔒 Game Total Production Locks")
    if simulation_ready:
        mc_state = "READY"
    elif str(mc_meta.get("state") or "").upper() == "CHECK":
        mc_state = "CHECK"
    elif probability_ready:
        mc_state = "RUN 5M"
    else:
        mc_state = "LOCKED"

    locks = pd.DataFrame([
        {"Layer":"Verified slate","State":"READY" if len(schedule) else "CHECK"},
        {"Layer":"Clock-safe pregame eligibility","State":"READY" if len(pregame) else "NO ELIGIBLE GAMES"},
        {"Layer":"Total-scoring team context","State":"READY" if context_state == "VERIFIED" else "CHECK"},
        {"Layer":"Current availability","State":"READY" if availability_ready else ("N/A" if expected_coverage == 0 else "CHECK")},
        {"Layer":"Exact sportsbook game total","State":"READY" if market_ready else ("N/A" if not len(pregame) else "CHECK")},
        {"Layer":"Independent projected game total","State":"READY" if projection_ready else ("NEXT" if market_ready else "LOCKED")},
        {"Layer":"Over/Under probability / fair total","State":"READY" if probability_ready else ("NEXT" if projection_ready else "LOCKED")},
        {"Layer":"5M Monte Carlo","State":mc_state},
        {"Layer":"Final Game Total grading","State":"NEXT" if simulation_ready else "OFF"},
        {"Layer":"Daily Picks connector","State":"OFF"},
    ])
    st.dataframe(locks, use_container_width=True, hide_index=True)
    st.info(
        "V1.4 completes the independent Game Total model through the actual 5,000,000-draw Step-7 simulation. "
        "No Game Total pick is published yet. Risk-adjusted final grading is the next layer; Daily Picks remains OFF."
    )


__all__ = ["MODEL_VERSION", "render_wnba_game_total_hub", "_render_step7", "monte"]
