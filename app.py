"""Kyre Sports AI — WNBA Live Games V6.6.1 memory-safe full-width route.

This wrapper preserves the frozen Step-1 application checkpoint and the V6.6
structural Q4 audit, while fixing two route-level problems:

1) iPad/tablet width: Live Games must render after leaving the WNBA navigation
   columns so the page owns the full Streamlit main canvas.
2) memory growth: the previous route deleted and re-imported every ``wnba_live_*``
   module on each rerun. Those modules contain Streamlit caches; repeatedly
   recreating them can leave duplicate cache/function objects alive and drive the
   Community Cloud process over its memory limit. V6.6.1 uses normal Python
   module reuse instead.

No production model math is changed here.
"""
from __future__ import annotations

import gc
import subprocess
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


def _purge_rejected_calibration_state_once():
    """Drop obsolete heavy audit payloads from this browser session once.

    The rejected Step 6.4/6.5 payloads can contain nested replay/projection data.
    They are no longer rendered by V6.6, so retaining them wastes RAM. This does
    not touch production outputs, the verified Step-6 model, or navigation state.
    """
    marker = "__wnba_live_v661_memory_migration_done"
    if st.session_state.get(marker):
        return

    prefixes = (
        "wnba_step64_pbp_calibration_",
        "wnba_step65_",
        "wnba_step651_",
        "wnba_step66_q4_shrinkage_",
    )
    for key in list(st.session_state.keys()):
        text = str(key)
        if text.startswith(prefixes):
            st.session_state.pop(key, None)

    st.session_state[marker] = True
    gc.collect()


def _live_route_css():
    st.markdown(
        r'''<style>
        /* The Live Games page is now a direct child of the main Streamlit block.
           These rules make tablet/desktop use the real viewport instead of the
           narrow default content column. */
        @media (min-width: 768px) {
          [data-testid="stAppViewContainer"],
          [data-testid="stMain"],
          section.main {
            width: 100% !important;
            max-width: none !important;
          }
          [data-testid="stMainBlockContainer"],
          .stMainBlockContainer,
          main .block-container,
          section.main > div.block-container {
            width: calc(100vw - 32px) !important;
            max-width: 1320px !important;
            margin-left: auto !important;
            margin-right: auto !important;
            padding-left: 16px !important;
            padding-right: 16px !important;
          }
          [data-testid="stMainBlockContainer"] > div,
          .stMainBlockContainer > div,
          main .block-container > div {
            width: 100% !important;
            max-width: none !important;
          }
        }
        @media (min-width: 768px) and (max-width: 1100px) {
          [data-testid="stMainBlockContainer"],
          .stMainBlockContainer,
          main .block-container,
          section.main > div.block-container {
            width: calc(100vw - 24px) !important;
            max-width: none !important;
            padding-left: 12px !important;
            padding-right: 12px !important;
          }
        }
        </style>''',
        unsafe_allow_html=True,
    )


def _render_live_full_width():
    """Render WNBA Live Games outside every navigation column."""
    st.selectbox = _REAL_SELECTBOX
    _purge_rejected_calibration_state_once()
    _live_route_css()

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

    # Both column contexts are closed before the Live Games page is rendered.
    if str(selected_sport).upper() != "WNBA" or str(selected_market) != "Live Games":
        st.rerun()

    # IMPORTANT: normal import reuse only. Do NOT delete/re-import the live module
    # tree on every Streamlit rerun; that was the memory-growth bug.
    import wnba_live_hub_v66 as live_v66

    live_v66.render_wnba_live_hub(None, None, None, None)
    st.stop()


# If Live Games was selected on the previous widget event, take the dedicated
# full-width route before replaying the frozen application shell.
if (
    str(st.session_state.get("ks_sport_touch") or "").upper() == "WNBA"
    and str(st.session_state.get("ks_wnba_market_touch") or "") == "Live Games"
):
    _render_live_full_width()


# Otherwise replay the exact frozen Step-1 app. The only source edits are:
# (1) point the isolated Live route at V6.6, and
# (2) when Live Games is first selected, rerun so the next pass can render it
#     outside the navigation column.
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

compile(source, "<kyre_wnba_live_v661_full_width_preflight>", "exec")
exec(
    compile(source, "kyre_wnba_live_games_v661_memory_safe_route.py", "exec"),
    globals(),
    globals(),
)
