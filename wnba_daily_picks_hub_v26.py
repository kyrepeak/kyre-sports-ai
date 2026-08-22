"""WNBA Daily Picks V26 — Step-5 Rebounds execution adapter.

Preserves the complete Daily Picks V21 seven-market production/verification surface
and the independently verified controller Steps 1-4. Step 5 wires exactly one new
execution adapter: the existing Rebounds V2.6 Step-17 boundary, which is the same
Steps 1-17 chain consumed unchanged by current Rebounds V2.9.

The adapter invokes the native Rebounds renderer only through Step 17, so the source
itself builds/validates Steps 1-16 and performs its existing 5,000,000 simulations
per verified player, 20-batch convergence checks and +/-5% sensitivity. Steps 18-20,
Daily Picks connector writes, cross-market ranking and the other four unwired market
adapters are not executed by this controller step. Run All 7 remains disabled.
"""
from __future__ import annotations

import pandas as pd
import streamlit as st

import wnba_daily_picks_hub_v25 as prior
import wnba_daily_picks_hub_v21 as v21
import wnba_rebounds_hub_v26 as rebounds_v26

MODEL_VERSION = "WNBA DAILY PICKS V26 • MASTER CONTROLLER STEP 5 • REBOUNDS 5M ADAPTER"

_PREFLIGHT_KEY = prior._PREFLIGHT_KEY
_PRA_RUN_KEY = prior._PRA_RUN_KEY
_POINTS_RUN_KEY = prior._POINTS_RUN_KEY
_REBOUNDS_RUN_KEY = "ks_run_all_7_step5_rebounds_v26"
_MARKETS = prior._MARKETS


def _run_rebounds_standard_5m():
    """Execute the native Rebounds chain exactly through current Step 17."""
    # Render inside a disposable placeholder so the source owns every upstream
    # state transition without duplicating model logic on the Daily Picks page.
    # V2.6 is intentionally the Step-17 boundary; V2.7-V2.9 only add Steps 18-20.
    slot = st.empty()
    try:
        with slot.container():
            rebounds_v26.render_wnba_rebounds_hub(None, None, None, None)
    finally:
        slot.empty()

    frame = pd.DataFrame(st.session_state.get("wnba_rebounds_step17_players") or [])
    ready = bool(st.session_state.get("wnba_rebounds_step17_ready"))
    sensitivity = pd.DataFrame(st.session_state.get("wnba_rebounds_step17_sensitivity") or [])

    if frame.empty:
        return {
            "status": "BLOCKED",
            "reason": "Native Rebounds Steps 1-17 produced no Step-17 player frame.",
            "players": 0,
            "simulations": 0,
            "converged": 0,
            "sensitivity_rows": int(len(sensitivity)),
        }

    sims = pd.to_numeric(frame.get("MC simulations"), errors="coerce").fillna(0)
    states = frame.get("Step17 state", pd.Series("CHECK", index=frame.index)).astype(str)
    conv = frame.get("MC convergence", pd.Series("CHECK", index=frame.index)).astype(str)
    verified = states.eq("VERIFIED") & conv.eq("PASS")
    complete = bool(
        ready
        and len(frame) > 0
        and (sims >= int(rebounds_v26.BASE_SIMULATIONS)).all()
        and verified.all()
    )

    day = None
    for key in (
        "wnba_rebounds_date",
        "wnba_rebounds_slate_date",
        "wnba_rebounds_date_control",
    ):
        if st.session_state.get(key) is not None:
            day = st.session_state.get(key)
            break
    if day is None:
        day = prior._today_et()

    return {
        "status": "5M COMPLETE" if complete else "CHECK",
        "day": pd.to_datetime(day).strftime("%Y-%m-%d"),
        "reason": "" if complete else "One or more native Rebounds Step-17 player simulations failed readiness/convergence.",
        "players": int(len(frame)),
        "simulations": int(sims.sum()),
        "converged": int(verified.sum()),
        "sensitivity_rows": int(len(sensitivity)),
        "trials_per_player": int(rebounds_v26.BASE_SIMULATIONS),
        "batches": int(rebounds_v26.BATCHES),
        "market_input": bool(frame.get("MC market input", pd.Series(False, index=frame.index)).fillna(False).astype(bool).any()),
    }


def _render_controller_step5():
    st.markdown("## 🚀 Seven-Market Master Controller — Step 5")
    st.caption(
        "Third execution adapter only: current Rebounds Steps 1-17 through the native V2.6 Step-17 boundary. "
        "Steps 1-4 of this controller are frozen/verified. Rebounds V2.9 projection and simulation math is unchanged; "
        "Steps 18-20 are intentionally not controller-run yet. Assists, Spread, Moneyline and Game Total remain unwired."
    )

    records, all_pass, passed = prior._preflight_state()
    if not all_pass:
        if st.button("🔎 CHECK ALL 7 PREFLIGHTS", key="ks_step5_recheck_preflight_v26", use_container_width=True):
            st.session_state[_PREFLIGHT_KEY] = prior._run_preflight()
            st.rerun()
        st.warning(f"⚠️ STEP 5 LOCKED • Step-2 infrastructure preflight must be 7/7 first. Current: {passed}/7.")
    else:
        st.success("✅ STEP 2 FROZEN • 7/7 source routes + connector contracts passed. Rebounds execution adapter may be tested.")

    pra_run = st.session_state.get(_PRA_RUN_KEY)
    points_run = st.session_state.get(_POINTS_RUN_KEY)
    rebounds_run = st.session_state.get(_REBOUNDS_RUN_KEY)

    pra_complete = str((pra_run or {}).get("status") or "") == "5M COMPLETE"
    points_complete = str((points_run or {}).get("status") or "") == "5M COMPLETE"
    rebounds_status = str((rebounds_run or {}).get("status") or "NOT RUN")
    rebounds_complete = rebounds_status == "5M COMPLETE"

    launched = sum(isinstance(x, dict) for x in (pra_run, points_run, rebounds_run))
    sims_total = sum(int((x or {}).get("simulations") or 0) for x in (pra_run, points_run, rebounds_run))

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Controller state", "REBOUNDS ADAPTER VERIFIED" if rebounds_complete else ("REBOUNDS ADAPTER READY" if all_pass else "STEP 2 REQUIRED"))
    m2.metric("Execution adapters", "3/7")
    m3.metric("Models launched this session", launched)
    m4.metric("New simulations this session", f"{sims_total:,}")

    st.button(
        "🚀 RUN ALL 7 WNBA MARKETS",
        key="ks_daily_picks_run_all_7_disabled_v26",
        disabled=True,
        use_container_width=True,
        help="Master execution stays locked until all seven adapters are independently verified.",
    )

    if st.button(
        "🧱 RUN REBOUNDS 5,000,000 THROUGH CONTROLLER",
        key="ks_step5_run_rebounds_5m_v26",
        disabled=not all_pass,
        use_container_width=True,
        help="Runs the existing Rebounds model only through native Step 17: 5M/player + convergence + +/-5% sensitivity. Steps 18-20 are not controller-run in Step 5.",
    ):
        try:
            with st.spinner("Rebounds controller adapter is using the existing Steps 1-17 production chain…"):
                st.session_state[_REBOUNDS_RUN_KEY] = _run_rebounds_standard_5m()
        except Exception as exc:
            st.session_state[_REBOUNDS_RUN_KEY] = {
                "status": "ERROR",
                "day": pd.to_datetime(prior._today_et()).strftime("%Y-%m-%d"),
                "reason": f"{type(exc).__name__}: {exc}",
                "players": 0,
                "simulations": 0,
                "converged": 0,
                "sensitivity_rows": 0,
            }
        st.rerun()

    rebounds_run = st.session_state.get(_REBOUNDS_RUN_KEY)
    if isinstance(rebounds_run, dict):
        token = str(rebounds_run.get("status") or "CHECK")
        if token == "5M COMPLETE":
            st.success(
                "✅ REBOUNDS CONTROLLER ADAPTER PASSED • native Rebounds Steps 1-17 completed through the controller. "
                "Every verified player retained the existing 5M, 20-batch convergence and +/-5% sensitivity contracts; market input remained excluded."
            )
        elif token == "BLOCKED":
            st.warning("⚠️ REBOUNDS CONTROLLER BLOCKED • " + str(rebounds_run.get("reason") or "source readiness gate did not pass"))
        else:
            st.error("⛔ REBOUNDS CONTROLLER CHECK • " + str(rebounds_run.get("reason") or token))

        a, b, c, d = st.columns(4)
        a.metric("Rebounds day", str(rebounds_run.get("day") or "—"))
        b.metric("Player simulations", int(rebounds_run.get("players") or 0))
        c.metric("Completed simulations", f"{int(rebounds_run.get('simulations') or 0):,}")
        d.metric("Converged", f"{int(rebounds_run.get('converged') or 0)}/{int(rebounds_run.get('players') or 0)}")

        e, f, g = st.columns(3)
        e.metric("Trials / player", f"{int(rebounds_run.get('trials_per_player') or 0):,}")
        f.metric("Batches", int(rebounds_run.get("batches") or 0))
        g.metric("Market input", "NONE" if not rebounds_run.get("market_input") else "CHECK")

        st.caption(
            "Step 5 intentionally stops at the native Rebounds Step-17 boundary. Steps 18-20 and the source final-card ranking remain unwired until this adapter is independently verified."
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
            if rebounds_complete:
                value = "✅ 5M COMPLETE"
            elif rebounds_run:
                value = "⚠️ " + str(rebounds_run.get("status") or "CHECK")
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
        "Step 5 contract • adapters wired 3/7 • PRA + Points adapters frozen/verified • Rebounds source math changed 0 • "
        "Rebounds native Steps 1-17 only • 5,000,000 simulations/player • 20 batches • +/-5% sensitivity preserved • "
        "other source models executed 0 • Rebounds Steps 18-20 auto-run 0 • connector writes 0 • Daily Picks ranking changes 0"
    )
    st.markdown("---")


def render_wnba_daily_picks_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _render_controller_step5()
    return v21.render_wnba_daily_picks_hub(
        section_header=section_header,
        status_info=status_info,
        team_logo=team_logo,
        h=h,
    )


__all__ = ["MODEL_VERSION", "render_wnba_daily_picks_hub"]
