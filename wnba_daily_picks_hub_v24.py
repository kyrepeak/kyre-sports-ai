"""WNBA Daily Picks V24 — Step-3 PRA execution adapter.

Preserves the complete Daily Picks V21 seven-market production/verification surface
and the verified V23 infrastructure preflight. Step 3 wires exactly one source
execution adapter: PRA V3.6.1 standard 5M.

The adapter calls the existing PRA production engine and persistence contracts.
It does not change any projection, market, grading, simulation-count, convergence,
injury/availability, lineup, or qualification math. The 10M finalist pass remains
intentionally NOT WIRED in this step. The master Run All 7 button remains disabled
until each market adapter is independently verified.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import importlib.util
import sys

import pandas as pd
import streamlit as st

import wnba_daily_picks_hub_v21 as v21
import wnba_pra_hub_v351 as pra_v351
import wnba_pra_hub_v35 as pra_v35
import wnba_pra_integrity_v33 as pra_integrity
import wnba_pra_matchup_v36 as pra_matchup
import wnba_pra_monte_carlo_v311 as pra_monte
import wnba_pra_persist_v33 as pra_persist
import wnba_pra_variance_v353 as pra_variance
import wnba_rotowire_status_v34 as pra_rotowire

MODEL_VERSION = "WNBA DAILY PICKS V24 • MASTER CONTROLLER STEP 3 • PRA 5M ADAPTER"
ET = ZoneInfo("America/New_York")

_PREFLIGHT_KEY = "ks_run_all_7_step2_preflight_v23"
_PRA_RUN_KEY = "ks_run_all_7_step3_pra_v24"

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


def _install_pra_runtime_contracts():
    """Install the same non-UI PRA runtime patches used by the live V3.6.1 route."""
    pra_rotowire.install()
    pra_variance.install()
    pra_matchup.install()
    pra_integrity.install_runtime_guards()
    pra_v351._install_strict_final_ready()


def _run_pra_standard_5m():
    """Execute the existing PRA standard 5M engine and store it in its native contract."""
    day = _today_et()
    st.session_state["wnba_pra_v2_date"] = day
    _install_pra_runtime_contracts()

    state = pra_integrity.current_basketball_state(day)
    if not bool((state or {}).get("safe")):
        return {
            "status": "BLOCKED",
            "day": pd.to_datetime(day).strftime("%Y-%m-%d"),
            "reason": "PRA availability/injury basketball-state integrity is not SAFE.",
            "rows": 0,
            "distributions": 0,
            "simulations": 0,
        }

    pra_integrity.invalidate_stale_session(day, state)

    bar = st.progress(0.0, text="Controller: running PRA standard 5M…")
    try:
        rows, meta = pra_monte.run_standard(day, progress=bar)
    finally:
        bar.empty()

    if not isinstance(rows, pd.DataFrame) or rows.empty:
        return {
            "status": "BLOCKED",
            "day": pd.to_datetime(day).strftime("%Y-%m-%d"),
            "reason": "PRA standard engine returned no exact simulatable market rows.",
            "rows": 0,
            "distributions": 0,
            "simulations": 0,
        }

    native_key = pra_persist.std_key(day)
    st.session_state[native_key] = {
        "rows": rows,
        "meta": dict(meta or {}),
        "ran_at": pd.Timestamp.now(),
    }

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
        "rows": int(len(rows)),
        "distributions": int(len(unique)),
        "simulations": int(sims.sum()) if len(sims) else 0,
        "converged": int(converged.sum()),
        "qualified": int(rows.get("model_qualified", pd.Series(False, index=rows.index)).fillna(False).astype(bool).sum()),
        "final_ready": int(rows.get("final_ready", pd.Series(False, index=rows.index)).fillna(False).astype(bool).sum()),
        "native_key": native_key,
    }


def _render_controller_step3():
    st.markdown("## 🚀 Seven-Market Master Controller — Step 3")
    st.caption(
        "First execution adapter only: PRA V3.6.1 standard 5M. Step 1 shell and Step 2 preflight are frozen. "
        "The other six market adapters remain unwired. PRA projection/grading/simulation math is not duplicated or changed."
    )

    records, all_pass, passed = _preflight_state()
    if not all_pass:
        if st.button("🔎 CHECK ALL 7 PREFLIGHTS", key="ks_step3_recheck_preflight_v24", use_container_width=True):
            st.session_state[_PREFLIGHT_KEY] = _run_preflight()
            st.rerun()
        st.warning(f"⚠️ STEP 3 LOCKED • Step-2 infrastructure preflight must be 7/7 first. Current: {passed}/7.")
    else:
        st.success("✅ STEP 2 FROZEN • 7/7 source routes + connector contracts passed. PRA execution adapter may be tested.")

    run = st.session_state.get(_PRA_RUN_KEY)
    status = str((run or {}).get("status") or "NOT RUN")
    completed = status == "5M COMPLETE"

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Controller state", "PRA ADAPTER VERIFIED" if completed else ("PRA ADAPTER READY" if all_pass else "STEP 2 REQUIRED"))
    m2.metric("Execution adapters", "1/7")
    m3.metric("Models launched", "1" if run else "0")
    m4.metric("New simulations", f"{int((run or {}).get('simulations') or 0):,}")

    st.button(
        "🚀 RUN ALL 7 WNBA MARKETS",
        key="ks_daily_picks_run_all_7_disabled_v24",
        disabled=True,
        use_container_width=True,
        help="Master execution stays locked until all seven adapters are independently verified.",
    )

    if st.button(
        "🧮 RUN PRA 5,000,000 THROUGH CONTROLLER",
        key="ks_step3_run_pra_5m_v24",
        disabled=not all_pass,
        use_container_width=True,
        help="Runs the existing PRA V3.6.1 standard Monte Carlo path only. Targeted 10M finalist execution is not wired in Step 3.",
    ):
        try:
            with st.spinner("PRA controller adapter is using the existing production engine…"):
                st.session_state[_PRA_RUN_KEY] = _run_pra_standard_5m()
        except Exception as exc:
            st.session_state[_PRA_RUN_KEY] = {
                "status": "ERROR",
                "day": pd.to_datetime(_today_et()).strftime("%Y-%m-%d"),
                "reason": f"{type(exc).__name__}: {exc}",
                "rows": 0,
                "distributions": 0,
                "simulations": 0,
            }
        st.rerun()

    run = st.session_state.get(_PRA_RUN_KEY)
    if isinstance(run, dict):
        token = str(run.get("status") or "CHECK")
        if token == "5M COMPLETE":
            st.success(
                "✅ PRA CONTROLLER ADAPTER PASSED • native PRA standard 5M completed through the controller and was stored "
                "under the existing fingerprint-safe source contract. No projection or grading rule was changed."
            )
        elif token == "BLOCKED":
            st.warning("⚠️ PRA CONTROLLER BLOCKED • " + str(run.get("reason") or "source safety gate did not pass"))
        else:
            st.error("⛔ PRA CONTROLLER CHECK • " + str(run.get("reason") or token))

        a, b, c, d = st.columns(4)
        a.metric("PRA day", str(run.get("day") or "—"))
        b.metric("Unique distributions", int(run.get("distributions") or 0))
        c.metric("Completed simulations", f"{int(run.get('simulations') or 0):,}")
        d.metric("Converged", f"{int(run.get('converged') or 0)}/{int(run.get('distributions') or 0)}")

        st.caption(
            "Step 3 intentionally stops after the standard PRA 5M. Strict 10M finalist/lineup finalization remains owned by the "
            "existing PRA source contract and will be wired only after this adapter is verified."
        )

    st.markdown("### 🧩 Controller Market Status")
    statuses = []
    for item in _MARKETS:
        if item["market"] == "PRA":
            if completed:
                value = "✅ 5M COMPLETE"
            elif run:
                value = "⚠️ " + str(run.get("status") or "CHECK")
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
        "Step 3 contract • adapters wired 1/7 • PRA source math changed 0 • other source models executed 0 • "
        "PRA standard simulation count preserved at 5,000,000/distribution • 10M auto-run 0 • connector writes 0 • ranking changes 0"
    )
    st.markdown("---")


def render_wnba_daily_picks_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _render_controller_step3()
    return v21.render_wnba_daily_picks_hub(
        section_header=section_header,
        status_info=status_info,
        team_logo=team_logo,
        h=h,
    )


__all__ = ["MODEL_VERSION", "render_wnba_daily_picks_hub"]
