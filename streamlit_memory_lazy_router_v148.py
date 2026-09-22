"""KYRE Streamlit Router V148 — CFB Moneyline Monster dashboard.

Additive over frozen Router V147. Advances only exact College Football ->
Moneyline to the new presentation-only clean page while preserving Receiving
Yards V16, CFB Over/Under, Game Total, and every other certified route.

No CFB Moneyline projection, probability, calibration, fair-odds, or ranking
math is implemented here. Sportsbook projection influence remains 0.0%.
"""
from __future__ import annotations

import streamlit as st

import streamlit_memory_lazy_router_v1 as root
import streamlit_memory_lazy_router_v77 as cfb_route_base
import streamlit_memory_lazy_router_v147 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V148 • CFB MONEYLINE MONSTER DASHBOARD"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v147"
CFB_SPORT_LABEL = "College Football"
MONEYLINE_MARKET = "Moneyline"
ACTIVE_PAGE = "cfb_moneyline_clean_page_v1"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False

_ORIGINAL_RENDER_NFL = root._render_nfl


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def _moneyline_route_active() -> bool:
    return (
        str(st.session_state.get("ks_sport_touch") or "") == CFB_SPORT_LABEL
        and str(st.session_state.get("ks_cfb_market_touch") or "") == MONEYLINE_MARKET
    )


def _install_frozen_moneyline_styles() -> None:
    """Load CSS only for frozen evidence cards rendered inside collapsed drawers."""
    frozen = root._import("cfb_moneyline_hub_v5")
    st.markdown(
        frozen.prior.frozen_step5.frozen_v1.identity_ui._CSS,
        unsafe_allow_html=True,
    )
    st.markdown(
        frozen.prior.frozen_step5.frozen_v3._STEP3_CSS,
        unsafe_allow_html=True,
    )
    st.markdown(
        frozen.prior.frozen_step5.frozen_v1._CSS,
        unsafe_allow_html=True,
    )
    st.markdown(frozen.prior.frozen_step5._CSS, unsafe_allow_html=True)
    st.markdown(frozen._CSS, unsafe_allow_html=True)


def _render_cfb_moneyline_v148(market: str) -> None:
    sport = str(st.session_state.get("ks_sport_touch") or "")
    market = str(market or "")

    if sport == CFB_SPORT_LABEL and market != MONEYLINE_MARKET:
        # The user changed CFB markets while the direct Moneyline render was
        # active. Stop this old rerun; V148 delegates the next rerun to V147.
        st.rerun()

    if sport != CFB_SPORT_LABEL or market != MONEYLINE_MARKET:
        return _ORIGINAL_RENDER_NFL(market)

    _install_frozen_moneyline_styles()
    page = root._import(ACTIVE_PAGE)
    return page.render_cfb_hub(
        market,
        root.section_header,
        root.status_info,
        root.team_logo,
        root.h,
    )


def _render_direct_cfb_moneyline() -> None:
    original_selectbox = root.st.selectbox
    original_render_nfl = root._render_nfl
    original_prefixes = root._ROUTE_MODULE_PREFIXES

    # Reuse the already-certified CFB sport/market selector behavior rather
    # than creating a second navigation system.
    root.st.selectbox = cfb_route_base._selectbox_v77
    root._render_nfl = _render_cfb_moneyline_v148
    if "cfb_" not in root._ROUTE_MODULE_PREFIXES:
        root._ROUTE_MODULE_PREFIXES = root._ROUTE_MODULE_PREFIXES + ("cfb_",)

    try:
        return root.render_app()
    finally:
        root.st.selectbox = original_selectbox
        root._render_nfl = original_render_nfl
        root._ROUTE_MODULE_PREFIXES = original_prefixes


def render_app() -> None:
    if _moneyline_route_active():
        return _render_direct_cfb_moneyline()
    return prior.render_app()


__all__ = [
    "ACTIVE_PAGE",
    "CFB_SPORT_LABEL",
    "FROZEN_ROUTER",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "MONEYLINE_MARKET",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_install_frozen_moneyline_styles",
    "_moneyline_route_active",
    "_render_cfb_moneyline_v148",
    "_render_direct_cfb_moneyline",
    "record_bootstrap_import_ms",
    "render_app",
]
