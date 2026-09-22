"""WNBA Daily Picks V30 — Step-9 Game Total execution adapter.

Preserves the complete Daily Picks V21 seven-market production/verification surface
and independently verified controller Steps 1-8. Step 9 wires exactly one final
execution adapter: current Game Total V1.5 through its native V1.4 Step-7 actual
5,000,000-draw Monte Carlo boundary.

No Game Total projection/probability/no-vig/Monte Carlo math is copied or changed.
The controller builds the native Steps 1-6 inputs through source-owned helpers:
verified ET slate, clock-safe pregame games, verified team context, exact-day
availability, exact same-book two-sided sportsbook totals, market-independent
projected total, and the native empirical-sigma O/U probability board. It then
calls the existing V1.4 Monte Carlo engine.

Exactly 5,000,000 unique integer-valued full-game total draws per eligible game are
streamed in 20 x 250,000 batches and reused across all sportsbook total rows for
that game. Sportsbook lines/prices remain settlement/comparison thresholds only.
Native Step-7 persistence is populated exactly as on the Game Total page. Native
Step-8 final grading and Daily Picks connector/ranking writes are intentionally not
controller-run here. Run All 7 remains disabled until this seventh adapter is
independently verified.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

import wnba_daily_picks_hub_v29 as prior
import wnba_daily_picks_hub_v25 as controller_base
import wnba_daily_picks_hub_v21 as v21
import wnba_game_total_hub_v15 as game_total_v15

MODEL_VERSION = "WNBA DAILY PICKS V30 • MASTER CONTROLLER STEP 9 • GAME TOTAL 5M ADAPTER"
_ET = ZoneInfo("America/New_York")

_PREFLIGHT_KEY = prior._PREFLIGHT_KEY
_PRA_RUN_KEY = prior._PRA_RUN_KEY
_POINTS_RUN_KEY = prior._POINTS_RUN_KEY
_REBOUNDS_RUN_KEY = prior._REBOUNDS_RUN_KEY
_ASSISTS_RUN_KEY = prior._ASSISTS_RUN_KEY
_SPREAD_RUN_KEY = prior._SPREAD_RUN_KEY
_MONEYLINE_RUN_KEY = prior._MONEYLINE_RUN_KEY
_GAME_TOTAL_RUN_KEY = "ks_run_all_7_step9_game_total_v30"
_MARKETS = prior._MARKETS


def _day_str() -> str:
    return datetime.now(_ET).strftime("%Y-%m-%d")


def _build_native_step6(day_str: str):
    """Build current Game Total Steps 1-6 using only source-owned helpers."""
    foundation = game_total_v15.foundation
    clock = game_total_v15.clock
    spread_current = game_total_v15.spread_current
    step4 = game_total_v15.step4
    step5 = game_total_v15.step5
    step6 = game_total_v15.step6

    now_et = pd.Timestamp.now(tz=game_total_v15.ET)
    schedule = foundation._schedule(day_str)
    if not isinstance(schedule, pd.DataFrame):
        schedule = pd.DataFrame()
    pregame = clock._pregame_schedule(schedule, now_et=now_et) if not schedule.empty else pd.DataFrame()
    if not isinstance(pregame, pd.DataFrame):
        pregame = pd.DataFrame()
    if pregame.empty:
        return pd.DataFrame(), {
            "ready": False,
            "reason": "No clock-safe pregame Game Total games remain for the current ET slate.",
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
        market_rows, _rejected, market_meta = step4._total_market_snapshot(day_str, pregame)
        market_meta = dict(market_meta or {})
        market_ready = bool(str(market_meta.get("state") or "CHECK").upper() == "READY")
    else:
        market_rows = pd.DataFrame()
        market_meta = {"state": "LOCKED"}
        market_ready = False

    if market_ready:
        projection_rows, projection_meta = step5._projected_total_board(day_str, pregame, contexts)
        projection_meta = dict(projection_meta or {})
        projection_ready = bool(projection_meta.get("model_ready", False))
    else:
        projection_rows = pd.DataFrame()
        projection_meta = {"state": "LOCKED", "model_ready": False}
        projection_ready = False

    if projection_ready:
        probability_rows, probability_meta = step6.total_probability.probability_board(
            day_str, pregame, projection_rows, market_rows
        )
        probability_meta = dict(probability_meta or {})
        probability_ready = bool(probability_meta.get("model_ready", False))
    else:
        probability_rows = pd.DataFrame()
        probability_meta = {"state": "LOCKED", "model_ready": False}
        probability_ready = False

    if not isinstance(probability_rows, pd.DataFrame):
        probability_rows = pd.DataFrame()

    ready = bool(
        foundation_ready
        and market_ready
        and projection_ready
        and probability_ready
        and not probability_rows.empty
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
            "exact sportsbook Game Total Step 4 not READY"
            + (": " + "; ".join(str(x) for x in missing) if missing else "")
        )
    if not projection_ready:
        reasons.append("independent projected Game Total Step 5 not READY")
    if not probability_ready:
        reasons.append("Game Total O/U probability/fair-total Step 6 not READY")
    if probability_rows.empty:
        reasons.append("Step-6 Game Total probability board is empty")

    return probability_rows, {
        "ready": ready,
        "reason": "; ".join(reasons),
        "games": int(len(pregame)),
        "context_state": context_state,
        "availability_ready": availability_ready,
        "market_ready": market_ready,
        "projection_ready": projection_ready,
        "probability_ready": probability_ready,
        "probability_rows": int(len(probability_rows)),
        "sportsbook_projection_inputs": int(probability_meta.get("sportsbook_projection_inputs", 0) or 0),
    }


def _run_game_total_standard_5m():
    """Execute current Game Total exactly through its native V1.4 Step-7 Monte Carlo."""
    day_str = _day_str()
    board, upstream = _build_native_step6(day_str)
    monte = game_total_v15.monte

    if not bool(upstream.get("ready")):
        return {
            "status": "BLOCKED",
            "day": day_str,
            "reason": str(upstream.get("reason") or "Native Game Total Step 6 is not READY."),
            "games": int(upstream.get("games") or 0),
            "covered_games": 0,
            "rows": 0,
            "converged": 0,
            "simulations": 0,
            "trials_per_game": int(monte.SIMULATIONS_PER_GAME),
            "batches": int(monte.BATCHES),
            "batch_size": int(monte.BATCH_SIZE),
            "sportsbook_sim_inputs": 0,
        }

    progress = st.progress(0.0, text="Controller: running Game Total native Step-7 5M…")
    status = st.empty()
    total_batches = max(1, int(upstream.get("games") or 0) * int(monte.BATCHES))

    def _progress(done, total):
        total = max(1, int(total or total_batches))
        done = max(0, int(done or 0))
        progress.progress(
            min(1.0, float(done) / total),
            text=f"Game Total 5M • {done}/{total} batches",
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

    # Preserve the native V1.4 Step-7 persistence contract used by a manual
    # Game Total page run. This is source snapshot persistence only.
    st.session_state["wnba_game_total_v14_mc_records"] = (
        detail.to_dict("records") if not detail.empty else []
    )
    st.session_state["wnba_game_total_v14_mc_meta"] = dict(meta)
    st.session_state["wnba_game_total_v14_mc_day"] = str(day_str)

    games = int(meta.get("games", 0) or 0)
    covered_games = int(meta.get("covered_games", 0) or 0)
    rows = int(meta.get("rows", 0) or 0)
    converged_rows = int(meta.get("converged_rows", 0) or 0)
    per_game = int(meta.get("simulations_per_game", monte.SIMULATIONS_PER_GAME) or 0)
    total_draws = int(meta.get("total_game_draws", games * per_game) or 0)
    sportsbook_sim_inputs = int(meta.get("sportsbook_simulation_inputs", 0) or 0)

    states = detail.get("mc_state", pd.Series(dtype=object)).astype(str).str.upper() if not detail.empty else pd.Series(dtype=object)
    ready_rows = int(states.eq("READY").sum()) if not states.empty else 0
    monitor_rows = int(states.eq("MONITOR").sum()) if not states.empty else 0

    complete = bool(
        meta.get("simulation_ready", False)
        and str(meta.get("state") or "CHECK").upper() == "READY"
        and games > 0
        and covered_games == games
        and rows > 0
        and converged_rows == rows
        and per_game == int(monte.SIMULATIONS_PER_GAME)
        and total_draws == games * int(monte.SIMULATIONS_PER_GAME)
        and sportsbook_sim_inputs == 0
    )

    return {
        "status": "5M COMPLETE" if complete else "CHECK",
        "day": day_str,
        "reason": "" if complete else "Native Game Total Step-7 Monte Carlo did not satisfy its complete coverage/convergence contract.",
        "games": games,
        "covered_games": covered_games,
        "rows": rows,
        "converged": converged_rows,
        "simulations": total_draws,
        "trials_per_game": per_game,
        "batches": int(meta.get("batches", monte.BATCHES) or 0),
        "batch_size": int(meta.get("batch_size", monte.BATCH_SIZE) or 0),
        "sportsbook_sim_inputs": sportsbook_sim_inputs,
        "ready_rows": ready_rows,
        "monitor_rows": monitor_rows,
        "seed": meta.get("seed"),
        "fingerprint": str(meta.get("fingerprint") or ""),
    }


def _render_controller_step9():
    st.markdown("## 🚀 Seven-Market Master Controller — Step 9")
    st.caption(
        "Seventh execution adapter only: current Game Total V1.5 through its native V1.4 Step-7 5M boundary. "
        "Controller Steps 1-8 are frozen/verified. Game Total source projection/probability/Monte Carlo math is unchanged. "
        "This step verifies the final independent adapter; master Run All remains locked until the next controller step."
    )

    records, all_pass, passed = controller_base._preflight_state()
    if not all_pass:
        if st.button("🔎 CHECK ALL 7 PREFLIGHTS", key="ks_step9_recheck_preflight_v30", use_container_width=True):
            st.session_state[_PREFLIGHT_KEY] = controller_base._run_preflight()
            st.rerun()
        st.warning(f"⚠️ STEP 9 LOCKED • Step-2 infrastructure preflight must be 7/7 first. Current: {passed}/7.")
    else:
        st.success("✅ STEP 2 FROZEN • 7/7 source routes + connector contracts passed. Game Total execution adapter may be tested.")

    pra_run = st.session_state.get(_PRA_RUN_KEY)
    points_run = st.session_state.get(_POINTS_RUN_KEY)
    rebounds_run = st.session_state.get(_REBOUNDS_RUN_KEY)
    assists_run = st.session_state.get(_ASSISTS_RUN_KEY)
    spread_run = st.session_state.get(_SPREAD_RUN_KEY)
    moneyline_run = st.session_state.get(_MONEYLINE_RUN_KEY)
    game_total_run = st.session_state.get(_GAME_TOTAL_RUN_KEY)

    complete = lambda x: str((x or {}).get("status") or "") == "5M COMPLETE"
    pra_complete = complete(pra_run)
    points_complete = complete(points_run)
    rebounds_complete = complete(rebounds_run)
    assists_complete = complete(assists_run)
    spread_complete = complete(spread_run)
    moneyline_complete = complete(moneyline_run)
    game_total_complete = complete(game_total_run)

    runs = (
        pra_run, points_run, rebounds_run, assists_run,
        spread_run, moneyline_run, game_total_run,
    )
    launched = sum(isinstance(x, dict) for x in runs)
    sims_total = sum(int((x or {}).get("simulations") or 0) for x in runs)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric(
        "Controller state",
        "GAME TOTAL ADAPTER VERIFIED" if game_total_complete else (
            "GAME TOTAL ADAPTER READY" if all_pass else "STEP 2 REQUIRED"
        ),
    )
    m2.metric("Execution adapters", "7/7")
    m3.metric("Models launched this session", launched)
    m4.metric("New simulations this session", f"{sims_total:,}")

    st.button(
        "🚀 RUN ALL 7 WNBA MARKETS",
        key="ks_daily_picks_run_all_7_disabled_v30",
        disabled=True,
        use_container_width=True,
        help="The seventh adapter must pass independently before master execution is enabled in the next controller step.",
    )

    if st.button(
        "📊 RUN GAME TOTAL 5,000,000 THROUGH CONTROLLER",
        key="ks_step9_run_game_total_5m_v30",
        disabled=not all_pass,
        use_container_width=True,
        help="Runs current Game Total through native Step 7 only: 5M unique integer total draws/game in 20 batches, reused across all exact sportsbook total rows.",
    ):
        try:
            with st.spinner("Game Total controller adapter is using the existing Steps 1-7 production chain…"):
                st.session_state[_GAME_TOTAL_RUN_KEY] = _run_game_total_standard_5m()
        except Exception as exc:
            monte = game_total_v15.monte
            st.session_state[_GAME_TOTAL_RUN_KEY] = {
                "status": "ERROR",
                "day": _day_str(),
                "reason": f"{type(exc).__name__}: {exc}",
                "games": 0,
                "covered_games": 0,
                "rows": 0,
                "converged": 0,
                "simulations": 0,
                "trials_per_game": int(monte.SIMULATIONS_PER_GAME),
                "batches": int(monte.BATCHES),
                "batch_size": int(monte.BATCH_SIZE),
                "sportsbook_sim_inputs": 0,
            }
        st.rerun()

    game_total_run = st.session_state.get(_GAME_TOTAL_RUN_KEY)
    if isinstance(game_total_run, dict):
        token = str(game_total_run.get("status") or "CHECK")
        if token == "5M COMPLETE":
            st.success(
                "✅ GAME TOTAL CONTROLLER ADAPTER PASSED • native Game Total Steps 1-7 completed through the controller. "
                "Every eligible game retained exactly 5M integer total draws, 20-batch convergence, coherent reuse across books, and sportsbook simulation input ZERO."
            )
        elif token == "BLOCKED":
            st.warning("⚠️ GAME TOTAL CONTROLLER BLOCKED • " + str(game_total_run.get("reason") or "source readiness gate did not pass"))
        else:
            st.error("⛔ GAME TOTAL CONTROLLER CHECK • " + str(game_total_run.get("reason") or token))

        a, b, c, d = st.columns(4)
        a.metric("Game Total day", str(game_total_run.get("day") or "—"))
        b.metric("Games simulated", f"{int(game_total_run.get('covered_games') or 0)}/{int(game_total_run.get('games') or 0)}")
        c.metric("Unique game draws", f"{int(game_total_run.get('simulations') or 0):,}")
        d.metric("Converged rows", f"{int(game_total_run.get('converged') or 0)}/{int(game_total_run.get('rows') or 0)}")

        e, f, g, h = st.columns(4)
        e.metric("Trials / game", f"{int(game_total_run.get('trials_per_game') or 0):,}")
        f.metric("Batches / game", int(game_total_run.get("batches") or 0))
        g.metric("Sportsbook sim inputs", int(game_total_run.get("sportsbook_sim_inputs") or 0))
        h.metric(
            "READY / MONITOR rows",
            f"{int(game_total_run.get('ready_rows') or 0)} / {int(game_total_run.get('monitor_rows') or 0)}",
        )

        st.caption(
            "Step 9 stops at the native Game Total Step-7 Monte Carlo boundary. Exact sportsbook totals/prices are settlement/comparison thresholds only and do not alter the Step-5 projected total, Step-6 empirical sigma, or simulated distribution. Native Step-8 grading and Daily Picks connector/ranking execution are not performed by this adapter."
        )

    st.markdown("### 🧩 Controller Market Status")
    status_map = {
        "PRA": "✅ 5M COMPLETE" if pra_complete else "✅ ADAPTER VERIFIED • STEP 3",
        "POINTS": "✅ 5M COMPLETE" if points_complete else "✅ ADAPTER VERIFIED • STEP 4",
        "REBOUNDS": "✅ 5M COMPLETE" if rebounds_complete else "✅ ADAPTER VERIFIED • STEP 5",
        "ASSISTS": "✅ 5M COMPLETE" if assists_complete else "✅ ADAPTER VERIFIED • STEP 6",
        "SPREAD": "✅ 5M COMPLETE" if spread_complete else "✅ ADAPTER VERIFIED • STEP 7",
        "MONEYLINE": "✅ 5M COMPLETE" if moneyline_complete else "✅ ADAPTER VERIFIED • STEP 8",
    }
    if game_total_complete:
        status_map["GAME TOTAL"] = "✅ 5M COMPLETE"
    elif game_total_run:
        status_map["GAME TOTAL"] = "⚠️ " + str(game_total_run.get("status") or "CHECK")
    elif all_pass:
        status_map["GAME TOTAL"] = "🟢 ADAPTER READY"
    else:
        status_map["GAME TOTAL"] = "WAITING"

    rows_ui = [st.columns(4), st.columns(3)]
    for idx, item in enumerate(_MARKETS):
        row = rows_ui[0] if idx < 4 else rows_ui[1]
        col = row[idx] if idx < 4 else row[idx - 4]
        market = item["market"]
        with col:
            st.markdown(f"**{item['icon']} {market}**")
            st.metric("Controller status", status_map.get(market, "WAITING"))

    if records:
        with st.expander("🔎 Frozen Step-2 preflight audit"):
            st.dataframe(pd.DataFrame(records), use_container_width=True, hide_index=True)

    all_seven_complete = all(
        [
            pra_complete, points_complete, rebounds_complete, assists_complete,
            spread_complete, moneyline_complete, game_total_complete,
        ]
    )
    if all_seven_complete:
        st.success(
            "🏁 ALL 7 EXECUTION ADAPTERS VERIFIED • independent adapter testing is complete. "
            "The next controller step can safely wire the single master Run All 7 orchestration button without changing any source model."
        )

    st.caption(
        "Step 9 contract • adapters wired 7/7 • prior six adapters frozen/verified • Game Total source math changed 0 • "
        "Game Total native Steps 1-7 only • exactly 5,000,000 unique integer draws/game • 20 batches/game • same game outcomes reused across books • "
        "sportsbook simulation inputs 0 • Game Total Step 8 auto-run 0 • connector writes 0 • Daily Picks ranking changes 0"
    )
    st.markdown("---")


def render_wnba_daily_picks_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _render_controller_step9()
    return v21.render_wnba_daily_picks_hub(
        section_header=section_header,
        status_info=status_info,
        team_logo=team_logo,
        h=h,
    )


__all__ = ["MODEL_VERSION", "render_wnba_daily_picks_hub"]
