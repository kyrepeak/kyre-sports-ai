"""WNBA Daily Picks V22 — Step-1 seven-market master-controller shell.

This wrapper preserves Daily Picks V21 exactly and adds only a passive controller
shell above it. The controller button is intentionally disabled in Step 1 and does
not invoke, rerun, refresh, mutate, or backfill any source market. No simulations,
network requests, source writes, connector writes, or ranking changes occur here.
"""
from __future__ import annotations

import streamlit as st

import wnba_daily_picks_hub_v21 as v21

MODEL_VERSION = "WNBA DAILY PICKS V22 • MASTER CONTROLLER STEP 1 SHELL"
_MARKETS = (
    ("PRA", "🧮"),
    ("POINTS", "🎯"),
    ("REBOUNDS", "🧱"),
    ("ASSISTS", "🧠"),
    ("SPREAD", "🏀"),
    ("MONEYLINE", "💰"),
    ("GAME TOTAL", "📊"),
)


def _render_controller_shell() -> None:
    st.markdown("## 🚀 Seven-Market Master Controller — Step 1")
    st.caption(
        "Controller shell only. The seven production models remain independent and frozen. "
        "This step does not run a model, request data, launch simulations, alter a connector, "
        "or publish a pick."
    )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Controller state", "SHELL ONLY")
    m2.metric("Controller-wired markets", "0/7")
    m3.metric("Models launched", "0")
    m4.metric("New simulations", "0")

    st.button(
        "🚀 RUN ALL 7 WNBA MARKETS",
        key="ks_daily_picks_run_all_7_shell_v22",
        disabled=True,
        use_container_width=True,
        help="Step 1 is display-only. The button will stay disabled until the controller preflight is built and verified.",
    )
    st.info(
        "ℹ️ STEP 1 CONTROLLER SHELL ACTIVE • the Run All 7 button is intentionally disabled. "
        "Next we will add read-only preflight checks before wiring any market execution."
    )

    st.markdown("### 🧩 Controller Market Status")
    rows = [st.columns(4), st.columns(3)]
    for idx, (market, icon) in enumerate(_MARKETS):
        row = rows[0] if idx < 4 else rows[1]
        col = row[idx] if idx < 4 else row[idx - 4]
        with col:
            st.markdown(f"**{icon} {market}**")
            st.metric("Controller status", "WAITING")

    st.caption(
        "Step 1 contract • source models changed 0 • source runs 0 • network requests 0 • "
        "simulations 0 • connector writes 0 • Daily Picks ranking changes 0"
    )
    st.markdown("---")


def render_wnba_daily_picks_hub(section_header=None, status_info=None, team_logo=None, h=None):
    _render_controller_shell()
    return v21.render_wnba_daily_picks_hub(
        section_header=section_header,
        status_info=status_info,
        team_logo=team_logo,
        h=h,
    )


__all__ = ["MODEL_VERSION", "render_wnba_daily_picks_hub"]
