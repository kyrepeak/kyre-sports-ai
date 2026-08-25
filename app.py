"""Kyre Sports AI — WNBA Live Games V6.6 full-width route repair.

This wrapper preserves the frozen Step-1 application checkpoint and the V6.6
structural Q4 calibration audit, but fixes the actual iPad layout bug at the
routing layer.

Root cause
----------
The historical Live Games route was invoked *inside* the WNBA market selectbox
wrapper. On tablet/desktop that selectbox is rendered inside the right navigation
column, so the entire Live Games page inherited that column's width. CSS on the
main Streamlit block could not escape the parent column, which is why iPad still
looked like a phone with a large empty area on the left.

Repair
------
- When Live Games is already selected, render a small dedicated WNBA navigation
  row first, exit the column context, and only then render ``wnba_live_hub_v66``.
- On the first selection of Live Games from the frozen shell, rerun immediately
  instead of rendering from inside the selectbox callback. The next run enters
  the dedicated full-width route.
- All non-Live WNBA/MLB/NFL routes remain owned by the exact frozen Step-1 app.
- Production Step 6 remains unchanged. V6.6 remains an audit only.
"""
from __future__ import annotations

import importlib
import subprocess
import sys
import urllib.request

import streamlit as st


FROZEN_LIVE_STEP1_COMMIT = "e091e92c7a1f03ba07c403506ef347c75f69d7de"
RAW_URL = (
    "https://raw.githubusercontent.com/kyrepeak/kyre-sports-ai/"
    f"{FROZEN_LIVE_STEP1_COMMIT}/app.py"
)

SPORTS = ["MLB", "WNBA", "NFL"]
WNBA_MARKETS = [
    "Points",
    "Rebounds",
    "Assists",
    "Rebounds + Assists",
    "PRA",
    "Spread",
    "Moneyline",
    "Game Total",
    "Live Games",
    "Daily Picks",
]


def _load_step1_app() -> str:
    try:
        return subprocess.check_output(
            ["git", "show", f"{FROZEN_LIVE_STEP1_COMMIT}:app.py"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        with urllib.request.urlopen(RAW_URL, timeout=15) as response:
            return response.read().decode("utf-8")


def _real_streamlit_method(name: str, fallback):
    main = getattr(st, "_main", None)
    candidate = getattr(main, name, None) if main is not None else None
    return candidate if callable(candidate) else fallback


_REAL_SELECTBOX = _real_streamlit_method("selectbox", st.selectbox)


def _clear_live_modules():
    for name in list(sys.modules):
        if name.startswith("wnba_live_"):
            sys.modules.pop(name, None)
    importlib.invalidate_caches()


def _render_live_full_width():
    """Render WNBA Live Games only after leaving all Streamlit nav columns."""
    # Restore the native selectbox in case a previous hot reload left a wrapper.
    st.selectbox = _REAL_SELECTBOX

    st.markdown(
        r'''<style>
        @media (min-width: 768px) {
          [data-testid="stMainBlockContainer"], .stMainBlockContainer, main .block-container {
            width: calc(100vw - 32px) !important;
            max-width: 1280px !important;
            margin-left: auto !important;
            margin-right: auto !important;
            padding-left: 16px !important;
            padding-right: 16px !important;
          }
        }
        </style>''',
        unsafe_allow_html=True,
    )

    nav1, nav2 = st.columns([1, 1], gap="small")
    with nav1:
        selected_sport = _REAL_SELECTBOX(
            "🏟️ Sport",
            SPORTS,
            key="ks_sport_touch",
        )
    with nav2:
        selected_market = _REAL_SELECTBOX(
            "🎯 WNBA Market",
            WNBA_MARKETS,
            key="ks_wnba_market_touch",
        )

    # IMPORTANT: route only after both `with st.columns(...)` blocks have ended.
    # This is the layout bug fix; the page is now a child of the main block, not
    # of the right navigation column.
    if str(selected_sport).upper() != "WNBA" or str(selected_market) != "Live Games":
        st.rerun()

    _clear_live_modules()
    import wnba_live_hub_v66 as live_v66

    live_v66.render_wnba_live_hub(None, None, None, None)
    st.stop()


# If Live Games was selected on the previous widget event, take the dedicated
# full-width path before replaying the frozen application shell.
if (
    str(st.session_state.get("ks_sport_touch") or "").upper() == "WNBA"
    and str(st.session_state.get("ks_wnba_market_touch") or "") == "Live Games"
):
    _render_live_full_width()


# Otherwise replay the exact frozen Step-1 app. We make two narrow source edits:
# (1) point its isolated Live route at V6.6, and
# (2) when Live Games is first selected, rerun instead of rendering inside the
#     selectbox's right-column context.
source = _load_step1_app()

import_anchor = "    import wnba_live_hub_v1 as wnba_live_v1"
import_replacement = "    import wnba_live_hub_v66 as wnba_live_v1"
if import_anchor not in source:
    raise RuntimeError("Frozen WNBA Live Step-1 route import not found.")
source = source.replace(import_anchor, import_replacement, 1)

route_anchor = '''    if is_wnba_market_widget and str(selected) == "Live Games":\n        _render_wnba_live_route()'''
route_replacement = '''    if is_wnba_market_widget and str(selected) == "Live Games":\n        st.rerun()'''
if route_anchor not in source:
    raise RuntimeError("Frozen WNBA Live in-column route hook not found.")
source = source.replace(route_anchor, route_replacement, 1)

compile(source, "<kyre_wnba_live_v66_full_width_preflight>", "exec")
exec(
    compile(source, "kyre_wnba_live_games_v66_full_width_route.py", "exec"),
    globals(),
    globals(),
)
