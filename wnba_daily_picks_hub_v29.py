"""WNBA Daily Picks V29 — Step-8 Moneyline execution adapter.

Preserves the complete Daily Picks V21 seven-market production/verification surface
and the independently verified controller Steps 1-7. Step 8 wires exactly one new
execution adapter: current Moneyline V1.5 through its native V1.4 Step-7 actual
5,000,000-draw Monte Carlo boundary.

No Moneyline projection/probability/no-vig/Monte Carlo math is copied or changed.
The controller builds the same native Steps 1-6 inputs from the verified ET slate,
clock-safe pregame games, verified team context, exact-day availability, exact
same-book two-sided sportsbook Moneyline rows, the market-independent Step-5 win
distribution, and the native Step-6 no-vig/fair-odds board. It then calls the
existing V1.4 Monte Carlo engine.

Exactly 5,000,000 unique final-margin draws per eligible game are streamed in
20 x 250,000 batches and reused across every sportsbook row for that game. The
native Step-7 snapshot keys are populated exactly as on the Moneyline page. Step 8
final Moneyline grading is intentionally not controller-run yet; this adapter stops
at the independently verified 5M simulation boundary. Game Total remains unwired,
Daily Picks connector/ranking writes remain zero, and Run All 7 stays disabled.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

import wnba_daily_picks_hub_v281 as prior
import wnba_daily_picks_hub_v25 as controller_base
import wnba_daily_picks_hub_v21 as v21
import wnba_moneyline_hub_v15 as moneyline_v15

MODEL_VERSION = "WNBA DAILY PICKS V29 • MASTER CONTROLLER STEP 8 • MONEYLINE 5M ADAPTER"
_ET = ZoneInfo("America/New_York")

_PREFLIGHT_KEY = prior._PREFLIGHT_KEY
_PRA_RUN_KEY = prior._PRA_RUN_KEY
_POINTS_RUN_KEY = prior._POINTS_RUN_KEY
_REBOUNDS_RUN_KEY = prior._REBOUNDS_RUN_KEY
_ASSISTS_RUN_KEY = prior._ASSISTS_RUN_KEY
_SPREAD_RUN_KEY = prior._SPREAD_RUN_KEY
_MONEYLINE_RUN_KEY = "ks_run_all_7_step8_moneyline_v29"
_MARKETS = prior._MARKETS


def _day_str() -> str:
    return datetime.now(_ET).strftime("%Y-%m-%d")


def _build_native_step6(day_str: str):
    """Build current Moneyline Steps 1-6 using the source-owned analytical helpers."""
    foundation = moneyline_v15.foundation
    clock = moneyline_v15.clock
    spread_current = moneyline_v15.spread_current
    step4 = moneyline_v15.step4
    step5 = moneyline_v15.step5
    step6 = moneyline_v15.step6

    now_et = pd.Timestamp.now(tz=moneyline_v15.ET)
    schedule = foundation._schedule(day_str)
    if not isinstance(schedule, pd.DataFrame):
        schedule = pd.DataFrame()

    pregame = clock._pregame_schedule(schedule, now_et=now_et) if not schedule.empty else pd.DataFrame()
    if not isinstance(pregame, pd.DataFrame):
        pregame = pd.DataFrame()
    if pregame.empty:
        return pd.DataFrame(), {
            "ready": False,
            "reason": "No clock-safe pregame Moneyline games remain for the current ET slate.",
            "games": 0,
        }

    try:
        contexts, cdiag = foundation.context.slate_context(day_str)
    except Exception as exc:
        contexts, cdiag = {}, {"state": "CHECK", "reason": type(exc).__name__}
    contexts = contexts if isinstance(contexts, dict) else {}
    cdiag = cdiag if isinstance(cdiag, dict) else {}
    context_state = str(cdiag.get("state") or "CHECK").upper()

    try:
        av = spread_current._availability_snapshot_exact_day(day_str, pregame)
    except Exception as exc:
        av = pd.DataFrame()
        availability_reason = type(exc).__name__
    else:
        availability_reason = ""
    if not isinstance(av, pd.DataFrame):
        av = pd.DataFrame()

    covered = int(
        pd.to_numeric(av.get("covered_teams", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()
    ) if not av.empty else 0
    expected_coverage = int(2 * len(pregame))
    unverified = int(
        pd.to_numeric(av.get("unverified", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()
    ) if not av.empty else 0
    availability_ready = bool(expected_coverage > 0 and covered == expected_coverage and unverified == 0)
    foundation_ready = bool(len(pregame) and context_state == "VERIFIED" and availability_ready)

    if foundation_ready:
        ready_ml, _rejected_ml, market_meta = step4._moneyline_market_snapshot(day_str, pregame)
        market_meta = dict(market_meta or {})
        market_ready = bool(str(market_meta.get("state") or "CHECK").upper() == "READY")
    else:
        ready_ml = pd.DataFrame()
        market_meta = {"state": "LOCKED", "market_ready": False}
        market_ready = False

    if market_ready:
        win_board, win_meta = step5._independent_win_board(day_str, pregame, contexts)
        win_meta = dict(win_meta or {})
        win_ready = bool(win_meta.get("model_ready", False))
    else:
        win_board = pd.DataFrame()
        win_meta = {"state": "LOCKED", "model_ready": False}
        win_ready = False

    if win_ready:
        compare_board, compare_meta = step6._novig_fair_board(win_board, ready_ml)
        compare_meta = dict(compare_meta or {})
        comparison_ready = bool(compare_meta.get("comparison_ready", False))
    else:
        compare_board = pd.DataFrame()
        compare_meta = {"state": "LOCKED", "comparison_ready": False}
        comparison_ready = False

    if not isinstance(compare_board, pd.DataFrame):
        compare_board = pd.DataFrame()

    ready = bool(
        foundation_ready
        and market_ready
        and win_ready
        and comparison_ready
        and not compare_board.empty
    )

    reasons = []
    if context_state != "VERIFIED":
        reasons.append("team context not VERIFIED")
    if not availability_ready:
        reasons.append(
            f"availability {covered}/{expected_coverage} covered teams; {unverified} unverified"
            + (f" ({availability_reason})" if availability_reason else "")
        )
    if not market_ready:
        missing = market_meta.get("missing_games") or []
        reasons.append(
            "exact sportsbook Moneyline Step 4 not READY"
            + (": " + "; ".join(str(x) for x in missing) if missing else "")
        )
    if not win_ready:
        reasons.append("independent Moneyline win-probability Step 5 not READY")
    if not comparison_ready:
        reasons.append("same-book no-vig/fair-odds Step 6 not READY")
    if compare_board.empty:
        reasons.append("Step-6 Moneyline comparison board is empty")

    return compare_board, {
        "ready": ready,
        "reason": "; ".join(reasons),
        "games": int(len(pregame)),
        "context_state": context_state,
        "availability_ready": availability_ready,
        "market_ready": market_ready,
        "win_ready": win_ready,
        "comparison_ready": comparison_ready,
        "comparison_rows": int(len(compare_board)),
        "sportsbook_projection_inputs": int(compare_meta.get("sportsbook_projection_inputs", 0) or 0),
    }


def _run_moneyline_standard_5m():
    """Execute current Moneyline exactly through its native V1.4 Step-7 Monte Carlo."""
    day_str = _day_str()
    board, upstream = _build_native_step6(day_str)
    monte = moneyline_v15.prior.monte

    if not bool(upstream.get("ready")):
        return {
            "status": "BLOCKED",
            "day": day_str,
            "reason": str(upstream.get("reason") or "Native Moneyline Step 6 is not READY."),
            "games": int(upstream.get("games") or 0),
            "rows": 0,
            "converged": 0,
            "simulations": 0,
            "trials_per_game": int(monte.N_SIMS),
            "batches": int(monte.N_BATCHES),
            "batch_size": int(monte.BATCH_SIZE),
            "sportsbook_sim_inputs": 0,
        }

    progress = st.progress(0.0, text="Controller: running Moneyline native Step-7 5M…")
    status = st.empty()
    total_batches = max(1, int(upstream.get("games") or 0) * int(monte.N_BATCHES))

    def _progress(done, total):
        total = max(1, int(total or total_batches))
        done = max(0, int(done or 0))
        progress.progress(
            min(1.0, float(done) / total),
            text=f"Moneyline 5M • {done}/{total} batches",
        )
        status.caption(
            f"Completed {done * int(monte.BATCH_SIZE):,} streamed game-draw slots"
        )

    try:
        detail, meta = monte.run_monte_carlo(day_str, board, progress_callback=_progress)
    finally:
        progress.empty()
        status.empty()

    if not isinstance(detail, pd.DataFrame):
        detail = pd.DataFrame()
    meta = dict(meta or {})

    # Native V1.4 Step-7 persistence contract. This is source snapshot persistence,
    # not a Daily Picks connector write and not a cross-market ranking write.
    st.session_state["wnba_moneyline_v14_mc_detail"] = detail.copy()
    st.session_state["wnba_moneyline_v14_mc_meta"] = dict(meta)
    st.session_state["wnba_moneyline_v14_mc_day"] = str(day_str)

    games = int(meta.get("games", 0) or 0)
    covered_games = int(meta.get("covered_games", 0) or 0)
    rows = int(meta.get("rows", 0) or 0)
    converged_rows = int(meta.get("converged_rows", 0) or 0)
    per_game = int(meta.get("simulations_per_game", monte.N_SIMS) or 0)
    total_draws = int(meta.get("total_game_draws", covered_games * per_game) or 0)
    sportsbook_sim_inputs = int(meta.get("sportsbook_simulation_inputs", 0) or 0)

    complete = bool(
        meta.get("simulation_ready", False)
        and str(meta.get("state") or "CHECK").upper() == "READY"
        and games > 0
        and covered_games == games
        and rows > 0
        and converged_rows == rows
        and per_game == int(monte.N_SIMS)
        and total_draws == games * int(monte.N_SIMS)
        and sportsbook_sim_inputs == 0
    )

    return {
        "status": "5M COMPLETE" if complete else "CHECK",
        "day": day_str,
        "reason": "" if complete else "Native Moneyline Step-7 Monte Carlo did not satisfy its complete coverage/convergence contract.",
        "games": games,
        "covered_games": covered_games,
        "rows": rows,
        "converged": converged_rows,
        "simulations": total_draws,
        "trials_per_game": per_game,
        "batches": int(meta.get("batches", monte.N_BATCHES) or 0),
        "batch_size": int(meta.get("batch_size", monte.BATCH_SIZE) or 0),
        "sportsbook_sim_inputs": sportsbook_sim_inputs,
        "ready_rows": int(meta.get("ready_rows", 0) or 0),
        "monitor_rows": int(meta.get("monitor_rows", 0) or 0),
        "seed": meta.get("seed"),
        "fingerprint": str(meta.get("fingerprint") or ""),
    }


def _render_controller_step8():
    st.markdown("## 🚀 Seven-Market Master Controller — Step 8")
    st.caption(
        "Sixth execution adapter only: current Moneyline V1.5 through its native V1.4 Step-7 5M boundary. "
        "Controller Steps 1-7 are frozen/verified. Moneyline source projection/probability/no-vig/Monte Carlo math is unchanged. "
        "Game Total remains unwired."
    )

    records, all_pass, passed = controller_base._preflight_state()
    if not all_pass:
        if st.button("🔎 CHECK ALL 7 PREFLIGHTS", key="ks_step8_recheck_preflight_v29", use_container_width=True):
            st.session_state[_PREFLIGHT_KEY] = controller_base._run_preflight()
            st.rerun()
        st.warning(f"⚠️ STEP 8 LOCKED • Step-2 infrastructure preflight must be 7/7 first. Current: {passed}/7.")
    else:
        st.success("✅ STEP 2 FROZEN • 7/7 source routes + connector contracts passed. Moneyline execution adapter may be tested.")

    pra_run = st.session_state.get(_PRA_RUN_KEY)
    points_run = st.session_state.get(_POINTS_RUN_KEY)
    rebounds_run = st.session_state.get(_REBOUNDS_RUN_KEY)
    assists_run = st.session_state.get(_ASSISTS_RUN_KEY)
    spread_run = st.session_state.get(_SPREAD_RUN_KEY)
    moneyline_run = st.session_state.get(_MONEYLINE_RUN_KEY)

    pra_complete = str((pra_run or {}).get("status") or "") == "5M COMPLETE"
    points_complete = str((points_run or {}).get("status") or "") == "5M COMPLETE"
    rebounds_complete = str((rebounds_run or {}).get("status") or "") == "5M COMPLETE"
    assists_complete = str((assists_run or {}).get("status") or "") == "5M COMPLETE"
    spread_complete = str((spread_run or {}).get("status") or "") == "5M COMPLETE"
    moneyline_complete = str((moneyline_run or {}).get("status") or "") == "5M COMPLETE"

    runs = (pra_run, points_run, rebounds_run, assists_run, spread_run, moneyline_run)
    launched = sum(isinstance(x, dict) for x in runs)
    sims_total = sum(int((x or {}).get("simulations") or 0) for x in runs)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Controller state", "MONEYLINE ADAPTER VERIFIED" if moneyline_complete else ("MONEYLINE ADAPTER READY" if all_pass else "STEP 2 REQUIRED"))
    m2.metric("Execution adapters", "6/7")
    m3.metric("Models launched this session", launched)
    m4.metric("New simulations this session", f"{sims_total:,}")

    st.button(
        "🚀 RUN ALL 7 WNBA MARKETS",
        key="ks_daily_picks_run_all_7_disabled_v29",
        disabled=True,
        use_container_width=True,
        help="Master execution stays locked until all seven adapters are independently verified.",
    )

    if st.button(
        "💰 RUN MONEYLINE 5,000,000 THROUGH CONTROLLER",
        key="ks_step8_run_moneyline_5m_v29",
        disabled=not all_pass,
        use_container_width=True,
        help="Runs current Moneyline through native Step 7 only: 5M unique final-margin draws/game in 20 batches, reused across all exact sportsbook rows.",
    ):
        try:
            with st.spinner("Moneyline controller adapter is using the existing Steps 1-7 production chain…"):
                st.session_state[_MONEYLINE_RUN_KEY] = _run_moneyline_standard_5m()
        except Exception as exc:
            monte = moneyline_v15.prior.monte
            st.session_state[_MONEYLINE_RUN_KEY] = {
                "status": "ERROR",
                "day": _day_str(),
                "reason": f"{type(exc).__name__}: {exc}",
                "games": 0,
                "rows": 0,
                "converged": 0,
                "simulations": 0,
                "trials_per_game": int(monte.N_SIMS),
                "batches": int(monte.N_BATCHES),
                "batch_size": int(monte.BATCH_SIZE),
                "sportsbook_sim_inputs": 0,
            }
        st.rerun()

    moneyline_run = st.session_state.get(_MONEYLINE_RUN_KEY)
    if isinstance(moneyline_run, dict):
        token = str(moneyline_run.get("status") or "CHECK")
        if token == "5M COMPLETE":
            st.success(
                "✅ MONEYLINE CONTROLLER ADAPTER PASSED • native Moneyline Steps 1-7 completed through the controller. "
                "Each eligible game retained exactly 5M unique final-margin draws, 20-batch convergence, coherent reuse across books, and sportsbook simulation input remained ZERO."
            )
        elif token == "BLOCKED":
            st.warning("⚠️ MONEYLINE CONTROLLER BLOCKED • " + str(moneyline_run.get("reason") or "source readiness gate did not pass"))
        else:
            st.error("⛔ MONEYLINE CONTROLLER CHECK • " + str(moneyline_run.get("reason") or token))

        a, b, c, d = st.columns(4)
        a.metric("Moneyline day", str(moneyline_run.get("day") or "—"))
        b.metric("Games simulated", f"{int(moneyline_run.get('covered_games') or 0)}/{int(moneyline_run.get('games') or 0)}")
        c.metric("Unique game draws", f"{int(moneyline_run.get('simulations') or 0):,}")
        d.metric("Converged rows", f"{int(moneyline_run.get('converged') or 0)}/{int(moneyline_run.get('rows') or 0)}")

        e, f, g, h = st.columns(4)
        e.metric("Trials / game", f"{int(moneyline_run.get('trials_per_game') or 0):,}")
        f.metric("Batches / game", int(moneyline_run.get("batches") or 0))
        g.metric("Sportsbook sim inputs", int(moneyline_run.get("sportsbook_sim_inputs") or 0))
        h.metric("READY / MONITOR rows", f"{int(moneyline_run.get('ready_rows') or 0)} / {int(moneyline_run.get('monitor_rows') or 0)}")

        st.caption(
            "Step 8 stops at the native Moneyline Step-7 Monte Carlo boundary. Exact sportsbook prices are comparison/EV inputs only and do not alter the Step-5 projected margin, empirical sigma or simulated distribution. Native Step-8 final grading and Daily Picks connector/ranking execution are not performed by this adapter."
        )

    st.markdown("### 🧩 Controller Market Status")
    statuses = []
    for item in _MARKETS:
        market = item["market"]
        if market == "PRA":
            value = "✅ 5M COMPLETE" if pra_complete else "✅ ADAPTER VERIFIED • STEP 3"
        elif market == "POINTS":
            value = "✅ 5M COMPLETE" if points_complete else "✅ ADAPTER VERIFIED • STEP 4"
        elif market == "REBOUNDS":
            value = "✅ 5M COMPLETE" if rebounds_complete else "✅ ADAPTER VERIFIED • STEP 5"
        elif market == "ASSISTS":
            value = "✅ 5M COMPLETE" if assists_complete else "✅ ADAPTER VERIFIED • STEP 6"
        elif market == "SPREAD":
            value = "✅ 5M COMPLETE" if spread_complete else "✅ ADAPTER VERIFIED • STEP 7"
        elif market == "MONEYLINE":
            if moneyline_complete:
                value = "✅ 5M COMPLETE"
            elif moneyline_run:
                value = "⚠️ " + str(moneyline_run.get("status") or "CHECK")
            elif all_pass:
                value = "🟢 ADAPTER READY"
            else:
                value = "WAITING"
        else:
            value = "✅ PREFLIGHT PASS • ADAPTER NEXT" if all_pass else "WAITING"
        statuses.append((item, value))

    rows_ui = [st.columns(4), st.columns(3)]
    for idx, (item, value) in enumerate(statuses):
        row = rows_ui[0] if idx < 4 else rows_ui[1]
        col = row[idx] if idx < 4 else row[idx - 4]
        with col:
            st.markdown(f"**{item['icon']} {item['market']}**")
            st.metric("Controller status", value)

    if records:
        with st.expander("🔎 Frozen Step-2 preflight audit"):
            st.dataframe(pd.DataFrame(records), use_container_width=True, hide_index=True)

    st.caption(
        "Step 8 contract • adapters wired 6/7 • PRA + Points + Rebounds + Assists + Spread adapters frozen/verified • Moneyline source math changed 0 • "
        "Moneyline native Steps 1-7 only • exactly 5,000,000 unique draws/game • 20 batches/game • same game outcomes reused across books • "
        "sportsbook simulation inputs 0 • Moneyline Step 8 auto-run 0 • Game Total executed 0 • connector writes 0 • Daily Picks ranking changes 0"
    )
    st.markdown("---")


def render_wnba_daily_picks_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _render_controller_step8()
    return v21.render_wnba_daily_picks_hub(
        section_header=section_header,
        status_info=status_info,
        team_logo=team_logo,
        h=h,
    )


__all__ = ["MODEL_VERSION", "render_wnba_daily_picks_hub"]
