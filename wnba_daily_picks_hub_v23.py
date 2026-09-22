"""WNBA Daily Picks V23 — Step-2 seven-market read-only controller preflight.

Preserves the complete Daily Picks V21 seven-market production/verification surface.
Step 1's controller shell is now verified. Step 2 adds only an explicit read-only
infrastructure preflight: it confirms each current source route module and its
existing Daily Picks read-only connector contract are available before any source
execution adapter is wired.

The preflight does NOT import or execute source production modules, request data,
launch/restore Monte Carlo, refresh sportsbook/roster/injury data, write connector
or source state, backfill a result, change ranking, or publish a pick. The Run All 7
button remains intentionally disabled until Step 3 begins one-market-at-a-time
execution wiring.
"""
from __future__ import annotations

import importlib.util
import sys

import pandas as pd
import streamlit as st

import wnba_daily_picks_hub_v21 as v21

MODEL_VERSION = "WNBA DAILY PICKS V23 • MASTER CONTROLLER STEP 2 READ-ONLY PREFLIGHT"
_STATE_KEY = "ks_run_all_7_step2_preflight_v23"

_MARKETS = (
    {
        "market": "PRA", "icon": "🧮",
        "source": "wnba_pra_hub_v361",
        "connector": "wnba_daily_picks_pra_connector_v1",
        "route": "PRA V3.6.1",
    },
    {
        "market": "POINTS", "icon": "🎯",
        "source": "wnba_points_hub_v19845",
        "connector": "wnba_daily_picks_points_connector_v1",
        "route": "Points V1.9.8.4.5",
    },
    {
        "market": "REBOUNDS", "icon": "🧱",
        "source": "wnba_rebounds_hub_v29",
        "connector": "wnba_daily_picks_rebounds_connector_v1",
        "route": "Rebounds V2.9",
    },
    {
        "market": "ASSISTS", "icon": "🧠",
        "source": "wnba_assists_hub_v20",
        "connector": "wnba_daily_picks_assists_connector_v1",
        "route": "Assists V20",
    },
    {
        "market": "SPREAD", "icon": "🏀",
        "source": "wnba_spread_hub_v161",
        "connector": "wnba_daily_picks_spread_connector_v1",
        "route": "Spread V1.6.1",
    },
    {
        "market": "MONEYLINE", "icon": "💰",
        "source": "wnba_moneyline_hub_v15",
        "connector": "wnba_daily_picks_moneyline_connector_v1",
        "route": "Moneyline V1.5",
    },
    {
        "market": "GAME TOTAL", "icon": "📊",
        "source": "wnba_game_total_hub_v15",
        "connector": "wnba_daily_picks_game_total_connector_v1",
        "route": "Game Total V1.5",
    },
)


def _module_available(name: str) -> bool:
    """Check a top-level module without importing/executing it."""
    try:
        loaded = sys.modules.get(name)
        if loaded is not None and (getattr(loaded, "__spec__", None) is not None or getattr(loaded, "__file__", None)):
            return True
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


def _run_preflight() -> list[dict]:
    daily_contract = _module_available("wnba_daily_picks_hub_v21")
    records: list[dict] = []
    for item in _MARKETS:
        source_ok = _module_available(item["source"])
        connector_ok = _module_available(item["connector"])
        passed = bool(source_ok and connector_ok and daily_contract)
        records.append({
            "Market": item["market"],
            "Source route": item["route"],
            "Source module": item["source"],
            "Source available": "PASS" if source_ok else "MISSING",
            "Connector module": item["connector"],
            "Connector contract": "PASS" if connector_ok and daily_contract else "MISSING",
            "Execution adapter": "NOT WIRED — STEP 3",
            "Preflight": "PASS" if passed else "CHECK",
        })
    return records


def _render_controller_preflight() -> None:
    st.markdown("## 🚀 Seven-Market Master Controller — Step 2")
    st.caption(
        "Read-only infrastructure preflight. Step 1 is frozen/verified. This step checks that each current market route "
        "and its existing passive Daily Picks connector contract are present. Same-day market output is NOT required here, "
        "and no source model is executed."
    )

    if st.button(
        "🔎 CHECK ALL 7 PREFLIGHTS",
        key="ks_daily_picks_check_all_7_preflight_v23",
        use_container_width=True,
    ):
        st.session_state[_STATE_KEY] = _run_preflight()

    saved = st.session_state.get(_STATE_KEY)
    records = list(saved) if isinstance(saved, list) else []
    checked = bool(records)
    passed = sum(1 for r in records if str(r.get("Preflight")).upper() == "PASS") if checked else 0
    all_pass = bool(checked and passed == len(_MARKETS))

    state = "PREFLIGHT PASSED" if all_pass else ("PREFLIGHT CHECK" if checked else "PREFLIGHT READY")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Controller state", state)
    m2.metric("Preflight passed", f"{passed}/7" if checked else "0/7")
    m3.metric("Models launched", "0")
    m4.metric("New simulations", "0")

    st.button(
        "🚀 RUN ALL 7 WNBA MARKETS",
        key="ks_daily_picks_run_all_7_disabled_v23",
        disabled=True,
        use_container_width=True,
        help="Step 2 verifies infrastructure only. Execution adapters are wired one market at a time beginning in Step 3.",
    )

    if not checked:
        st.info(
            "ℹ️ STEP 2 READY • press CHECK ALL 7 PREFLIGHTS. This check does not run any WNBA model or simulation."
        )
    elif all_pass:
        st.success(
            "✅ STEP 2 PREFLIGHT PASSED • all 7 current source routes and all 7 existing read-only connector contracts are available. "
            "No models were launched. Safe to begin Step 3 execution wiring one market at a time."
        )
    else:
        failed = [str(r.get("Market")) for r in records if str(r.get("Preflight")).upper() != "PASS"]
        st.warning(
            "⚠️ STEP 2 PREFLIGHT CHECK • do not wire execution yet. Missing/check: " + ", ".join(failed)
        )

    st.markdown("### 🧩 Controller Market Status")
    status_map = {str(r.get("Market")): str(r.get("Preflight")) for r in records}
    rows = [st.columns(4), st.columns(3)]
    for idx, item in enumerate(_MARKETS):
        row = rows[0] if idx < 4 else rows[1]
        col = row[idx] if idx < 4 else row[idx - 4]
        with col:
            st.markdown(f"**{item['icon']} {item['market']}**")
            token = status_map.get(item["market"])
            if token == "PASS":
                value = "✅ PREFLIGHT PASS"
            elif token:
                value = "⚠️ CHECK"
            else:
                value = "WAITING"
            st.metric("Controller status", value)

    if checked:
        st.markdown("### 🔎 Step-2 Preflight Audit")
        st.dataframe(pd.DataFrame(records), use_container_width=True, hide_index=True)
        st.caption(
            "Source available/connector PASS means the deployed code path exists. It does not claim the source has run today. "
            "Execution adapters intentionally remain NOT WIRED until Step 3."
        )

    st.caption(
        "Step 2 contract • Step 1 verified • source models changed 0 • source models executed 0 • "
        "network requests 0 • simulations 0 • connector writes 0 • backfills 0 • ranking changes 0"
    )
    st.markdown("---")


def render_wnba_daily_picks_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _render_controller_preflight()
    return v21.render_wnba_daily_picks_hub(
        section_header=section_header,
        status_info=status_info,
        team_logo=team_logo,
        h=h,
    )


__all__ = ["MODEL_VERSION", "render_wnba_daily_picks_hub"]
