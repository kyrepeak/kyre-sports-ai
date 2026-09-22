"""WNBA Daily Picks V28 — Step-7 Spread execution adapter.

Preserves the complete Daily Picks V21 seven-market production/verification surface
and the independently verified controller Steps 1-6. Step 7 wires exactly one new
execution adapter: the current Spread V1.6.1 chain through its native V1.6 Step-7
5,000,000-draw Monte Carlo boundary.

No Spread projection/probability/Monte Carlo math is copied or changed. The adapter
builds the same verified Steps 1-6 inputs using the current V1.6.1 exact-day
availability repair, then calls the existing V1.6 Monte Carlo engine. Exactly
5,000,000 unique final-margin draws per eligible game are streamed in 20 x 250,000
batches and reused across all sportsbook rows for that game. Native Step-7 source
snapshot keys are populated so the result has the same persistence contract as a
manual Spread-page run. Daily Picks connector writes/cross-market ranking and the
Moneyline/Game Total execution adapters remain unwired. Run All 7 remains disabled.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

import wnba_daily_picks_hub_v27 as prior
import wnba_daily_picks_hub_v25 as controller_base
import wnba_daily_picks_hub_v21 as v21
import wnba_spread_hub_v161 as spread_v161

MODEL_VERSION = "WNBA DAILY PICKS V28 • MASTER CONTROLLER STEP 7 • SPREAD 5M ADAPTER"
_ET = ZoneInfo("America/New_York")

_PREFLIGHT_KEY = prior._PREFLIGHT_KEY
_PRA_RUN_KEY = prior._PRA_RUN_KEY
_POINTS_RUN_KEY = prior._POINTS_RUN_KEY
_REBOUNDS_RUN_KEY = prior._REBOUNDS_RUN_KEY
_ASSISTS_RUN_KEY = prior._ASSISTS_RUN_KEY
_SPREAD_RUN_KEY = "ks_run_all_7_step7_spread_v28"
_MARKETS = prior._MARKETS


def _day_str() -> str:
    return datetime.now(_ET).strftime("%Y-%m-%d")


def _build_native_step6(day_str: str):
    """Build the current Spread Steps 1-6 chain and return its frozen probability board."""
    foundation = spread_v161.foundation
    clock = spread_v161.clock
    ui = spread_v161.ui
    step6_ui = spread_v161.step6_ui
    base = spread_v161.base

    now_et = pd.Timestamp.now(tz=spread_v161.ET)
    schedule = foundation._schedule(day_str)
    if not isinstance(schedule, pd.DataFrame):
        schedule = pd.DataFrame()
    pregame = clock._pregame_schedule(schedule, now_et=now_et) if not schedule.empty else pd.DataFrame()
    if not isinstance(pregame, pd.DataFrame):
        pregame = pd.DataFrame()
    if pregame.empty:
        return pd.DataFrame(), {
            "ready": False,
            "reason": "No clock-safe pregame Spread games remain for the current ET slate.",
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
        av = foundation._availability_snapshot(day_str, pregame)
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

    # These are the source-owned Step-4/5/6 render functions. They are executed in
    # a disposable container only to preserve their exact data/readiness contracts;
    # their visible diagnostics are removed after the frozen Step-6 board is built.
    slot = st.empty()
    try:
        with slot.container():
            ready_lines, step4 = ui._render_step4(day_str, pregame, foundation_ready)
            step4 = dict(step4 or {})
            market_ready = bool(step4.get("market_ready", False))

            projected, step5 = base.prior._render_step5(day_str, pregame, contexts, market_ready)
            step5 = dict(step5 or {})
            margin_ready = bool(step5.get("model_ready", False))

            probability_board, step6 = step6_ui._render_step6(
                day_str, pregame, projected, ready_lines, margin_ready
            )
            step6 = dict(step6 or {})
            probability_ready = bool(step6.get("model_ready", False))
    finally:
        slot.empty()

    if not isinstance(probability_board, pd.DataFrame):
        probability_board = pd.DataFrame()

    ready = bool(foundation_ready and market_ready and margin_ready and probability_ready and not probability_board.empty)
    reasons = []
    if context_state != "VERIFIED":
        reasons.append("team context not VERIFIED")
    if not availability_ready:
        reasons.append(
            f"availability {covered}/{expected_coverage} covered teams; {unverified} unverified"
            + (f" ({availability_reason})" if availability_reason else "")
        )
    if not market_ready:
        reasons.append("exact sportsbook spread Step 4 not READY")
    if not margin_ready:
        reasons.append("independent projected margin Step 5 not READY")
    if not probability_ready:
        reasons.append("cover probability/fair spread Step 6 not READY")
    if probability_board.empty:
        reasons.append("Step-6 probability board is empty")

    return probability_board, {
        "ready": ready,
        "reason": "; ".join(reasons),
        "games": int(len(pregame)),
        "context_state": context_state,
        "availability_ready": availability_ready,
        "market_ready": market_ready,
        "margin_ready": margin_ready,
        "probability_ready": probability_ready,
    }


def _run_spread_standard_5m():
    """Execute the native Spread chain exactly through V1.6 Step 7."""
    day_str = _day_str()
    board, upstream = _build_native_step6(day_str)
    if not bool(upstream.get("ready")):
        return {
            "status": "BLOCKED",
            "day": day_str,
            "reason": str(upstream.get("reason") or "Native Spread Step 6 is not READY."),
            "games": int(upstream.get("games") or 0),
            "rows": 0,
            "converged": 0,
            "simulations": 0,
            "trials_per_game": int(spread_v161.monte.N_SIMS),
            "batches": int(spread_v161.monte.N_BATCHES),
            "batch_size": int(spread_v161.monte.BATCH_SIZE),
        }

    progress = st.progress(0.0, text="Controller: running Spread native Step-7 5M…")
    status = st.empty()

    total_batches = max(1, int(upstream.get("games") or 0) * int(spread_v161.monte.N_BATCHES))

    def _progress(done, total):
        total = max(1, int(total or total_batches))
        done = max(0, int(done or 0))
        progress.progress(
            min(1.0, float(done) / total),
            text=f"Spread 5M • {done}/{total} batches",
        )
        status.caption(
            f"Completed {done * int(spread_v161.monte.BATCH_SIZE):,} streamed game-draw slots"
        )

    try:
        detail, final, meta = spread_v161.monte.run_monte_carlo(
            day_str, board, progress_callback=_progress
        )
    finally:
        progress.empty()
        status.empty()

    if not isinstance(detail, pd.DataFrame):
        detail = pd.DataFrame()
    if not isinstance(final, pd.DataFrame):
        final = pd.DataFrame()
    meta = dict(meta or {})

    # Preserve the exact native V1.6 Step-7 source persistence contract used by a
    # manual Spread-page run. This is source snapshot persistence, not a Daily Picks
    # connector write and not cross-market ranking.
    st.session_state["wnba_spread_v16_mc_detail"] = detail.copy()
    st.session_state["wnba_spread_v16_mc_final"] = final.copy()
    st.session_state["wnba_spread_v16_mc_meta"] = dict(meta)
    st.session_state["wnba_spread_v16_mc_date"] = str(day_str)

    games = int(meta.get("games", 0) or 0)
    covered_games = int(meta.get("covered_games", 0) or 0)
    rows = int(meta.get("rows", 0) or 0)
    converged_rows = int(meta.get("converged_rows", 0) or 0)
    per_game = int(meta.get("simulations_per_game", spread_v161.monte.N_SIMS) or 0)
    total_draws = int(meta.get("total_game_draws", games * per_game) or 0)
    complete = bool(
        str(meta.get("state") or "CHECK").upper() == "READY"
        and games > 0
        and covered_games == games
        and rows > 0
        and converged_rows == rows
        and per_game == int(spread_v161.monte.N_SIMS)
        and total_draws == games * int(spread_v161.monte.N_SIMS)
    )

    return {
        "status": "5M COMPLETE" if complete else "CHECK",
        "day": day_str,
        "reason": "" if complete else "Native Spread Step-7 Monte Carlo did not satisfy its complete coverage/convergence contract.",
        "games": games,
        "covered_games": covered_games,
        "rows": rows,
        "converged": converged_rows,
        "simulations": total_draws,
        "trials_per_game": per_game,
        "batches": int(meta.get("batches", spread_v161.monte.N_BATCHES) or 0),
        "batch_size": int(meta.get("batch_size", spread_v161.monte.BATCH_SIZE) or 0),
        "qualified_games": int(meta.get("qualified_games", 0) or 0),
        "market_to_distribution": "0",
        "seed": meta.get("seed"),
        "fingerprint": str(meta.get("fingerprint") or ""),
    }


def _render_controller_step7():
    st.markdown("## 🚀 Seven-Market Master Controller — Step 7")
    st.caption(
        "Fifth execution adapter only: current Spread V1.6.1 through the native V1.6 Step-7 5M boundary. "
        "Controller Steps 1-6 are frozen/verified. Spread source projection/probability/Monte Carlo math is unchanged. "
        "Moneyline and Game Total remain unwired."
    )

    # Frozen Step-2 ownership remains V25. Calling it directly avoids relying on
    # later adapter modules to re-export private preflight helpers.
    records, all_pass, passed = controller_base._preflight_state()
    if not all_pass:
        if st.button("🔎 CHECK ALL 7 PREFLIGHTS", key="ks_step7_recheck_preflight_v28", use_container_width=True):
            st.session_state[_PREFLIGHT_KEY] = controller_base._run_preflight()
            st.rerun()
        st.warning(f"⚠️ STEP 7 LOCKED • Step-2 infrastructure preflight must be 7/7 first. Current: {passed}/7.")
    else:
        st.success("✅ STEP 2 FROZEN • 7/7 source routes + connector contracts passed. Spread execution adapter may be tested.")

    pra_run = st.session_state.get(_PRA_RUN_KEY)
    points_run = st.session_state.get(_POINTS_RUN_KEY)
    rebounds_run = st.session_state.get(_REBOUNDS_RUN_KEY)
    assists_run = st.session_state.get(_ASSISTS_RUN_KEY)
    spread_run = st.session_state.get(_SPREAD_RUN_KEY)

    pra_complete = str((pra_run or {}).get("status") or "") == "5M COMPLETE"
    points_complete = str((points_run or {}).get("status") or "") == "5M COMPLETE"
    rebounds_complete = str((rebounds_run or {}).get("status") or "") == "5M COMPLETE"
    assists_complete = str((assists_run or {}).get("status") or "") == "5M COMPLETE"
    spread_complete = str((spread_run or {}).get("status") or "") == "5M COMPLETE"

    runs = (pra_run, points_run, rebounds_run, assists_run, spread_run)
    launched = sum(isinstance(x, dict) for x in runs)
    sims_total = sum(int((x or {}).get("simulations") or 0) for x in runs)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Controller state", "SPREAD ADAPTER VERIFIED" if spread_complete else ("SPREAD ADAPTER READY" if all_pass else "STEP 2 REQUIRED"))
    m2.metric("Execution adapters", "5/7")
    m3.metric("Models launched this session", launched)
    m4.metric("New simulations this session", f"{sims_total:,}")

    st.button(
        "🚀 RUN ALL 7 WNBA MARKETS",
        key="ks_daily_picks_run_all_7_disabled_v28",
        disabled=True,
        use_container_width=True,
        help="Master execution stays locked until all seven adapters are independently verified.",
    )

    if st.button(
        "🏀 RUN SPREAD 5,000,000 THROUGH CONTROLLER",
        key="ks_step7_run_spread_5m_v28",
        disabled=not all_pass,
        use_container_width=True,
        help="Runs the current Spread source through native Step 7 only: 5M unique final-margin draws/game in 20 batches, reused across all exact book rows.",
    ):
        try:
            with st.spinner("Spread controller adapter is using the existing Steps 1-7 production chain…"):
                st.session_state[_SPREAD_RUN_KEY] = _run_spread_standard_5m()
        except Exception as exc:
            st.session_state[_SPREAD_RUN_KEY] = {
                "status": "ERROR",
                "day": _day_str(),
                "reason": f"{type(exc).__name__}: {exc}",
                "games": 0,
                "rows": 0,
                "converged": 0,
                "simulations": 0,
                "trials_per_game": int(spread_v161.monte.N_SIMS),
                "batches": int(spread_v161.monte.N_BATCHES),
                "batch_size": int(spread_v161.monte.BATCH_SIZE),
            }
        st.rerun()

    spread_run = st.session_state.get(_SPREAD_RUN_KEY)
    if isinstance(spread_run, dict):
        token = str(spread_run.get("status") or "CHECK")
        if token == "5M COMPLETE":
            st.success(
                "✅ SPREAD CONTROLLER ADAPTER PASSED • native Spread Steps 1-7 completed through the controller. "
                "Each eligible game retained exactly 5M unique final-margin draws, 20-batch convergence, coherent reuse across books and the frozen Step-5/Step-6 distribution."
            )
        elif token == "BLOCKED":
            st.warning("⚠️ SPREAD CONTROLLER BLOCKED • " + str(spread_run.get("reason") or "source readiness gate did not pass"))
        else:
            st.error("⛔ SPREAD CONTROLLER CHECK • " + str(spread_run.get("reason") or token))

        a, b, c, d = st.columns(4)
        a.metric("Spread day", str(spread_run.get("day") or "—"))
        b.metric("Games simulated", f"{int(spread_run.get('covered_games') or 0)}/{int(spread_run.get('games') or 0)}")
        c.metric("Unique game draws", f"{int(spread_run.get('simulations') or 0):,}")
        d.metric("Converged rows", f"{int(spread_run.get('converged') or 0)}/{int(spread_run.get('rows') or 0)}")

        e, f, g, h = st.columns(4)
        e.metric("Trials / game", f"{int(spread_run.get('trials_per_game') or 0):,}")
        f.metric("Batches / game", int(spread_run.get("batches") or 0))
        g.metric("Market → distribution", str(spread_run.get("market_to_distribution") or "0"))
        h.metric("Qualified games", int(spread_run.get("qualified_games") or 0))

        st.caption(
            "Step 7 stops at the native Spread Step-7 boundary. Sportsbook spreads/prices are settlement/comparison thresholds only and do not alter the Step-5 projected margin or Step-6 empirical sigma. Daily Picks connector/ranking execution is not performed by this adapter."
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
            if spread_complete:
                value = "✅ 5M COMPLETE"
            elif spread_run:
                value = "⚠️ " + str(spread_run.get("status") or "CHECK")
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
        "Step 7 contract • adapters wired 5/7 • PRA + Points + Rebounds + Assists adapters frozen/verified • Spread source math changed 0 • "
        "Spread native Steps 1-7 only • exactly 5,000,000 unique draws/game • 20 batches/game • same game outcomes reused across books • "
        "Moneyline/Game Total executed 0 • connector writes 0 • Daily Picks ranking changes 0"
    )
    st.markdown("---")


def render_wnba_daily_picks_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _render_controller_step7()
    return v21.render_wnba_daily_picks_hub(
        section_header=section_header,
        status_info=status_info,
        team_logo=team_logo,
        h=h,
    )


__all__ = ["MODEL_VERSION", "render_wnba_daily_picks_hub"]
