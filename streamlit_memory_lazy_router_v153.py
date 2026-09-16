"""KYRE Streamlit Router V153 — CFB Over/Under compact evidence renderer.

Additive over frozen Router V152. V153 advances only exact College Football ->
Over/Under to Clean Page V39. Game Total remains owned by V152, Moneyline and
all other certified routes remain delegated through the frozen router chain.
"""
from __future__ import annotations

import streamlit as st

import streamlit_memory_lazy_router_v1 as root
import streamlit_memory_lazy_router_v77 as cfb_route_base
import streamlit_memory_lazy_router_v152 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V153 • CFB O/U COMPACT EVIDENCE RENDERER"
PRODUCTION_HEARTBEAT = "CFB_OVER_UNDER_V39_PRODUCTION_ACTIVE"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v152"
CFB_SPORT_LABEL = "College Football"
OVER_UNDER_MARKET = "Over/Under"
ACTIVE_PAGE = "cfb_over_under_clean_page_v39"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False

_ORIGINAL_RENDER_NFL = root._render_nfl


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def _over_under_route_active() -> bool:
    return (
        str(st.session_state.get("ks_sport_touch") or "") == CFB_SPORT_LABEL
        and str(st.session_state.get("ks_cfb_market_touch") or "") == OVER_UNDER_MARKET
    )


def _query_requests_over_under() -> bool:
    return (
        cfb_route_base._query_value(cfb_route_base.ROUTE_QUERY_SPORT) == CFB_SPORT_LABEL
        and cfb_route_base._query_value(cfb_route_base.ROUTE_QUERY_MARKET) == OVER_UNDER_MARKET
    )


def _restore_over_under_route_from_query() -> bool:
    current_sport = str(st.session_state.get("ks_sport_touch") or "").strip()
    current_market = str(st.session_state.get("ks_cfb_market_touch") or "").strip()
    if current_sport or current_market:
        return False
    if not _query_requests_over_under():
        return False
    st.session_state["ks_sport_touch"] = CFB_SPORT_LABEL
    st.session_state["ks_cfb_market_touch"] = OVER_UNDER_MARKET
    return True


def _render_production_heartbeat() -> None:
    st.markdown(
        f'<div data-testid="cfb-over-under-v39-heartbeat" '
        f'style="font-size:.58rem;font-weight:800;color:#a7b6c5;margin:0 0 4px 2px">'
        f'{PRODUCTION_HEARTBEAT}</div>',
        unsafe_allow_html=True,
    )


def _render_cfb_over_under_v153(market: str) -> None:
    sport = str(st.session_state.get("ks_sport_touch") or "")
    market = str(market or "")

    if sport == CFB_SPORT_LABEL and market != OVER_UNDER_MARKET:
        cfb_route_base._clear_fast_route_query()
        st.rerun()

    if sport != CFB_SPORT_LABEL or market != OVER_UNDER_MARKET:
        return _ORIGINAL_RENDER_NFL(market)

    cfb_route_base._persist_fast_route_query()
    _render_production_heartbeat()
    page = root._import(ACTIVE_PAGE)
    return page.render_cfb_hub(
        market,
        root.section_header,
        root.status_info,
        root.team_logo,
        root.h,
    )


def _render_direct_cfb_over_under() -> None:
    original_selectbox = root.st.selectbox
    original_render_nfl = root._render_nfl
    original_prefixes = root._ROUTE_MODULE_PREFIXES

    root.st.selectbox = cfb_route_base._selectbox_v77
    root._render_nfl = _render_cfb_over_under_v153
    if "cfb_" not in root._ROUTE_MODULE_PREFIXES:
        root._ROUTE_MODULE_PREFIXES = root._ROUTE_MODULE_PREFIXES + ("cfb_",)

    try:
        return root.render_app()
    finally:
        root.st.selectbox = original_selectbox
        root._render_nfl = original_render_nfl
        root._ROUTE_MODULE_PREFIXES = original_prefixes


def render_app() -> None:
    if not _over_under_route_active():
        _restore_over_under_route_from_query()
    if _over_under_route_active():
        return _render_direct_cfb_over_under()
    return prior.render_app()


__all__ = [
    "ACTIVE_PAGE",
    "CFB_SPORT_LABEL",
    "FROZEN_ROUTER",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "OVER_UNDER_MARKET",
    "PRODUCTION_HEARTBEAT",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_over_under_route_active",
    "_query_requests_over_under",
    "_render_cfb_over_under_v153",
    "_render_direct_cfb_over_under",
    "_render_production_heartbeat",
    "_restore_over_under_route_from_query",
    "record_bootstrap_import_ms",
    "render_app",
]
