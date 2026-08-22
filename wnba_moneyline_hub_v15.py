"""WNBA Moneyline V1.5 — Step 8 risk-adjusted final grading.

Preserves Moneyline V1.4 Steps 1-7 exactly and adds Step 8 only.

Step 8 consumes only the current, converged 5,000,000-draw Step-7 rows. It does
not rerun or alter the Step-5 distribution or Step-7 simulations. For each game
it evaluates both teams at every exact sportsbook price, carries the upstream
READY/MONITOR state forward, applies transparent production thresholds, checks
the existing ±5% projected-margin sensitivity, and publishes at most one final
Moneyline candidate per game.

No play is forced. A QUALIFIED candidate requires:
- converged/current Step-7 simulation state = READY;
- Monte Carlo win probability >= 55%;
- model-vs-same-book no-vig edge >= +3.0 percentage points;
- positive expected value at the exact posted price;
- worst-case probability across the existing ±5% Step-7 mean sensitivity > 50%.

A row that clears the numerical thresholds but carries an upstream MONITOR flag
remains MONITOR. Rows that miss the core thresholds are NO PLAY. Invalid or
non-converged rows are BLOCKED. Daily Picks remains OFF until the next isolated
read-only connector layer.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

import wnba_moneyline_hub_v14 as prior

MODEL_VERSION = "WNBA MONEYLINE V1.5 • RISK-ADJUSTED FINAL GRADING"
ET = prior.ET
foundation = prior.foundation
clock = prior.clock
spread_current = prior.spread_current
base = prior.base
step4 = prior.step4
step5 = prior.step5
step6 = prior.step6

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


def _side_candidates(mc_detail: pd.DataFrame) -> pd.DataFrame:
    """Expand each exact-book Step-7 game row into away/home candidate rows."""
    if mc_detail is None or mc_detail.empty:
        return pd.DataFrame()

    rows = []
    for _, src in mc_detail.iterrows():
        low_home = _num(src.get("sensitivity_low_home_prob"), np.nan)
        high_home = _num(src.get("sensitivity_high_home_prob"), np.nan)
        base_home = _num(src.get("mc_home_win_prob"), np.nan)
        base_away = _num(src.get("mc_away_win_prob"), np.nan)

        for side in ("AWAY", "HOME"):
            is_home = side == "HOME"
            team = str(src.get("home_team") if is_home else src.get("away_team") or "")
            price = _num(src.get("home_price") if is_home else src.get("away_price"), np.nan)
            prob = _num(src.get("mc_home_win_prob") if is_home else src.get("mc_away_win_prob"), np.nan)
            market = _num(src.get("home_market_novig") if is_home else src.get("away_market_novig"), np.nan)
            edge = _num(src.get("mc_home_edge_pp") if is_home else src.get("mc_away_edge_pp"), np.nan)
            ev = _num(src.get("mc_home_ev") if is_home else src.get("mc_away_ev"), np.nan)
            fair = _num(src.get("mc_home_fair_odds") if is_home else src.get("mc_away_fair_odds"), np.nan)

            if is_home:
                sens_probs = [x for x in (base_home, low_home, high_home) if np.isfinite(x)]
            else:
                sens_probs = [x for x in (
                    base_away,
                    1.0 - low_home if np.isfinite(low_home) else np.nan,
                    1.0 - high_home if np.isfinite(high_home) else np.nan,
                ) if np.isfinite(x)]

            worst_prob = min(sens_probs) if sens_probs else np.nan
            best_prob = max(sens_probs) if sens_probs else np.nan
            drop_pp = 100.0 * (prob - worst_prob) if np.isfinite(prob) and np.isfinite(worst_prob) else np.nan
            span_pp = 100.0 * (best_prob - worst_prob) if np.isfinite(best_prob) and np.isfinite(worst_prob) else np.nan

            upstream = str(src.get("mc_state") or "CHECK").upper()
            converged = bool(src.get("converged", False))
            valid = bool(
                converged
                and upstream not in {"CHECK", "BLOCKED"}
                and np.isfinite(prob)
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
                reason = "upstream Step-5/7 uncertainty flag carried forward"
            elif not sensitivity_pass:
                grade = "MONITOR"
                reason = "worst-case ±5% sensitivity falls to 50% or lower"
            else:
                grade = "QUALIFIED"
                reason = "all final Moneyline guards passed"

            rows.append({
                "game_id": str(src.get("game_id") or ""),
                "away_team": str(src.get("away_team") or ""),
                "home_team": str(src.get("home_team") or ""),
                "first_tip_et": str(src.get("first_tip_et") or "—"),
                "book": str(src.get("book") or ""),
                "side": side,
                "team": team,
                "posted_price": price,
                "mc_win_prob": prob,
                "mc_fair_odds": fair,
                "market_novig": market,
                "edge_pp": edge,
                "ev": ev,
                "worst_case_prob": worst_prob,
                "sensitivity_drop_pp": drop_pp,
                "sensitivity_span_pp": span_pp,
                "upstream_state": upstream,
                "converged": converged,
                "simulation_count": int(_num(src.get("simulation_count"), 0) or 0),
                "seed": int(_num(src.get("seed"), 0) or 0),
                "snapshot_fingerprint": str(src.get("snapshot_fingerprint") or ""),
                "grade": grade,
                "reason": reason,
                "sportsbook_simulation_inputs": 0,
            })

    return pd.DataFrame(rows)


def _final_grade(mc_detail: pd.DataFrame, simulation_ready: bool):
    empty_meta = {
        "state": "LOCKED",
        "games": 0,
        "graded_games": 0,
        "qualified": 0,
        "monitor": 0,
        "no_play": 0,
        "blocked": 0,
        "grading_ready": False,
        "new_simulations": 0,
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

    # At most one candidate per game. A safer status always outranks a weaker
    # status; within the same status, edge then EV then probability decide the
    # exact side/book. This prevents a MONITOR row from displacing a QUALIFIED one.
    ordered = sides.sort_values(
        ["game_id", "_priority", "_edge_sort", "_ev_sort", "_worst_sort", "_prob_sort", "book"],
        ascending=[True, True, False, False, False, False, True],
        kind="stable",
    )
    final = ordered.drop_duplicates(subset=["game_id"], keep="first").copy()
    final = final.drop(columns=["_priority", "_edge_sort", "_ev_sort", "_prob_sort", "_worst_sort"], errors="ignore")
    sides = sides.drop(columns=["_priority", "_edge_sort", "_ev_sort", "_prob_sort", "_worst_sort"], errors="ignore")

    expected_games = int(mc_detail["game_id"].astype(str).nunique())
    graded_games = int(final["game_id"].astype(str).nunique())
    counts = final["grade"].astype(str).value_counts().to_dict()
    grading_ready = bool(expected_games > 0 and graded_games == expected_games and not final["grade"].astype(str).eq("BLOCKED").any())
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
    st.markdown("### 🏆 Step 8 — Risk-Adjusted Final Moneyline Grading")
    st.caption(
        "No forced plays • one best exact side/book per game • 5M result + same-book no-vig edge + exact-price EV + "
        "upstream uncertainty + existing ±5% sensitivity. Step 8 runs ZERO new simulations and cannot change the model probability."
    )

    if not simulation_ready or mc_detail is None or mc_detail.empty:
        st.warning("🔒 STEP 8 LOCKED • a current converged Step-7 5M result is required before final Moneyline grading.")
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
            "✅ STEP 8 PASSED • every simulated game received one risk-adjusted final Moneyline decision. "
            "No play is forced; upstream MONITOR states remain MONITOR."
        )
    else:
        st.warning("⚠️ STEP 8 CHECK • at least one game could not receive a safe final decision. Daily Picks remains locked.")

    if not final.empty:
        show = final.copy()
        show["Game"] = show["away_team"].astype(str) + " @ " + show["home_team"].astype(str)
        show["Candidate"] = show.apply(lambda r: f"{r.get('team')} ML ({_fmt_price(r.get('posted_price'))})", axis=1)
        show["MC win"] = show["mc_win_prob"].map(_fmt_pct)
        show["Worst ±5%"] = show["worst_case_prob"].map(_fmt_pct)
        show["MC fair"] = show["mc_fair_odds"].map(_fmt_price)
        show["No-vig"] = show["market_novig"].map(_fmt_pct)
        show["Edge"] = show["edge_pp"].map(_fmt_pp)
        show["EV"] = show["ev"].map(_fmt_ev)
        show["Sensitivity drop"] = show["sensitivity_drop_pp"].map(lambda x: "—" if not np.isfinite(_num(x)) else f"{float(x):.1f} pp")
        st.dataframe(
            show[[
                "Game", "book", "Candidate", "MC win", "Worst ±5%", "MC fair", "No-vig",
                "Edge", "EV", "Sensitivity drop", "upstream_state", "grade", "reason",
            ]].rename(columns={"book": "Exact book", "upstream_state": "Upstream", "grade": "Grade", "reason": "Guard reason"}),
            use_container_width=True,
            hide_index=True,
        )

    with st.expander("🧪 Step 8 qualification audit — every exact side/book", expanded=False):
        if sides.empty:
            st.info("No Step-8 side rows are available.")
        else:
            audit = sides.copy()
            audit["Game"] = audit["away_team"].astype(str) + " @ " + audit["home_team"].astype(str)
            audit["Candidate"] = audit.apply(lambda r: f"{r.get('team')} ML ({_fmt_price(r.get('posted_price'))})", axis=1)
            audit["MC win"] = audit["mc_win_prob"].map(_fmt_pct)
            audit["Worst ±5%"] = audit["worst_case_prob"].map(_fmt_pct)
            audit["Edge"] = audit["edge_pp"].map(_fmt_pp)
            audit["EV"] = audit["ev"].map(_fmt_ev)
            audit["Sims"] = audit["simulation_count"].map(lambda x: f"{int(x):,}")
            st.dataframe(
                audit[["Game", "book", "Candidate", "MC win", "Worst ±5%", "Edge", "EV", "Sims", "upstream_state", "grade", "reason"]].rename(
                    columns={"book": "Book", "upstream_state": "Upstream", "grade": "Grade", "reason": "Reason"}
                ),
                use_container_width=True,
                hide_index=True,
            )
            st.caption(
                "QUALIFIED = converged READY simulation + MC win ≥55% + no-vig edge ≥+3.0 pp + positive exact-price EV + worst-case ±5% probability >50%. "
                "A numerical pass with an upstream uncertainty flag remains MONITOR."
            )

    st.session_state["wnba_moneyline_v15_day"] = str(day_str)
    st.session_state["wnba_moneyline_v15_grading_ready"] = grading_ready
    st.session_state["wnba_moneyline_v15_final_card"] = final.to_dict("records") if not final.empty else []
    st.session_state["wnba_moneyline_v15_qualified_card"] = (
        final.loc[final["grade"].astype(str).eq("QUALIFIED")].to_dict("records") if not final.empty else []
    )
    st.session_state["wnba_moneyline_v15_grade_meta"] = dict(meta)

    return final, meta


def render_wnba_moneyline_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.markdown("## 💰 WNBA Moneyline Command Center")
    st.caption(
        "V1.5 • verified slate → clock-safe pregame guard → team context → exact-day availability → exact sportsbook Moneyline → "
        "independent win probability → same-book no-vig/fair odds → actual 5M Monte Carlo → risk-adjusted final grading. "
        "Daily Picks connector remains OFF."
    )

    default_day = st.session_state.get("wnba_moneyline_v1_date") or pd.Timestamp.now(tz=ET).date()
    selected = st.date_input(
        "Moneyline slate date",
        value=pd.to_datetime(default_day).date(),
        key="wnba_moneyline_v1_date_picker",
    )
    st.session_state["wnba_moneyline_v1_date"] = selected
    day_str = pd.to_datetime(selected).strftime("%Y-%m-%d")
    now_et = pd.Timestamp.now(tz=ET)

    with st.spinner("📅 Verifying WNBA Moneyline slate + clock-safe pregame eligibility…"):
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
        with st.expander("🚫 Games excluded from Moneyline pregame production", expanded=False):
            cols = [c for c in [
                "away_team", "home_team", "first_tip_et", "scheduled_tip_guard_et",
                "status", "status_text", "exclusion_reason",
            ] if c in excluded.columns]
            st.dataframe(excluded[cols] if cols else excluded, use_container_width=True, hide_index=True)

    with st.spinner("📊 Building verified team form + matchup context…"):
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
        st.success("✅ STEP 2 PASSED • team records/recent form are verified; advanced pace/ratings are used only where real samples exist.")
    else:
        st.warning("⚠️ STEP 2 CHECK • some team context is incomplete. Missing advanced fields remain neutral/missing; nothing is invented.")

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
        st.warning("⚠️ STEP 3 CHECK • availability is not fully verified for every pregame-eligible game. Future Moneyline production remains locked.")

    st.markdown("### 🧩 Pregame-Eligible Moneyline Foundation")
    if pregame.empty:
        st.info("No pregame-eligible games remain to display.")
    else:
        for _, game in pregame.iterrows():
            base._render_game_context(game, contexts, av_map)

    foundation_ready = bool(len(pregame) and context_state == "VERIFIED" and availability_ready)
    ready_ml, market_meta = step4._render_step4(day_str, pregame, foundation_ready)
    market_ready = bool(market_meta.get("market_ready"))

    win_board, step5_meta = step5._render_step5(day_str, pregame, contexts, market_ready)
    win_ready = bool(step5_meta.get("model_ready", False))

    compare_board, step6_meta = step6._render_step6(win_board, ready_ml, win_ready)
    comparison_ready = bool(step6_meta.get("comparison_ready", False))

    mc_detail, step7_meta = prior._render_step7(day_str, compare_board, comparison_ready)
    simulation_ready = bool(step7_meta.get("simulation_ready", False))

    final_card, step8_meta = _render_step8(day_str, mc_detail, simulation_ready)
    grading_ready = bool(step8_meta.get("grading_ready", False))

    st.session_state["wnba_moneyline_v1_day"] = day_str
    st.session_state["wnba_moneyline_v1_foundation_ready"] = foundation_ready
    st.session_state["wnba_moneyline_v1_schedule"] = schedule.to_dict("records")
    st.session_state["wnba_moneyline_v1_pregame"] = pregame.to_dict("records")
    st.session_state["wnba_moneyline_v1_availability"] = av.to_dict("records") if not av.empty else []
    st.session_state["wnba_moneyline_v11_market_ready"] = market_ready
    st.session_state["wnba_moneyline_v11_market_rows"] = ready_ml.to_dict("records") if not ready_ml.empty else []
    st.session_state["wnba_moneyline_v12_model_ready"] = win_ready
    st.session_state["wnba_moneyline_v13_comparison_ready"] = comparison_ready
    st.session_state["wnba_moneyline_v13_comparison_rows"] = compare_board.to_dict("records") if not compare_board.empty else []
    st.session_state["wnba_moneyline_v14_simulation_ready"] = simulation_ready
    st.session_state["wnba_moneyline_v14_mc_rows"] = mc_detail.to_dict("records") if not mc_detail.empty else []

    st.markdown("### 🔒 Moneyline Production Locks")
    locks = pd.DataFrame([
        {"Layer": "Verified slate", "State": "READY" if len(schedule) else "CHECK"},
        {"Layer": "Clock-safe pregame eligibility", "State": "READY" if len(pregame) else "NO ELIGIBLE GAMES"},
        {"Layer": "Team context", "State": "READY" if context_state == "VERIFIED" else "CHECK"},
        {"Layer": "Current availability", "State": "READY" if availability_ready else ("N/A" if not len(pregame) else "CHECK")},
        {"Layer": "Exact sportsbook moneyline", "State": "READY" if market_ready else ("CHECK" if foundation_ready else "LOCKED")},
        {"Layer": "Independent win probability", "State": "READY" if win_ready else ("CHECK" if market_ready else "LOCKED")},
        {"Layer": "No-vig / fair odds", "State": "READY" if comparison_ready else ("CHECK" if win_ready else "LOCKED")},
        {"Layer": "5M Monte Carlo", "State": "READY" if simulation_ready else ("RUN 5M" if comparison_ready else "LOCKED")},
        {"Layer": "Final Moneyline grading", "State": "READY" if grading_ready else ("CHECK" if simulation_ready else "LOCKED")},
        {"Layer": "Daily Picks connector", "State": "NEXT" if grading_ready else "OFF"},
    ])
    st.dataframe(locks, use_container_width=True, hide_index=True)

    qualified = int(step8_meta.get("qualified", 0) or 0)
    if grading_ready:
        st.info(
            f"V1.5 completes the independent Moneyline production model through risk-adjusted final grading. "
            f"{qualified} game(s) are QUALIFIED right now; zero plays are forced. Daily Picks remains read-only/OFF until Step 9."
        )
    else:
        st.info("V1.5 final grading is waiting on the complete current Step-7 simulation chain. Daily Picks remains OFF.")


__all__ = [
    "MODEL_VERSION",
    "MIN_WIN_PROB",
    "MIN_EDGE_PP",
    "MIN_EV",
    "MIN_WORST_CASE_PROB",
    "_side_candidates",
    "_final_grade",
    "_render_step8",
    "render_wnba_moneyline_hub",
]
