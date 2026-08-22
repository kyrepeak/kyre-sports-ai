"""WNBA Daily Picks V27 — Step-6 Assists execution adapter.

Preserves the complete Daily Picks V21 seven-market production/verification surface
and the independently verified controller Steps 1-5. Step 6 wires exactly one new
execution adapter: the native Assists V17 model boundary.

The adapter uses the existing Assists V16 renderer to build/validate the native
Steps 1-16 state, then calls the existing V17 Monte Carlo routine without copying
or changing its model math. It preserves exactly 5,000,000 base trials per active
calibrated player, 20 x 250,000 deterministic batches, convergence checks and the
existing deterministic sensitivity layer. Steps 18-20, Daily Picks connector
writes, cross-market ranking and Spread/Moneyline/Game Total execution remain
unwired in this controller step. Run All 7 remains disabled.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

import wnba_daily_picks_hub_v26 as prior
import wnba_daily_picks_hub_v21 as v21
import wnba_assists_hub_v17 as assists_v17

MODEL_VERSION = "WNBA DAILY PICKS V27 • MASTER CONTROLLER STEP 6 • ASSISTS 5M ADAPTER"
_ET = ZoneInfo("America/New_York")

_PREFLIGHT_KEY = prior._PREFLIGHT_KEY
_PRA_RUN_KEY = prior._PRA_RUN_KEY
_POINTS_RUN_KEY = prior._POINTS_RUN_KEY
_REBOUNDS_RUN_KEY = prior._REBOUNDS_RUN_KEY
_ASSISTS_RUN_KEY = "ks_run_all_7_step6_assists_v27"
_MARKETS = prior._MARKETS


def _day_str() -> str:
    return datetime.now(_ET).strftime("%Y-%m-%d")


def _build_native_step16(day_str: str):
    """Render only the existing Assists Steps 1-16 chain in a disposable slot."""
    slot = st.empty()
    try:
        with slot.container():
            assists_v17.v16.render_wnba_assists_hub(None, None, None, None)
    finally:
        slot.empty()

    distribution = st.session_state.get(f"wnba_assists_v16_distribution::{day_str}")
    diag16 = st.session_state.get(f"wnba_assists_v16_diag::{day_str}") or {}
    if not isinstance(distribution, pd.DataFrame):
        distribution = pd.DataFrame()
    return distribution, dict(diag16 or {})


def _run_assists_standard_5m():
    """Execute the native Assists chain exactly through Step 17."""
    day_str = _day_str()
    distribution, diag16 = _build_native_step16(day_str)
    step16_ready = bool(diag16.get("ready") and not distribution.empty)

    if not step16_ready:
        return {
            "status": "BLOCKED",
            "day": day_str,
            "reason": str(diag16.get("reason") or "Native Assists Step 16 is not READY."),
            "players": 0,
            "simulations": 0,
            "converged": 0,
            "sensitivity_rows": 0,
            "trials_per_player": int(assists_v17.BASE_SIMS),
            "batches": int(assists_v17.BATCHES),
        }

    progress = st.progress(0.0, text="Controller: running Assists native Step-17 5M…")

    def _progress(frac, row, summary):
        player = str(row.get("PLAYER_NAME") or "player")
        state = "converged" if summary.get("CONVERGED") else "checking"
        progress.progress(
            min(1.0, max(0.0, float(frac))),
            text=f"Assists 5M • {player} • {state}",
        )

    try:
        summary, sensitivity, diag = assists_v17._run_monte_carlo(
            distribution,
            day_str,
            progress_callback=_progress,
        )
    finally:
        progress.empty()

    if not isinstance(summary, pd.DataFrame):
        summary = pd.DataFrame()
    if not isinstance(sensitivity, pd.DataFrame):
        sensitivity = pd.DataFrame()
    diag = dict(diag or {})

    # Store the result under the source module's own native V17 persistence keys.
    # This is the same snapshot contract written by the live Step-17 button.
    fingerprint = assists_v17._distribution_fingerprint(distribution, day_str)
    snapshot = {
        "fingerprint": fingerprint,
        "base_sims_per_player": int(assists_v17.BASE_SIMS),
        "summary": summary.copy(),
        "sensitivity": sensitivity.copy(),
        "diag": dict(diag),
        "checked_at_et": datetime.now(_ET).strftime("%Y-%m-%d %I:%M:%S %p ET"),
    }
    st.session_state[assists_v17._snapshot_key(day_str)] = snapshot
    st.session_state[f"wnba_assists_v17_diag::{day_str}"] = dict(diag)
    st.session_state[f"wnba_assists_v17_summary::{day_str}"] = summary.copy()

    if summary.empty:
        return {
            "status": "BLOCKED",
            "day": day_str,
            "reason": str(diag.get("reason") or "Native Assists Step 17 produced no player summary."),
            "players": 0,
            "simulations": 0,
            "converged": 0,
            "sensitivity_rows": int(len(sensitivity)),
            "trials_per_player": int(assists_v17.BASE_SIMS),
            "batches": int(assists_v17.BATCHES),
        }

    sims = pd.to_numeric(summary.get("SIMULATIONS"), errors="coerce").fillna(0)
    converged = summary.get("CONVERGED", pd.Series(False, index=summary.index)).fillna(False).astype(bool)
    complete = bool(
        diag.get("ready")
        and len(summary) > 0
        and (sims >= int(assists_v17.BASE_SIMS)).all()
        and converged.all()
    )

    return {
        "status": "5M COMPLETE" if complete else "CHECK",
        "day": day_str,
        "reason": "" if complete else str(diag.get("reason") or "One or more native Assists Step-17 simulations failed convergence."),
        "players": int(len(summary)),
        "simulations": int(sims.sum()),
        "converged": int(converged.sum()),
        "sensitivity_rows": int(len(sensitivity)),
        "trials_per_player": int(assists_v17.BASE_SIMS),
        "batches": int(assists_v17.BATCHES),
        "batch_size": int(assists_v17.BATCH_SIZE),
        "market_input": "NONE",
        "h2h_influence": "0%",
        "fingerprint": fingerprint,
    }


def _render_controller_step6():
    st.markdown("## 🚀 Seven-Market Master Controller — Step 6")
    st.caption(
        "Fourth execution adapter only: native Assists Steps 1-17. Controller Steps 1-5 are frozen/verified. "
        "Assists V17 model and Monte Carlo math are unchanged; Steps 18-20 are intentionally not controller-run yet. "
        "Spread, Moneyline and Game Total remain unwired."
    )

    records, all_pass, passed = prior._preflight_state()
    if not all_pass:
        if st.button("🔎 CHECK ALL 7 PREFLIGHTS", key="ks_step6_recheck_preflight_v27", use_container_width=True):
            st.session_state[_PREFLIGHT_KEY] = prior._run_preflight()
            st.rerun()
        st.warning(f"⚠️ STEP 6 LOCKED • Step-2 infrastructure preflight must be 7/7 first. Current: {passed}/7.")
    else:
        st.success("✅ STEP 2 FROZEN • 7/7 source routes + connector contracts passed. Assists execution adapter may be tested.")

    pra_run = st.session_state.get(_PRA_RUN_KEY)
    points_run = st.session_state.get(_POINTS_RUN_KEY)
    rebounds_run = st.session_state.get(_REBOUNDS_RUN_KEY)
    assists_run = st.session_state.get(_ASSISTS_RUN_KEY)

    pra_complete = str((pra_run or {}).get("status") or "") == "5M COMPLETE"
    points_complete = str((points_run or {}).get("status") or "") == "5M COMPLETE"
    rebounds_complete = str((rebounds_run or {}).get("status") or "") == "5M COMPLETE"
    assists_complete = str((assists_run or {}).get("status") or "") == "5M COMPLETE"

    runs = (pra_run, points_run, rebounds_run, assists_run)
    launched = sum(isinstance(x, dict) for x in runs)
    sims_total = sum(int((x or {}).get("simulations") or 0) for x in runs)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Controller state", "ASSISTS ADAPTER VERIFIED" if assists_complete else ("ASSISTS ADAPTER READY" if all_pass else "STEP 2 REQUIRED"))
    m2.metric("Execution adapters", "4/7")
    m3.metric("Models launched this session", launched)
    m4.metric("New simulations this session", f"{sims_total:,}")

    st.button(
        "🚀 RUN ALL 7 WNBA MARKETS",
        key="ks_daily_picks_run_all_7_disabled_v27",
        disabled=True,
        use_container_width=True,
        help="Master execution stays locked until all seven adapters are independently verified.",
    )

    if st.button(
        "🧠 RUN ASSISTS 5,000,000 THROUGH CONTROLLER",
        key="ks_step6_run_assists_5m_v27",
        disabled=not all_pass,
        use_container_width=True,
        help="Runs the existing Assists model through native Step 17 only: 5M/player + 20-batch convergence + deterministic sensitivity. Steps 18-20 are not controller-run in Step 6.",
    ):
        try:
            with st.spinner("Assists controller adapter is using the existing Steps 1-17 production chain…"):
                st.session_state[_ASSISTS_RUN_KEY] = _run_assists_standard_5m()
        except Exception as exc:
            st.session_state[_ASSISTS_RUN_KEY] = {
                "status": "ERROR",
                "day": _day_str(),
                "reason": f"{type(exc).__name__}: {exc}",
                "players": 0,
                "simulations": 0,
                "converged": 0,
                "sensitivity_rows": 0,
                "trials_per_player": int(assists_v17.BASE_SIMS),
                "batches": int(assists_v17.BATCHES),
            }
        st.rerun()

    assists_run = st.session_state.get(_ASSISTS_RUN_KEY)
    if isinstance(assists_run, dict):
        token = str(assists_run.get("status") or "CHECK")
        if token == "5M COMPLETE":
            st.success(
                "✅ ASSISTS CONTROLLER ADAPTER PASSED • native Assists Steps 1-17 completed through the controller. "
                "Every simulated player retained the existing 5M, 20-batch convergence and deterministic sensitivity contracts; sportsbook and H2H influence remained excluded from the Step-17 model branch."
            )
        elif token == "BLOCKED":
            st.warning("⚠️ ASSISTS CONTROLLER BLOCKED • " + str(assists_run.get("reason") or "source readiness gate did not pass"))
        else:
            st.error("⛔ ASSISTS CONTROLLER CHECK • " + str(assists_run.get("reason") or token))

        a, b, c, d = st.columns(4)
        a.metric("Assists day", str(assists_run.get("day") or "—"))
        b.metric("Player simulations", int(assists_run.get("players") or 0))
        c.metric("Completed simulations", f"{int(assists_run.get('simulations') or 0):,}")
        d.metric("Converged", f"{int(assists_run.get('converged') or 0)}/{int(assists_run.get('players') or 0)}")

        e, f, g, h = st.columns(4)
        e.metric("Trials / player", f"{int(assists_run.get('trials_per_player') or 0):,}")
        f.metric("Batches", int(assists_run.get("batches") or 0))
        g.metric("Market input", str(assists_run.get("market_input") or "NONE"))
        h.metric("H2H influence", str(assists_run.get("h2h_influence") or "0%"))

        st.caption(
            "Step 6 intentionally stops at the native Assists Step-17 boundary. Steps 18-20 and the source final-card ranking remain unwired until this adapter is independently verified."
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
            if assists_complete:
                value = "✅ 5M COMPLETE"
            elif assists_run:
                value = "⚠️ " + str(assists_run.get("status") or "CHECK")
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
        "Step 6 contract • adapters wired 4/7 • PRA + Points + Rebounds adapters frozen/verified • Assists source math changed 0 • "
        "Assists native Steps 1-17 only • 5,000,000 simulations/player • 20 batches • deterministic sensitivity preserved • "
        "Assists Steps 18-20 auto-run 0 • Spread/Moneyline/Game Total executed 0 • connector writes 0 • Daily Picks ranking changes 0"
    )
    st.markdown("---")


def render_wnba_daily_picks_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _render_controller_step6()
    return v21.render_wnba_daily_picks_hub(
        section_header=section_header,
        status_info=status_info,
        team_logo=team_logo,
        h=h,
    )


__all__ = ["MODEL_VERSION", "render_wnba_daily_picks_hub"]
