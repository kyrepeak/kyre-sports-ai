"""WNBA Daily Picks V31 — Step-10 master Run All 7 orchestration.

Preserves the complete Daily Picks V21 seven-market production/verification surface
and independently verified controller Steps 1-9. All seven execution adapters are
now individually proven. Step 10 adds only one orchestration action: run the seven
already-verified adapters sequentially in the fixed order
PRA -> Points -> Rebounds -> Assists -> Spread -> Moneyline -> Game Total.

No source-model projection, probability, market, grading, Monte Carlo, calibration,
qualification, ranking or persistence math is copied or changed. Each stage calls
its existing verified adapter helper, validates that helper's native completion
contract for the current ET slate, stores the result under the same controller key
used during independent testing, and advances only after PASS. The sequence stops
immediately on BLOCKED/CHECK/ERROR or same-day/contract mismatch. No Daily Picks
connector writes, cross-market ranking changes, backfills or forced picks occur in
this step.
"""
from __future__ import annotations

from datetime import datetime
from time import monotonic
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

import wnba_daily_picks_hub_v21 as v21
import wnba_daily_picks_hub_v25 as controller_base
import wnba_daily_picks_hub_v26 as rebounds_adapter
import wnba_daily_picks_hub_v27 as assists_adapter
import wnba_daily_picks_hub_v281 as spread_adapter
import wnba_daily_picks_hub_v29 as moneyline_adapter
import wnba_daily_picks_hub_v30 as game_total_adapter

MODEL_VERSION = "WNBA DAILY PICKS V31 • MASTER CONTROLLER STEP 10 • RUN ALL 7"
_ET = ZoneInfo("America/New_York")

_PREFLIGHT_KEY = controller_base._PREFLIGHT_KEY
_PRA_RUN_KEY = controller_base._PRA_RUN_KEY
_POINTS_RUN_KEY = controller_base._POINTS_RUN_KEY
_REBOUNDS_RUN_KEY = rebounds_adapter._REBOUNDS_RUN_KEY
_ASSISTS_RUN_KEY = assists_adapter._ASSISTS_RUN_KEY
_SPREAD_RUN_KEY = spread_adapter._SPREAD_RUN_KEY
_MONEYLINE_RUN_KEY = moneyline_adapter._MONEYLINE_RUN_KEY
_GAME_TOTAL_RUN_KEY = game_total_adapter._GAME_TOTAL_RUN_KEY
_MASTER_RUN_KEY = "ks_run_all_7_master_v31"

_MARKETS = controller_base._MARKETS


def _today_str() -> str:
    return datetime.now(_ET).strftime("%Y-%m-%d")


def _complete(result) -> bool:
    return isinstance(result, dict) and str(result.get("status") or "").upper() == "5M COMPLETE"


def _validate_contract(market: str, result: dict, day_str: str) -> tuple[bool, str]:
    """Validate only adapter-output contracts; never recompute source-model math."""
    if not isinstance(result, dict):
        return False, "adapter returned no result dictionary"
    if str(result.get("status") or "").upper() != "5M COMPLETE":
        return False, str(result.get("reason") or result.get("status") or "adapter did not complete")
    if str(result.get("day") or "") != str(day_str):
        return False, f"adapter slate day {result.get('day')} does not match controller day {day_str}"

    sims = int(result.get("simulations") or 0)
    if sims <= 0:
        return False, "completed adapter reported zero simulations"

    if market in {"PRA", "POINTS"}:
        units = int(result.get("distributions") or 0)
        conv = int(result.get("converged") or 0)
        if units <= 0 or conv != units:
            return False, f"distribution convergence mismatch {conv}/{units}"

    elif market in {"REBOUNDS", "ASSISTS"}:
        players = int(result.get("players") or 0)
        conv = int(result.get("converged") or 0)
        trials = int(result.get("trials_per_player") or 0)
        if players <= 0 or conv != players:
            return False, f"player convergence mismatch {conv}/{players}"
        if trials != 5_000_000:
            return False, f"expected 5,000,000 trials/player; got {trials:,}"

    elif market == "SPREAD":
        games = int(result.get("games") or 0)
        covered = int(result.get("covered_games") or 0)
        rows = int(result.get("rows") or 0)
        conv = int(result.get("converged") or 0)
        trials = int(result.get("trials_per_game") or 0)
        batches = int(result.get("batches") or 0)
        if games <= 0 or covered != games:
            return False, f"game coverage mismatch {covered}/{games}"
        if rows <= 0 or conv != rows:
            return False, f"row convergence mismatch {conv}/{rows}"
        if trials != 5_000_000 or batches != 20:
            return False, f"Spread simulation contract mismatch: {trials:,} trials, {batches} batches"
        if str(result.get("market_to_distribution") or "0") != "0":
            return False, "sportsbook market influenced Spread distribution"

    elif market in {"MONEYLINE", "GAME TOTAL"}:
        games = int(result.get("games") or 0)
        covered = int(result.get("covered_games") or 0)
        rows = int(result.get("rows") or 0)
        conv = int(result.get("converged") or 0)
        trials = int(result.get("trials_per_game") or 0)
        batches = int(result.get("batches") or 0)
        market_inputs = int(result.get("sportsbook_sim_inputs") or 0)
        if games <= 0 or covered != games:
            return False, f"game coverage mismatch {covered}/{games}"
        if rows <= 0 or conv != rows:
            return False, f"row convergence mismatch {conv}/{rows}"
        if trials != 5_000_000 or batches != 20:
            return False, f"{market.title()} simulation contract mismatch: {trials:,} trials, {batches} batches"
        if market_inputs != 0:
            return False, f"sportsbook simulation inputs must remain 0; got {market_inputs}"

    return True, "PASS"


def _stage_units(market: str, result: dict) -> str:
    if market in {"PRA", "POINTS"}:
        return f"{int(result.get('distributions') or 0)} distributions"
    if market in {"REBOUNDS", "ASSISTS"}:
        return f"{int(result.get('players') or 0)} players"
    return f"{int(result.get('covered_games') or 0)}/{int(result.get('games') or 0)} games"


def _stage_convergence(market: str, result: dict) -> str:
    if market in {"PRA", "POINTS"}:
        return f"{int(result.get('converged') or 0)}/{int(result.get('distributions') or 0)}"
    if market in {"REBOUNDS", "ASSISTS"}:
        return f"{int(result.get('converged') or 0)}/{int(result.get('players') or 0)}"
    return f"{int(result.get('converged') or 0)}/{int(result.get('rows') or 0)}"


def _run_all_seven() -> dict:
    """Run the seven independently verified adapters sequentially and fail closed."""
    day_str = _today_str()
    started = datetime.now(_ET)

    stages = (
        ("PRA", "🧮", controller_base._run_pra_standard_5m, _PRA_RUN_KEY),
        ("POINTS", "🎯", controller_base._run_points_standard_5m, _POINTS_RUN_KEY),
        ("REBOUNDS", "🧱", rebounds_adapter._run_rebounds_standard_5m, _REBOUNDS_RUN_KEY),
        ("ASSISTS", "🧠", assists_adapter._run_assists_standard_5m, _ASSISTS_RUN_KEY),
        ("SPREAD", "🏀", spread_adapter._run_spread_standard_5m, _SPREAD_RUN_KEY),
        ("MONEYLINE", "💰", moneyline_adapter._run_moneyline_standard_5m, _MONEYLINE_RUN_KEY),
        ("GAME TOTAL", "📊", game_total_adapter._run_game_total_standard_5m, _GAME_TOTAL_RUN_KEY),
    )

    # Controller keys are cleared at the start so the master result can never be
    # assembled from mixed old/new adapter records. Native source persistence is
    # left under source ownership and each successful adapter refreshes it.
    for _market, _icon, _runner, key in stages:
        st.session_state.pop(key, None)

    master_bar = st.progress(0.0, text="Run All 7 • starting sequential execution…")
    master_status = st.empty()
    stage_rows = []
    completed = 0

    try:
        for idx, (market, icon, runner, key) in enumerate(stages, start=1):
            master_bar.progress(
                (idx - 1) / len(stages),
                text=f"Run All 7 • {idx}/7 • {market}",
            )
            master_status.info(
                f"{icon} Running {market} through its already-verified native adapter. "
                f"Completed before this stage: {completed}/7."
            )
            t0 = monotonic()
            try:
                result = runner()
            except Exception as exc:
                result = {
                    "status": "ERROR",
                    "day": day_str,
                    "reason": f"{type(exc).__name__}: {exc}",
                    "simulations": 0,
                }
            seconds = max(0.0, monotonic() - t0)
            result = dict(result or {})
            st.session_state[key] = result

            ok, reason = _validate_contract(market, result, day_str)
            stage_rows.append({
                "Order": idx,
                "Market": market,
                "State": "PASS" if ok else "STOP",
                "Units": _stage_units(market, result),
                "Simulations": int(result.get("simulations") or 0),
                "Converged": _stage_convergence(market, result),
                "Seconds": round(seconds, 1),
                "Reason": "" if ok else reason,
            })

            if not ok:
                return {
                    "status": "STOPPED",
                    "day": day_str,
                    "started_at_et": started.strftime("%Y-%m-%d %I:%M:%S %p ET"),
                    "finished_at_et": datetime.now(_ET).strftime("%Y-%m-%d %I:%M:%S %p ET"),
                    "completed_markets": completed,
                    "failed_market": market,
                    "reason": reason,
                    "simulations": sum(int(r.get("Simulations") or 0) for r in stage_rows),
                    "stages": stage_rows,
                }

            completed += 1
            master_bar.progress(idx / len(stages), text=f"Run All 7 • {idx}/7 PASS • {market}")

        return {
            "status": "7/7 COMPLETE",
            "day": day_str,
            "started_at_et": started.strftime("%Y-%m-%d %I:%M:%S %p ET"),
            "finished_at_et": datetime.now(_ET).strftime("%Y-%m-%d %I:%M:%S %p ET"),
            "completed_markets": 7,
            "failed_market": "",
            "reason": "",
            "simulations": sum(int(r.get("Simulations") or 0) for r in stage_rows),
            "stages": stage_rows,
        }
    finally:
        master_bar.empty()
        master_status.empty()


def _render_step10():
    st.markdown("## 🚀 Seven-Market Master Controller — Step 10")
    st.caption(
        "Master orchestration only. All seven execution adapters were independently verified in Steps 3-9. "
        "This button runs those existing adapters sequentially — PRA → Points → Rebounds → Assists → Spread → Moneyline → Game Total — "
        "and stops immediately if any native completion contract fails. No source-model math or Daily Picks ranking is changed."
    )

    records, all_pass, passed = controller_base._preflight_state()
    if not all_pass:
        if st.button("🔎 CHECK ALL 7 PREFLIGHTS", key="ks_step10_preflight_v31", use_container_width=True):
            st.session_state[_PREFLIGHT_KEY] = controller_base._run_preflight()
            st.rerun()
        st.warning(f"⚠️ RUN ALL 7 LOCKED • infrastructure preflight must be 7/7. Current: {passed}/7.")
    else:
        st.success(
            "✅ MASTER EXECUTION READY • all 7 adapter paths are independently verified and the current infrastructure preflight is 7/7."
        )

    master = st.session_state.get(_MASTER_RUN_KEY)
    master_complete = isinstance(master, dict) and str(master.get("status") or "") == "7/7 COMPLETE"

    a, b, c, d = st.columns(4)
    a.metric("Verified adapters", "7/7")
    b.metric("Master state", "COMPLETE" if master_complete else ("READY" if all_pass else "LOCKED"))
    c.metric("Completed markets", int((master or {}).get("completed_markets") or 0))
    d.metric("Master simulations", f"{int((master or {}).get('simulations') or 0):,}")

    if st.button(
        "🚀 RUN ALL 7 WNBA MARKETS",
        key="ks_daily_picks_run_all_7_v31",
        disabled=not all_pass,
        use_container_width=True,
        type="primary",
        help="Sequential fail-closed orchestration. Runs only the seven already-verified source adapters; no connector/ranking/backfill stage is added here.",
    ):
        # Mark an in-progress record before execution so stale prior COMPLETE state
        # can never survive a new master attempt.
        st.session_state[_MASTER_RUN_KEY] = {
            "status": "RUNNING",
            "day": _today_str(),
            "completed_markets": 0,
            "simulations": 0,
            "stages": [],
        }
        try:
            st.session_state[_MASTER_RUN_KEY] = _run_all_seven()
        except Exception as exc:
            st.session_state[_MASTER_RUN_KEY] = {
                "status": "ERROR",
                "day": _today_str(),
                "completed_markets": 0,
                "failed_market": "CONTROLLER",
                "reason": f"{type(exc).__name__}: {exc}",
                "simulations": 0,
                "stages": [],
            }
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
                + " did not satisfy its native completion contract. Later markets were not executed."
            )
            st.warning(str(master.get("reason") or "Inspect the stage audit below."))
        elif token == "ERROR":
            st.error("⛔ MASTER CONTROLLER ERROR • " + str(master.get("reason") or "unknown error"))

        stages = master.get("stages") or []
        if stages:
            frame = pd.DataFrame(stages)
            st.markdown("### 🧾 Run All 7 Sequential Audit")
            st.dataframe(frame, use_container_width=True, hide_index=True)

        x, y, z = st.columns(3)
        x.metric("Run slate", str(master.get("day") or "—"))
        y.metric("Markets passed", f"{int(master.get('completed_markets') or 0)}/7")
        z.metric("Total simulations", f"{int(master.get('simulations') or 0):,}")
        if master.get("started_at_et") or master.get("finished_at_et"):
            st.caption(
                f"Started {master.get('started_at_et') or '—'} • finished {master.get('finished_at_et') or '—'}"
            )

    st.markdown("### 🧩 Master Adapter Status")
    key_map = {
        "PRA": _PRA_RUN_KEY,
        "POINTS": _POINTS_RUN_KEY,
        "REBOUNDS": _REBOUNDS_RUN_KEY,
        "ASSISTS": _ASSISTS_RUN_KEY,
        "SPREAD": _SPREAD_RUN_KEY,
        "MONEYLINE": _MONEYLINE_RUN_KEY,
        "GAME TOTAL": _GAME_TOTAL_RUN_KEY,
    }
    rows_ui = [st.columns(4), st.columns(3)]
    for idx, item in enumerate(_MARKETS):
        market = item["market"]
        result = st.session_state.get(key_map[market])
        value = "✅ 5M COMPLETE" if _complete(result) else (
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
        "Step 10 contract • verified adapters 7/7 • fixed sequential order • fail closed on first non-PASS • current ET slate enforced • "
        "source model math changed 0 • source persistence contracts preserved • source simulations use their native counts/batches • "
        "connector writes 0 • backfills 0 • cross-market ranking changes 0 • forced picks 0"
    )
    st.markdown("---")


def render_wnba_daily_picks_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _render_step10()
    return v21.render_wnba_daily_picks_hub(
        section_header=section_header,
        status_info=status_info,
        team_logo=team_logo,
        h=h,
    )


__all__ = ["MODEL_VERSION", "render_wnba_daily_picks_hub"]
