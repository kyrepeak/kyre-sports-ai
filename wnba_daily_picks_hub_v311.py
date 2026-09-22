"""WNBA Daily Picks V31.1 — checkpointed Step-10 Run All 7 orchestration repair.

V31 proved all seven source routes and adapters, but its master button attempted to
execute the entire seven-market chain inside one Streamlit widget callback. A
controller-level interruption before the first adapter returned could leave the
master record at 0/7 with every adapter still appearing READY, which is exactly the
observed failure signature.

V31.1 changes only orchestration. The seven already-verified adapters and all source
model math remain untouched. RUN ALL 7 is now a checkpointed state machine: one
verified adapter executes per Streamlit script pass, its native result is validated
and persisted, then the controller reruns itself and advances to the next market.
This prevents a single long widget callback from owning the full chain and makes
every transition recoverable/auditable. It remains fail-closed and preserves the
fixed order PRA -> Points -> Rebounds -> Assists -> Spread -> Moneyline -> Game Total.
"""
from __future__ import annotations

from datetime import datetime
from time import monotonic

import pandas as pd
import streamlit as st

import wnba_daily_picks_hub_v31 as base

MODEL_VERSION = "WNBA DAILY PICKS V31.1 • MASTER CONTROLLER STEP 10 • CHECKPOINTED RUN ALL 7"
_MASTER_RUN_KEY = "ks_run_all_7_master_v311"

_STAGE_SPECS = (
    ("PRA", "🧮", base._PRA_RUN_KEY),
    ("POINTS", "🎯", base._POINTS_RUN_KEY),
    ("REBOUNDS", "🧱", base._REBOUNDS_RUN_KEY),
    ("ASSISTS", "🧠", base._ASSISTS_RUN_KEY),
    ("SPREAD", "🏀", base._SPREAD_RUN_KEY),
    ("MONEYLINE", "💰", base._MONEYLINE_RUN_KEY),
    ("GAME TOTAL", "📊", base._GAME_TOTAL_RUN_KEY),
)


def _today_str() -> str:
    return datetime.now(base._ET).strftime("%Y-%m-%d")


def _resolve_runner(market: str):
    """Resolve exactly one runner only when that stage is about to execute."""
    if market == "PRA":
        return base.controller_base._run_pra_standard_5m
    if market == "POINTS":
        return base.controller_base._run_points_standard_5m
    if market == "REBOUNDS":
        return base.rebounds_adapter._run_rebounds_standard_5m
    if market == "ASSISTS":
        return base.assists_adapter._run_assists_standard_5m
    if market == "SPREAD":
        return base.spread_adapter._run_spread_standard_5m
    if market == "MONEYLINE":
        return base.moneyline_adapter._run_moneyline_standard_5m
    if market == "GAME TOTAL":
        return base.game_total_adapter._run_game_total_standard_5m
    raise KeyError(f"Unknown controller market: {market}")


def _fresh_master(day_str: str) -> dict:
    return {
        "status": "RUNNING",
        "day": day_str,
        "started_at_et": datetime.now(base._ET).strftime("%Y-%m-%d %I:%M:%S %p ET"),
        "finished_at_et": "",
        "completed_markets": 0,
        "next_index": 0,
        "active_market": "",
        "attempt_in_progress": False,
        "failed_market": "",
        "reason": "",
        "simulations": 0,
        "stages": [],
    }


def _stop(master: dict, market: str, reason: str) -> dict:
    out = dict(master or {})
    out.update({
        "status": "STOPPED",
        "failed_market": str(market or "CONTROLLER"),
        "reason": str(reason or "native completion contract failed"),
        "active_market": "",
        "attempt_in_progress": False,
        "finished_at_et": datetime.now(base._ET).strftime("%Y-%m-%d %I:%M:%S %p ET"),
    })
    return out


def _advance_one_stage(master: dict) -> dict:
    """Execute at most one adapter, checkpoint it, then advance on the next rerun."""
    master = dict(master or {})
    day_str = _today_str()
    if str(master.get("day") or "") != day_str:
        return _stop(master, "CONTROLLER", f"controller slate changed from {master.get('day')} to {day_str}")

    idx = int(master.get("next_index") or 0)
    if idx >= len(_STAGE_SPECS):
        master.update({
            "status": "7/7 COMPLETE",
            "completed_markets": 7,
            "active_market": "",
            "attempt_in_progress": False,
            "finished_at_et": datetime.now(base._ET).strftime("%Y-%m-%d %I:%M:%S %p ET"),
        })
        return master

    market, icon, result_key = _STAGE_SPECS[idx]

    # If a prior script pass entered this stage but never returned a result, fail
    # closed instead of looping invisibly. This makes any Streamlit control-flow
    # interruption explicit in the audit.
    if bool(master.get("attempt_in_progress")) and str(master.get("active_market") or "") == market:
        return _stop(
            master,
            market,
            "the prior adapter attempt did not return to the master controller; execution was interrupted before a native result could be checkpointed",
        )

    master["active_market"] = market
    master["attempt_in_progress"] = True
    st.session_state[_MASTER_RUN_KEY] = master

    # Clear only the stage about to be refreshed. Never wipe all seven results at
    # once; completed checkpoints remain inspectable if a later market fails.
    st.session_state.pop(result_key, None)

    try:
        runner = _resolve_runner(market)
    except Exception as exc:
        return _stop(master, market, f"runner resolution failed: {type(exc).__name__}: {exc}")

    started = monotonic()
    try:
        with st.spinner(f"{icon} Run All 7 • {idx + 1}/7 • {market} using its verified native adapter…"):
            result = runner()
    except Exception as exc:
        result = {
            "status": "ERROR",
            "day": day_str,
            "reason": f"{type(exc).__name__}: {exc}",
            "simulations": 0,
        }
    seconds = max(0.0, monotonic() - started)
    result = dict(result or {})
    st.session_state[result_key] = result

    ok, reason = base._validate_contract(market, result, day_str)
    stage_row = {
        "Order": idx + 1,
        "Market": market,
        "State": "PASS" if ok else "STOP",
        "Units": base._stage_units(market, result),
        "Simulations": int(result.get("simulations") or 0),
        "Converged": base._stage_convergence(market, result),
        "Seconds": round(seconds, 1),
        "Reason": "" if ok else reason,
    }

    rows = list(master.get("stages") or [])
    rows.append(stage_row)
    master["stages"] = rows
    master["simulations"] = int(master.get("simulations") or 0) + int(stage_row["Simulations"])
    master["attempt_in_progress"] = False
    master["active_market"] = ""

    if not ok:
        master["completed_markets"] = idx
        return _stop(master, market, reason)

    master["completed_markets"] = idx + 1
    master["next_index"] = idx + 1
    if idx + 1 >= len(_STAGE_SPECS):
        master.update({
            "status": "7/7 COMPLETE",
            "completed_markets": 7,
            "finished_at_et": datetime.now(base._ET).strftime("%Y-%m-%d %I:%M:%S %p ET"),
        })
    return master


def _render_step10_checkpointed():
    st.markdown("## 🚀 Seven-Market Master Controller — Step 10")
    st.caption(
        "Checkpointed master orchestration. The seven independently verified adapters run in fixed order — "
        "PRA → Points → Rebounds → Assists → Spread → Moneyline → Game Total. One native adapter is executed "
        "and validated per Streamlit pass, then the controller checkpoints and advances automatically. Source-model math and Daily Picks ranking remain unchanged."
    )
    st.caption("🛠️ Daily Picks V31.1 • checkpointed Run All 7 repair ACTIVE")

    records, all_pass, passed = base.controller_base._preflight_state()
    if not all_pass:
        if st.button("🔎 CHECK ALL 7 PREFLIGHTS", key="ks_step10_preflight_v311", use_container_width=True):
            st.session_state[base._PREFLIGHT_KEY] = base.controller_base._run_preflight()
            st.rerun()
        st.warning(f"⚠️ RUN ALL 7 LOCKED • infrastructure preflight must be 7/7. Current: {passed}/7.")
    else:
        st.success("✅ MASTER EXECUTION READY • all 7 adapter paths are independently verified and infrastructure preflight is 7/7.")

    master = st.session_state.get(_MASTER_RUN_KEY)
    if isinstance(master, dict) and str(master.get("status") or "") == "RUNNING":
        master = _advance_one_stage(master)
        st.session_state[_MASTER_RUN_KEY] = master
        if str(master.get("status") or "") == "RUNNING":
            st.rerun()

    master = st.session_state.get(_MASTER_RUN_KEY)
    token = str((master or {}).get("status") or "") if isinstance(master, dict) else ""
    master_complete = token == "7/7 COMPLETE"
    master_running = token == "RUNNING"

    a, b, c, d = st.columns(4)
    a.metric("Verified adapters", "7/7")
    b.metric("Master state", "COMPLETE" if master_complete else ("RUNNING" if master_running else ("READY" if all_pass else "LOCKED")))
    c.metric("Completed markets", int((master or {}).get("completed_markets") or 0))
    d.metric("Master simulations", f"{int((master or {}).get('simulations') or 0):,}")

    active = str((master or {}).get("active_market") or "") if isinstance(master, dict) else ""
    if master_running:
        next_idx = int((master or {}).get("next_index") or 0)
        label = active or (_STAGE_SPECS[next_idx][0] if next_idx < len(_STAGE_SPECS) else "FINALIZING")
        st.info(f"⏳ RUN ALL 7 IN PROGRESS • completed {int(master.get('completed_markets') or 0)}/7 • next/current: {label}")

    if st.button(
        "🚀 RUN ALL 7 WNBA MARKETS",
        key="ks_daily_picks_run_all_7_v311",
        disabled=(not all_pass) or master_running,
        use_container_width=True,
        type="primary",
        help="Checkpointed sequential fail-closed orchestration. One verified native adapter per Streamlit pass; no connector/ranking/backfill stage is added.",
    ):
        st.session_state[_MASTER_RUN_KEY] = _fresh_master(_today_str())
        st.rerun()

    master = st.session_state.get(_MASTER_RUN_KEY)
    if isinstance(master, dict):
        token = str(master.get("status") or "")
        if token == "7/7 COMPLETE":
            st.success(
                "🏁 RUN ALL 7 COMPLETE • all seven verified WNBA adapters passed sequentially on the same ET slate. "
                "No source-model math, connector ranking, backfill or forced-pick logic was added."
            )
        elif token == "STOPPED":
            st.error(
                "⛔ RUN ALL 7 STOPPED FAIL-CLOSED • "
                + str(master.get("failed_market") or "unknown stage")
                + " did not return a valid native completion contract. Later markets were not executed."
            )
            st.warning(str(master.get("reason") or "Inspect the stage audit below."))

        stages = list(master.get("stages") or [])
        if stages:
            st.markdown("### 🧾 Run All 7 Sequential Audit")
            st.dataframe(pd.DataFrame(stages), use_container_width=True, hide_index=True)

        x, y, z = st.columns(3)
        x.metric("Run slate", str(master.get("day") or "—"))
        y.metric("Markets passed", f"{int(master.get('completed_markets') or 0)}/7")
        z.metric("Total simulations", f"{int(master.get('simulations') or 0):,}")
        if master.get("started_at_et") or master.get("finished_at_et"):
            st.caption(f"Started {master.get('started_at_et') or '—'} • finished {master.get('finished_at_et') or '—'}")

    st.markdown("### 🧩 Master Adapter Status")
    key_map = {market: key for market, _icon, key in _STAGE_SPECS}
    rows_ui = [st.columns(4), st.columns(3)]
    for idx, item in enumerate(base._MARKETS):
        market = item["market"]
        result = st.session_state.get(key_map[market])
        value = "✅ 5M COMPLETE" if base._complete(result) else (
            "⚠️ " + str((result or {}).get("status") or "NOT RUN") if isinstance(result, dict) else "READY"
        )
        row = rows_ui[0] if idx < 4 else rows_ui[1]
        col = row[idx] if idx < 4 else row[idx - 4]
        with col:
            st.markdown(f"**{item['icon']} {market}**")
            st.metric("Master status", value)

    if records:
        with st.expander("🔎 Frozen 7/7 infrastructure preflight"):
            st.dataframe(pd.DataFrame(records), use_container_width=True, hide_index=True)

    st.caption(
        "Step 10 V31.1 contract • verified adapters 7/7 • checkpoint after every market • fixed sequential order • fail closed on first non-PASS • "
        "current ET slate enforced • source model math changed 0 • native simulation contracts preserved • connector writes 0 • backfills 0 • "
        "cross-market ranking changes 0 • forced picks 0"
    )
    st.markdown("---")


# Patch only the V31 Step-10 orchestration renderer. Its existing source imports,
# validators, adapter helpers and V21 Daily Picks surface remain the owners.
base._render_step10 = _render_step10_checkpointed


def render_wnba_daily_picks_hub(section_header=None, status_info=None, team_logo=None, h=None):
    return base.render_wnba_daily_picks_hub(
        section_header=section_header,
        status_info=status_info,
        team_logo=team_logo,
        h=h,
    )


__all__ = ["MODEL_VERSION", "render_wnba_daily_picks_hub"]
