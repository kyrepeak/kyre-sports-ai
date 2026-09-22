"""WNBA Game Total V1.5 — Step 8 risk-adjusted final grading.

Preserves Game Total V1.4 Steps 1-7 exactly and adds Step 8 only.

Step 8 consumes only the current, converged 5,000,000-draw Step-7 rows. It does
not rerun or alter the Step-5 projected total, Step-6 distribution, or Step-7
simulations. For each game it evaluates Over and Under at every exact sportsbook
price, carries upstream READY/MONITOR state forward, applies transparent
production thresholds, checks the existing ±5% projected-total sensitivity, and
publishes at most one final Game Total candidate per game.

No play is forced. A QUALIFIED candidate requires:
- converged/current Step-7 simulation state = READY;
- Monte Carlo no-push win probability >= 55%;
- model-vs-same-book no-vig edge >= +3.0 percentage points;
- positive expected value at the exact posted price (pushes refunded);
- worst-case no-push probability across existing ±5% sensitivity > 50%.

A row that clears the numerical thresholds but carries an upstream MONITOR flag
remains MONITOR. Rows that miss the core thresholds are NO PLAY. Invalid or
non-converged rows are BLOCKED. Daily Picks remains OFF until the next isolated
read-only connector layer.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

import wnba_game_total_hub_v14 as prior

MODEL_VERSION = "WNBA GAME TOTAL V1.5 • RISK-ADJUSTED FINAL GRADING"
ET = prior.ET
foundation = prior.foundation
clock = prior.clock
spread_current = prior.spread_current
base = prior.base
step4 = prior.step4
step5 = prior.step5
step6 = prior.step6
monte = prior.monte

MIN_WIN_PROB = 0.55
MIN_EDGE_PP = 3.0
MIN_EV = 0.0
MIN_WORST_CASE_PROB = 0.50


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
    return "—" if not np.isfinite(x) else f"{100.0 * x:.{digits}f}%"


def _fmt_pp(value, digits=1):
    x = _num(value, np.nan)
    return "—" if not np.isfinite(x) else f"{x:+.{digits}f} pp"


def _fmt_price(value):
    x = _num(value, np.nan)
    return "—" if not np.isfinite(x) else f"{int(round(x)):+d}"


def _fmt_ev(value):
    x = _num(value, np.nan)
    return "—" if not np.isfinite(x) else f"{100.0 * x:+.1f}%"


def _profit_multiple(price):
    x = _num(price, np.nan)
    if not np.isfinite(x) or x == 0:
        return np.nan
    return float(x / 100.0) if x > 0 else float(100.0 / abs(x))


def _side_candidates(mc_detail: pd.DataFrame) -> pd.DataFrame:
    """Expand each exact-book Step-7 total row into Over/Under candidate rows."""
    if mc_detail is None or mc_detail.empty:
        return pd.DataFrame()

    rows = []
    for _, src in mc_detail.iterrows():
        base_over = _num(src.get("mc_over_no_push"), np.nan)
        base_under = _num(src.get("mc_under_no_push"), np.nan)
        low_over = _num(src.get("sensitivity_low_over_prob"), np.nan)
        high_over = _num(src.get("sensitivity_high_over_prob"), np.nan)
        low_under = _num(src.get("sensitivity_low_under_prob"), np.nan)
        high_under = _num(src.get("sensitivity_high_under_prob"), np.nan)
        market_total = _num(src.get("market_total"), np.nan)
        push_prob = _num(src.get("mc_push_prob"), np.nan)

        for side in ("OVER", "UNDER"):
            is_over = side == "OVER"
            price = _num(src.get("over_price") if is_over else src.get("under_price"), np.nan)
            prob = _num(src.get("mc_over_no_push") if is_over else src.get("mc_under_no_push"), np.nan)
            win_uncond = _num(src.get("mc_over_prob") if is_over else src.get("mc_under_prob"), np.nan)
            loss_uncond = _num(src.get("mc_under_prob") if is_over else src.get("mc_over_prob"), np.nan)
            market = _num(src.get("over_market_novig") if is_over else src.get("under_market_novig"), np.nan)
            edge = _num(src.get("mc_over_edge_pp") if is_over else src.get("mc_under_edge_pp"), np.nan)
            fair = _num(src.get("mc_over_fair_odds") if is_over else src.get("mc_under_fair_odds"), np.nan)
            sens_probs = [
                x for x in (
                    prob,
                    low_over if is_over else low_under,
                    high_over if is_over else high_under,
                ) if np.isfinite(x)
            ]
            worst_prob = min(sens_probs) if sens_probs else np.nan
            best_prob = max(sens_probs) if sens_probs else np.nan
            drop_pp = 100.0 * (prob - worst_prob) if np.isfinite(prob) and np.isfinite(worst_prob) else np.nan
            span_pp = 100.0 * (best_prob - worst_prob) if np.isfinite(best_prob) and np.isfinite(worst_prob) else np.nan

            profit = _profit_multiple(price)
            ev = win_uncond * profit - loss_uncond if all(np.isfinite(x) for x in (win_uncond, loss_uncond, profit)) else np.nan

            upstream = str(src.get("mc_state") or "CHECK").upper()
            converged = bool(src.get("converged", False))
            valid = bool(
                converged
                and upstream not in {"CHECK", "BLOCKED"}
                and np.isfinite(market_total)
                and np.isfinite(prob)
                and np.isfinite(win_uncond)
                and np.isfinite(loss_uncond)
                and np.isfinite(push_prob)
                and np.isfinite(market)
                and np.isfinite(edge)
                and np.isfinite(ev)
                and np.isfinite(price)
                and np.isfinite(worst_prob)
            )
            core_pass = bool(valid and prob >= MIN_WIN_PROB and edge >= MIN_EDGE_PP and ev > MIN_EV)
            sensitivity_pass = bool(valid and worst_prob > MIN_WORST_CASE_PROB)

            if not valid:
                grade = "BLOCKED"
                reason = "invalid/non-converged Step-7 row"
            elif not core_pass:
                grade = "NO PLAY"
                misses = []
                if prob < MIN_WIN_PROB:
                    misses.append("MC win <55%")
                if edge < MIN_EDGE_PP:
                    misses.append("edge <+3.0 pp")
                if ev <= MIN_EV:
                    misses.append("EV <=0")
                reason = "; ".join(misses) or "core production threshold missed"
            elif upstream != "READY":
                grade = "MONITOR"
                reason = "upstream Step-6/7 uncertainty flag carried forward"
            elif not sensitivity_pass:
                grade = "MONITOR"
                reason = "worst-case ±5% sensitivity falls to 50% or lower"
            else:
                grade = "QUALIFIED"
                reason = "all final Game Total guards passed"

            rows.append({
                "game_id": str(src.get("game_id") or ""),
                "away_team": str(src.get("away_team") or ""),
                "home_team": str(src.get("home_team") or ""),
                "first_tip_et": str(src.get("first_tip_et") or "—"),
                "book": str(src.get("book") or ""),
                "side": side,
                "market_total": market_total,
                "posted_price": price,
                "mc_win_prob": prob,
                "mc_fair_odds": fair,
                "market_novig": market,
                "edge_pp": edge,
                "ev": ev,
                "push_prob": push_prob,
                "worst_case_prob": worst_prob,
                "sensitivity_drop_pp": drop_pp,
                "sensitivity_span_pp": span_pp,
                "upstream_state": upstream,
                "converged": converged,
                "simulation_count": int(_num(src.get("simulation_count"), 0) or 0),
                "seed": int(_num(src.get("seed"), 0) or 0),
                "grade": grade,
                "reason": reason,
                "sportsbook_simulation_inputs": 0,
                "new_simulations": 0,
            })

    return pd.DataFrame(rows)


def _final_grade(mc_detail: pd.DataFrame, simulation_ready: bool):
    empty_meta = {
        "state": "LOCKED", "games": 0, "graded_games": 0,
        "qualified": 0, "monitor": 0, "no_play": 0, "blocked": 0,
        "grading_ready": False, "new_simulations": 0,
    }
    if not simulation_ready or mc_detail is None or mc_detail.empty:
        return pd.DataFrame(), pd.DataFrame(), empty_meta

    sides = _side_candidates(mc_detail)
    if sides.empty:
        return pd.DataFrame(), pd.DataFrame(), {**empty_meta, "state": "CHECK"}

    priority = {"QUALIFIED": 0, "MONITOR": 1, "NO PLAY": 2, "BLOCKED": 3}
    sides["_priority"] = sides["grade"].map(priority).fillna(9).astype(int)
    sides["_edge_sort"] = pd.to_numeric(sides["edge_pp"], errors="coerce").fillna(-1e9)
    sides["_ev_sort"] = pd.to_numeric(sides["ev"], errors="coerce").fillna(-1e9)
    sides["_prob_sort"] = pd.to_numeric(sides["mc_win_prob"], errors="coerce").fillna(-1e9)
    sides["_worst_sort"] = pd.to_numeric(sides["worst_case_prob"], errors="coerce").fillna(-1e9)

    ordered = sides.sort_values(
        ["game_id", "_priority", "_edge_sort", "_ev_sort", "_worst_sort", "_prob_sort", "book", "side"],
        ascending=[True, True, False, False, False, False, True, True],
        kind="stable",
    )
    final = ordered.drop_duplicates(subset=["game_id"], keep="first").copy()
    final = final.drop(columns=["_priority", "_edge_sort", "_ev_sort", "_prob_sort", "_worst_sort"], errors="ignore")
    sides = sides.drop(columns=["_priority", "_edge_sort", "_ev_sort", "_prob_sort", "_worst_sort"], errors="ignore")

    expected_games = int(mc_detail["game_id"].astype(str).nunique())
    graded_games = int(final["game_id"].astype(str).nunique())
    counts = final["grade"].astype(str).value_counts().to_dict()
    grading_ready = bool(
        expected_games > 0
        and graded_games == expected_games
        and not final["grade"].astype(str).eq("BLOCKED").any()
    )
    meta = {
        "state": "READY" if grading_ready else "CHECK",
        "games": expected_games,
        "graded_games": graded_games,
        "qualified": int(counts.get("QUALIFIED", 0)),
        "monitor": int(counts.get("MONITOR", 0)),
        "no_play": int(counts.get("NO PLAY", 0)),
        "blocked": int(counts.get("BLOCKED", 0)),
        "grading_ready": grading_ready,
        "new_simulations": 0,
    }
    return sides, final, meta


def _render_step8(day_str: str, mc_detail: pd.DataFrame, simulation_ready: bool):
    st.markdown("### 🏆 Step 8 — Risk-Adjusted Final Game Total Grading")
    st.caption(
        "No forced plays • one best exact O/U side/book per game • existing 5M result + same-book no-vig edge + "
        "exact-price EV + upstream uncertainty + existing ±5% projected-total sensitivity. Step 8 runs ZERO new simulations."
    )

    if not simulation_ready or mc_detail is None or mc_detail.empty:
        st.warning("🔒 STEP 8 LOCKED • a current converged Step-7 5M result is required before final Game Total grading.")
        return pd.DataFrame(), {"state": "LOCKED", "grading_ready": False}

    sides, final, meta = _final_grade(mc_detail, simulation_ready)
    grading_ready = bool(meta.get("grading_ready", False))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Games graded", f"{int(meta.get('graded_games', 0))}/{int(meta.get('games', 0))}")
    c2.metric("QUALIFIED", int(meta.get("qualified", 0)))
    c3.metric("MONITOR", int(meta.get("monitor", 0)))
    c4.metric("NO PLAY", int(meta.get("no_play", 0)))

    if grading_ready:
        st.success(
            "✅ STEP 8 PASSED • every simulated game received one risk-adjusted final Game Total decision. "
            "No play is forced; upstream MONITOR states remain MONITOR."
        )
    else:
        st.warning("⚠️ STEP 8 CHECK • at least one game could not receive a safe final decision. Daily Picks remains locked.")

    if not final.empty:
        show = final.copy()
        show["Game"] = show["away_team"].astype(str) + " @ " + show["home_team"].astype(str)
        show["Candidate"] = show.apply(
            lambda r: f"{r.get('side')} {_fmt(r.get('market_total'),1)} ({_fmt_price(r.get('posted_price'))})", axis=1
        )
        show["MC win"] = show["mc_win_prob"].map(_fmt_pct)
        show["Worst ±5%"] = show["worst_case_prob"].map(_fmt_pct)
        show["MC fair"] = show["mc_fair_odds"].map(_fmt_price)
        show["No-vig"] = show["market_novig"].map(_fmt_pct)
        show["Edge"] = show["edge_pp"].map(_fmt_pp)
        show["EV"] = show["ev"].map(_fmt_ev)
        show["Push"] = show["push_prob"].map(_fmt_pct)
        show["Sensitivity drop"] = show["sensitivity_drop_pp"].map(
            lambda x: "—" if not np.isfinite(_num(x)) else f"{float(x):.1f} pp"
        )
        st.dataframe(
            show[[
                "Game", "book", "Candidate", "MC win", "Worst ±5%", "MC fair", "No-vig",
                "Edge", "EV", "Push", "Sensitivity drop", "upstream_state", "grade", "reason",
            ]].rename(columns={
                "book": "Exact book", "upstream_state": "Upstream",
                "grade": "Grade", "reason": "Guard reason",
            }),
            use_container_width=True,
            hide_index=True,
        )

    with st.expander("🧪 Step 8 qualification audit — every exact O/U side/book", expanded=False):
        if sides.empty:
            st.info("No Step-8 side rows are available.")
        else:
            audit = sides.copy()
            audit["Game"] = audit["away_team"].astype(str) + " @ " + audit["home_team"].astype(str)
            audit["Candidate"] = audit.apply(
                lambda r: f"{r.get('side')} {_fmt(r.get('market_total'),1)} ({_fmt_price(r.get('posted_price'))})", axis=1
            )
            audit["MC win"] = audit["mc_win_prob"].map(_fmt_pct)
            audit["Worst ±5%"] = audit["worst_case_prob"].map(_fmt_pct)
            audit["Edge"] = audit["edge_pp"].map(_fmt_pp)
            audit["EV"] = audit["ev"].map(_fmt_ev)
            audit["Push"] = audit["push_prob"].map(_fmt_pct)
            audit["Sims"] = audit["simulation_count"].map(lambda x: f"{int(x):,}")
            st.dataframe(
                audit[[
                    "Game", "book", "Candidate", "MC win", "Worst ±5%", "Edge", "EV", "Push",
                    "Sims", "upstream_state", "grade", "reason",
                ]].rename(columns={
                    "book": "Book", "upstream_state": "Upstream",
                    "grade": "Grade", "reason": "Reason",
                }),
                use_container_width=True,
                hide_index=True,
            )
            st.caption(
                "QUALIFIED requires READY convergence, MC no-push win ≥55%, no-vig edge ≥+3.0 pp, positive exact-price EV, "
                "and worst-case ±5% no-push probability >50%. Integer-total pushes are refunded in EV; no play is forced."
            )

    return final, meta


def render_wnba_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.markdown("## 🧮 WNBA Game Total Command Center")
    st.caption(
        "V1.5 • verified slate → clock-safe pregame guard → total-scoring team context → exact-day availability → exact sportsbook total → "
        "independent projected total → line-specific O/U probability + fair total → actual 5M Monte Carlo → risk-adjusted final grading."
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
    c4.metric("Model state", "STEP 8")
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
            contexts, cdiag = {}, {"state": "CHECK", "reason": type(exc).__name__}

    context_state = str(cdiag.get("state") or "CHECK").upper()
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Context state", context_state)
    d2.metric("Records verified", f"{int(cdiag.get('records_verified', 0) or 0)}/{int(cdiag.get('teams', teams) or teams)}")
    d3.metric("Advanced teams", int(cdiag.get("advanced_teams", 0) or 0))
    d4.metric("H2H samples", int(cdiag.get("h2h_samples", 0) or 0))
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
    mc_rows, mc_meta = prior._render_step7(day_str, probability_rows, probability_ready)
    simulation_ready = bool(mc_meta.get("simulation_ready", False))
    final_rows, grading_meta = _render_step8(day_str, mc_rows, simulation_ready)
    grading_ready = bool(grading_meta.get("grading_ready", False))

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
    st.session_state["wnba_game_total_v13_probability_rows"] = probability_rows.to_dict("records") if isinstance(probability_rows, pd.DataFrame) and not probability_rows.empty else []
    st.session_state["wnba_game_total_v13_probability_meta"] = dict(probability_meta)
    st.session_state["wnba_game_total_v13_probability_ready"] = probability_ready
    st.session_state["wnba_game_total_v14_mc_rows"] = mc_rows.to_dict("records") if isinstance(mc_rows, pd.DataFrame) and not mc_rows.empty else []
    st.session_state["wnba_game_total_v14_mc_ready"] = simulation_ready
    st.session_state["wnba_game_total_v15_final_rows"] = final_rows.to_dict("records") if isinstance(final_rows, pd.DataFrame) and not final_rows.empty else []
    st.session_state["wnba_game_total_v15_grading_meta"] = dict(grading_meta)
    st.session_state["wnba_game_total_v15_grading_ready"] = grading_ready
    st.session_state["wnba_game_total_v15_day"] = day_str

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
        {"Layer": "Verified slate", "State": "READY" if len(schedule) else "CHECK"},
        {"Layer": "Clock-safe pregame eligibility", "State": "READY" if len(pregame) else "NO ELIGIBLE GAMES"},
        {"Layer": "Total-scoring team context", "State": "READY" if context_state == "VERIFIED" else "CHECK"},
        {"Layer": "Current availability", "State": "READY" if availability_ready else ("N/A" if expected_coverage == 0 else "CHECK")},
        {"Layer": "Exact sportsbook game total", "State": "READY" if market_ready else ("N/A" if not len(pregame) else "CHECK")},
        {"Layer": "Independent projected game total", "State": "READY" if projection_ready else ("NEXT" if market_ready else "LOCKED")},
        {"Layer": "Over/Under probability / fair total", "State": "READY" if probability_ready else ("NEXT" if projection_ready else "LOCKED")},
        {"Layer": "5M Monte Carlo", "State": mc_state},
        {"Layer": "Final Game Total grading", "State": "READY" if grading_ready else ("NEXT" if simulation_ready else "OFF")},
        {"Layer": "Daily Picks connector", "State": "NEXT" if grading_ready else "OFF"},
    ])
    st.dataframe(locks, use_container_width=True, hide_index=True)

    qualified = int(grading_meta.get("qualified", 0) or 0)
    if grading_ready:
        st.info(
            f"V1.5 completes the independent Game Total production model through risk-adjusted final grading. "
            f"{qualified} game(s) are QUALIFIED right now; zero plays are forced. Daily Picks remains read-only/OFF until Step 9."
        )
    else:
        st.info(
            "V1.5 preserves Steps 1-7 and adds only risk-adjusted final grading. "
            "Daily Picks remains OFF until a complete Step-8 decision set is verified."
        )


__all__ = [
    "MODEL_VERSION", "render_wnba_game_total_hub", "_render_step8", "_final_grade",
    "_side_candidates", "MIN_WIN_PROB", "MIN_EDGE_PP", "MIN_EV", "MIN_WORST_CASE_PROB",
]
