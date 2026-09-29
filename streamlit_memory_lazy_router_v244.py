"""Streamlit Router V244 — CFB Top Picks Step 4 detail dropdowns.

Additive over frozen V243. Only College Football -> Top Picks advances to the
Step-4 V4 page. Every other route delegates unchanged to frozen V243.
"""
from __future__ import annotations

import importlib

import streamlit_memory_lazy_router_v1 as root
import streamlit_memory_lazy_router_v241 as top_picks_base
import streamlit_memory_lazy_router_v243 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V244 • CFB TOP PICKS STEP 4"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v243"
TOP_PICKS_PAGE = "cfb_top_picks_page_v4"
MAY_MODIFY_EXISTING_CFB_PRODUCTS = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
HISTORY_PROJECTION_INFLUENCE = 0.0


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def _render_cfb_top_picks_v244(market: str) -> None:
    sport = str(root.st.session_state.get(top_picks_base.SPORT_KEY) or "").strip()
    normalized = str(market or "").strip()
    if sport != top_picks_base.CFB_SPORT_LABEL or normalized != top_picks_base.TOP_PICKS_MARKET:
        raise RuntimeError("Router V244 owns only College Football -> Top Picks.")

    top_picks_base._persist_top_picks_query()
    module = importlib.import_module(TOP_PICKS_PAGE)
    return module.render_cfb_hub(
        normalized,
        root.section_header,
        root.status_info,
        root.team_logo,
        root.h,
    )


def _render_direct_top_picks_v244() -> None:
    original_selectbox = root.st.selectbox
    original_render_nfl = root._render_nfl
    original_prefixes = root._ROUTE_MODULE_PREFIXES

    top_picks_base._install_top_picks_market_option()
    root.st.selectbox = top_picks_base.cfb_route_base._selectbox_v77
    root._render_nfl = _render_cfb_top_picks_v244
    if "cfb_" not in root._ROUTE_MODULE_PREFIXES:
        root._ROUTE_MODULE_PREFIXES = root._ROUTE_MODULE_PREFIXES + ("cfb_",)

    try:
        return root.render_app()
    finally:
        root.st.selectbox = original_selectbox
        root._render_nfl = original_render_nfl
        root._ROUTE_MODULE_PREFIXES = original_prefixes


def render_app() -> None:
    top_picks_base._install_top_picks_market_option()
    if not top_picks_base._active_top_picks_route() and top_picks_base._cold_top_picks_query_requested():
        top_picks_base._prime_top_picks_state_from_query()

    if top_picks_base._active_top_picks_route():
        return _render_direct_top_picks_v244()

    return prior.render_app()


__all__ = [
    "FROZEN_ROUTER",
    "HISTORY_PROJECTION_INFLUENCE",
    "MAY_MODIFY_EXISTING_CFB_PRODUCTS",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "TOP_PICKS_PAGE",
    "_render_cfb_top_picks_v244",
    "_render_direct_top_picks_v244",
    "record_bootstrap_import_ms",
    "render_app",
]
