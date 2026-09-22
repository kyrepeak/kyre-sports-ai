"""WNBA Daily Picks V25 — Step-4 Points execution adapter.

Preserves the complete Daily Picks V21 seven-market production/verification surface,
verified Step-1 controller shell, verified Step-2 7/7 infrastructure preflight, and
verified Step-3 PRA standard-5M adapter. Step 4 wires exactly one additional source
execution adapter: Points V1.9.8.4.5 standard 5M.

The Points adapter calls the existing production engine and its native readiness,
player-quarantine, empirical-history, position-matchup, Monte Carlo and persistence
contracts. It does not change projection, market, grading, simulation-count,
convergence, roster, history, sanity, position, or qualification math. The targeted
Points 10M finalist pass remains intentionally NOT WIRED in this step. The master
Run All 7 button remains disabled until each market adapter is independently verified.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import importlib.util
import sys

import pandas as pd
import streamlit as st

import wnba_daily_picks_hub_v21 as v21
import wnba_points_hub_v19845 as points_hub
import wnba_pra_hub_v351 as pra_v351
import wnba_pra_hub_v35 as pra_v35
import wnba_pra_integrity_v33 as pra_integrity
import wnba_pra_matchup_v36 as pra_matchup
import wnba_pra_monte_carlo_v311 as pra_monte
import wnba_pra_persist_v33 as pra_persist
import wnba_pra_variance_v353 as pra_variance
import wnba_rotowire_status_v34 as pra_rotowire

MODEL_VERSION = "WNBA DAILY PICKS V25 • MASTER CONTROLLER STEP 4 • POINTS 5M ADAPTER"
ET = ZoneInfo("America/New_York")

_PREFLIGHT_KEY = "ks_run_all_7_step2_preflight_v23"
_PRA_RUN_KEY = "ks_run_all_7_step3_pra_v24"
_POINTS_RUN_KEY = "ks_run_all_7_step4_points_v25"

_MARKETS = (
    {"market": "PRA", "icon": "🧮", "source": "wnba_pra_hub_v361", "connector": "wnba_daily_picks_pra_connector_v1", "route": "PRA V3.6.1"},
    {"market": "POINTS", "icon": "🎯", "source": "wnba_points_hub_v19845", "connector": "wnba_daily_picks_points_connector_v1", "route": "Points V1.9.8.4.5"},
    {"market": "REBOUNDS", "icon": "🧱", "source": "wnba_rebounds_hub_v29", "connector": "wnba_daily_picks_rebounds_connector_v1", "route": "Rebounds V2.9"},
    {"market": "ASSISTS", "icon": "🧠", "source": "wnba_assists_hub_v20", "connector": "wnba_daily_picks_assists_connector_v1", "route": "Assists V20"},
    {"market": "SPREAD", "icon": "🏀", "source": "wnba_spread_hub_v161", "connector": "wnba_daily_picks_spread_connector_v1", "route": "Spread V1.6.1"},
    {"market": "MONEYLINE", "icon": "💰", "source": "wnba_moneyline_hub_v15", "connector": "wnba_daily_picks_moneyline_connector_v1", "route": "Moneyline V1.5"},
    {"market": "GAME TOTAL", "icon": "📊", "source": "wnba_game_total_hub_v15", "connector": "wnba_daily_picks_game_total_connector_v1", "route": "Game Total V1.5"},
)


def _module_available(name: str) -> bool:
    try:
        loaded = sys.modules.get(name)
        if loaded is not None and (getattr(loaded, "__spec__", None) is not None or getattr(loaded, "__file__", None)):
            return True
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


def _run_preflight() -> list[dict]:
    daily_ok = _module_available("wnba_daily_picks_hub_v21")
    out = []
    for item in _MARKETS:
        source_ok = _module_available(item["source"])
        connector_ok = _module_available(item["connector"])
        passed = bool(source_ok and connector_ok and daily_ok)
        out.append({
            "Market": item["market"],
            "Source route": item["route"],
            "Source available": "PASS" if source_ok else "MISSING",
            "Connector contract": "PASS" if connector_ok and daily_ok else "MISSING",
            "Preflight": "PASS" if passed else "CHECK",
        })
    return out


def _preflight_state():
    saved = st.session_state.get(_PREFLIGHT_KEY)
    rows = list(saved) if isinstance(saved, list) else []
    passed = sum(1 for r in rows if str(r.get("Preflight")).upper() == "PASS")
    return rows, bool(rows and passed == len(_MARKETS)), passed


def _today_et():
    return datetime.now(ET).date()


# ---------------------------------------------------------------------------
# Frozen Step-3 PRA adapter (kept byte-for-byte in behavior, not auto-run here)
# ---------------------------------------------------------------------------

def _install_pra_runtime_contracts():
    pra_rotowire.install()
    pra_variance.install()
    pra_matchup.install()
    pra_integrity.install_runtime_guards()
    pra_v351._install_strict_final_ready()


def _run_pra_standard_5m():
    day = _today_et()
    st.session_state["wnba_pra_v2_date"] = day
    _install_pra_runtime_contracts()

    state = pra_integrity.current_basketball_state(day)
    if not bool((state or {}).get("safe")):
        return {
            "status": "BLOCKED", "day": pd.to_datetime(day).strftime("%Y-%m-%d"),
            "reason": "PRA availability/injury basketball-state integrity is not SAFE.",
            "rows": 0, "distributions": 0, "simulations": 0,
        }

    pra_integrity.invalidate_stale_session(day, state)
    bar = st.progress(0.0, text="Controller: running PRA standard 5M…")
    try:
        rows, meta = pra_monte.run_standard(day, progress=bar)
    finally:
        bar.empty()

    if not isinstance(rows, pd.DataFrame) or rows.empty:
        return {
            "status": "BLOCKED", "day": pd.to_datetime(day).strftime("%Y-%m-%d"),
            "reason": "PRA standard engine returned no exact simulatable market rows.",
            "rows": 0, "distributions": 0, "simulations": 0,
        }

    native_key = pra_persist.std_key(day)
    st.session_state[native_key] = {"rows": rows, "meta": dict(meta or {}), "ran_at": pd.Timestamp.now()}
    current_state = pra_integrity.current_basketball_state(day)
    pra_integrity.attach_fingerprint(day, current_state)
    try:
        pra_v35._stamp_game_fingerprints(day, current_state)
    except Exception:
        pass
    pra_persist.persist_if_ready(day, current_state)

    key_cols = [c for c in ("game_id", "player_key", "line") if c in rows.columns]
    unique = rows.drop_duplicates(key_cols) if len(key_cols) == 3 else rows
    sims = pd.to_numeric(unique.get("sims"), errors="coerce").fillna(0) if "sims" in unique.columns else pd.Series(dtype=float)
    converged = unique.get("converged", pd.Series(False, index=unique.index)).fillna(False).astype(bool)
    complete = bool(len(unique) > 0 and (sims >= 5_000_000).all() and converged.all())

    return {
        "status": "5M COMPLETE" if complete else "CHECK",
        "day": pd.to_datetime(day).strftime("%Y-%m-%d"),
        "reason": "" if complete else "One or more PRA distributions failed the existing 5M/convergence contract.",
        "rows": int(len(rows)), "distributions": int(len(unique)),
        "simulations": int(sims.sum()) if len(sims) else 0,
        "converged": int(converged.sum()),
        "qualified": int(rows.get("model_qualified", pd.Series(False, index=rows.index)).fillna(False).astype(bool).sum()),
        "final_ready": int(rows.get("final_ready", pd.Series(False, index=rows.index)).fillna(False).astype(bool).sum()),
        "native_key": native_key,
    }


# ---------------------------------------------------------------------------
# Step-4 Points adapter — exact native V1.9.8.4.5 readiness + 5M path
# ---------------------------------------------------------------------------

def _install_points_runtime_contracts():
    """Install the same non-UI Points patches as the live V1.9.8.4.5 route."""
    # Live V1.9.8.4.5 render order is: quarantine -> explainable sanity -> unified
    # readiness. Reproduce that order without invoking any UI renderer.
    points_hub._install()
    points_hub.prior.prior._install()
    points_hub.prior._install_unified()


def _points_readiness(day_str: str) -> dict:
    _install_points_runtime_contracts()
    points = points_hub.points
    try:
        _pool, pdiag = points.corrected_player_pool(day_str)
        info = points_hub.prior._readiness_snapshot_unified(day_str, pdiag)
        return dict(info or {})
    except Exception as exc:
        return {"ready": False, "error": f"{type(exc).__name__}: {exc}"}


def _run_points_standard_5m():
    day = _today_et()
    day_str = pd.to_datetime(day).strftime("%Y-%m-%d")
    st.session_state["wnba_points_date"] = day_str
    st.session_state["wnba_points_date_control"] = day

    readiness = _points_readiness(day_str)
    if not bool(readiness.get("ready")):
        history = readiness.get("history_gate") or {}
        roster = readiness.get("roster_gate") or {}
        return {
            "status": "BLOCKED",
            "day": day_str,
            "reason": str(readiness.get("error") or "Points native production readiness is not READY."),
            "active_games": int(readiness.get("active_games") or 0),
            "eligible_pairs": int(readiness.get("eligible_pairs") or 0),
            "history_missing": int(history.get("missing") or 0),
            "sanity_holds": int(history.get("sanity_count") or 0),
            "roster_state": str(roster.get("state") or "CHECK"),
            "rows": 0, "distributions": 0, "simulations": 0, "converged": 0,
        }

    points = points_hub.points
    bar = st.progress(0.0, text="Controller: running Points standard 5M…")
    try:
        rows, meta = points.run_standard(day_str, bar)
    finally:
        bar.empty()

    if not isinstance(rows, pd.DataFrame) or rows.empty:
        return {
            "status": "BLOCKED", "day": day_str,
            "reason": "Points standard engine returned no exact simulatable market rows.",
            "rows": 0, "distributions": 0, "simulations": 0, "converged": 0,
        }

    # Use the source module's existing persistence contract exactly as the live
    # Points production button does after run_standard().
    points.persist_if_ready(day_str)

    key_cols = [c for c in ("game_id", "player_key", "line") if c in rows.columns]
    unique = rows.drop_duplicates(key_cols) if len(key_cols) == 3 else rows
    sims = pd.to_numeric(unique.get("sims"), errors="coerce").fillna(0) if "sims" in unique.columns else pd.Series(dtype=float)
    converged = unique.get("converged", pd.Series(False, index=unique.index)).fillna(False).astype(bool)
    complete = bool(len(unique) > 0 and (sims >= 5_000_000).all() and converged.all())

    return {
        "status": "5M COMPLETE" if complete else "CHECK",
        "day": day_str,
        "reason": "" if complete else "One or more Points distributions failed the existing 5M/convergence contract.",
        "rows": int(len(rows)),
        "distributions": int(len(unique)),
        "simulations": int(sims.sum()) if len(sims) else 0,
        "converged": int(converged.sum()),
        "qualified": int(rows.get("model_qualified", pd.Series(False, index=rows.index)).fillna(False).astype(bool).sum()),
        "final_ready": int(rows.get("final_ready", pd.Series(False, index=rows.index)).fillna(False).astype(bool).sum()),
        "active_games": int(readiness.get("active_games") or 0),
        "eligible_pairs": int(readiness.get("eligible_pairs") or 0),
        "native_key": points.std_key(day_str),
        "meta_units": int((meta or {}).get("unique_units") or 0),
    }


def _render_controller_step4():
    st.markdown("## 🚀 Seven-Market Master Controller — Step 4")
    st.caption(
        "Second execution adapter only: Points V1.9.8.4.5 standard 5M. Step 1 shell, Step 2 preflight and the verified Step-3 PRA adapter are frozen. "
        "Rebounds, Assists, Spread, Moneyline and Game Total remain unwired. Points source math is not duplicated or changed."
    )

    records, all_pass, passed = _preflight_state()
    if not all_pass:
        if st.button("🔎 CHECK ALL 7 PREFLIGHTS", key="ks_step4_recheck_preflight_v25", use_container_width=True):
            st.session_state[_PREFLIGHT_KEY] = _run_preflight()
            st.rerun()
        st.warning(f"⚠️ STEP 4 LOCKED • Step-2 infrastructure preflight must be 7/7 first. Current: {passed}/7.")
    else:
        st.success("✅ STEP 2 FROZEN • 7/7 source routes + connector contracts passed. Points execution adapter may be tested.")

    pra_run = st.session_state.get(_PRA_RUN_KEY)
    points_run = st.session_state.get(_POINTS_RUN_KEY)
    pra_complete = str((pra_run or {}).get("status") or "") == "5M COMPLETE"
    points_status = str((points_run or {}).get("status") or "NOT RUN")
    points_complete = points_status == "5M COMPLETE"
    launched = int(isinstance(pra_run, dict)) + int(isinstance(points_run, dict))
    sims_total = int((pra_run or {}).get("simulations") or 0) + int((points_run or {}).get("simulations") or 0)

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Controller state", "POINTS ADAPTER VERIFIED" if points_complete else ("POINTS ADAPTER READY" if all_pass else "STEP 2 REQUIRED"))
    m2.metric("Execution adapters", "2/7")
    m3.metric("Models launched this session", launched)
    m4.metric("New simulations this session", f"{sims_total:,}")

    st.button(
        "🚀 RUN ALL 7 WNBA MARKETS",
        key="ks_daily_picks_run_all_7_disabled_v25",
        disabled=True,
        use_container_width=True,
        help="Master execution stays locked until all seven adapters are independently verified.",
    )

    if st.button(
        "🎯 RUN POINTS 5,000,000 THROUGH CONTROLLER",
        key="ks_step4_run_points_5m_v25",
        disabled=not all_pass,
        use_container_width=True,
        help="Runs the existing Points V1.9.8.4.5 standard Monte Carlo path only. The selective 10M finalist pass is not wired in Step 4.",
    ):
        try:
            with st.spinner("Points controller adapter is using the existing production engine…"):
                st.session_state[_POINTS_RUN_KEY] = _run_points_standard_5m()
        except Exception as exc:
            st.session_state[_POINTS_RUN_KEY] = {
                "status": "ERROR",
                "day": pd.to_datetime(_today_et()).strftime("%Y-%m-%d"),
                "reason": f"{type(exc).__name__}: {exc}",
                "rows": 0, "distributions": 0, "simulations": 0, "converged": 0,
            }
        st.rerun()

    points_run = st.session_state.get(_POINTS_RUN_KEY)
    if isinstance(points_run, dict):
        token = str(points_run.get("status") or "CHECK")
        if token == "5M COMPLETE":
            st.success(
                "✅ POINTS CONTROLLER ADAPTER PASSED • native Points standard 5M completed through the controller and was stored "
                "under the existing source persistence contract. Quarantine/readiness/projection/grading rules were unchanged."
            )
        elif token == "BLOCKED":
            st.warning("⚠️ POINTS CONTROLLER BLOCKED • " + str(points_run.get("reason") or "source readiness gate did not pass"))
        else:
            st.error("⛔ POINTS CONTROLLER CHECK • " + str(points_run.get("reason") or token))

        a, b, c, d = st.columns(4)
        a.metric("Points day", str(points_run.get("day") or "—"))
        b.metric("Unique distributions", int(points_run.get("distributions") or 0))
        c.metric("Completed simulations", f"{int(points_run.get('simulations') or 0):,}")
        d.metric("Converged", f"{int(points_run.get('converged') or 0)}/{int(points_run.get('distributions') or 0)}")

        if token == "BLOCKED":
            e, f, g, h = st.columns(4)
            e.metric("Eligible games", int(points_run.get("active_games") or 0))
            f.metric("Exact eligible pairs", int(points_run.get("eligible_pairs") or 0))
            g.metric("History missing", int(points_run.get("history_missing") or 0))
            h.metric("Sanity holds", int(points_run.get("sanity_holds") or 0))

        st.caption(
            "Step 4 intentionally stops after the standard Points 5M. The source-owned selective 10M finalist pass remains unwired until this adapter is independently verified."
        )

    st.markdown("### 🧩 Controller Market Status")
    statuses = []
    for item in _MARKETS:
        market = item["market"]
        if market == "PRA":
            value = "✅ 5M COMPLETE" if pra_complete else "✅ ADAPTER VERIFIED • STEP 3"
        elif market == "POINTS":
            if points_complete:
                value = "✅ 5M COMPLETE"
            elif points_run:
                value = "⚠️ " + str(points_run.get("status") or "CHECK")
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
        "Step 4 contract • adapters wired 2/7 • PRA adapter frozen/verified • Points source math changed 0 • other source models executed 0 • "
        "Points standard simulation count preserved at 5,000,000/distribution • Points 10M auto-run 0 • connector writes 0 • ranking changes 0"
    )
    st.markdown("---")


def render_wnba_daily_picks_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _render_controller_step4()
    return v21.render_wnba_daily_picks_hub(
        section_header=section_header,
        status_info=status_info,
        team_logo=team_logo,
        h=h,
    )


__all__ = ["MODEL_VERSION", "render_wnba_daily_picks_hub"]
