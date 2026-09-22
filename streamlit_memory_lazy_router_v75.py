"""KYRE Streamlit Router V75 — CFB O/U parallel-prewarm fast route.

Step 4 of the College Football Over/Under performance work.

V75 preserves Router V74's direct CFB Over/Under fast route and advances only
that route from Clean Page V33 to Clean Page V34. V34 overlaps certified
analysis-source cache warmups with the existing live market request while
keeping frozen V14 projection math and every identity/market protection intact.

Every non-active-CFB-O/U route delegates to certified Router V74 unchanged.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

import streamlit_memory_lazy_router_v74 as prior
import streamlit_memory_lazy_router_v1 as root

MODEL_VERSION = "KYRE STREAMLIT ROUTER V75 • CFB O/U PARALLEL PREWARM FAST ROUTE"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v74"
CFB_SPORT_LABEL = prior.CFB_SPORT_LABEL
CFB_MARKETS = tuple(prior.CFB_MARKETS)
OVER_UNDER_MARKET = "Over/Under"
ACTIVE_PAGE = "cfb_over_under_clean_page_v34"

_ORIGINAL_SELECTBOX = root.st.selectbox
_ORIGINAL_RENDER_NFL = root._render_nfl


def _fast_route_active() -> bool:
    return (
        str(st.session_state.get("ks_sport_touch") or "") == CFB_SPORT_LABEL
        and str(st.session_state.get("ks_cfb_market_touch") or "") == OVER_UNDER_MARKET
    )


def _selectbox_v75(label: Any, options: Any, *args: Any, **kwargs: Any):
    if label == "🏟️ Sport":
        choices = list(options)
        if CFB_SPORT_LABEL not in choices:
            choices.append(CFB_SPORT_LABEL)
        return _ORIGINAL_SELECTBOX(label, choices, *args, **kwargs)

    if (
        label == "🎯 NFL Market"
        and str(st.session_state.get("ks_sport_touch") or "") == CFB_SPORT_LABEL
    ):
        if str(st.session_state.get("ks_cfb_market_touch") or "") not in CFB_MARKETS:
            st.session_state.pop("ks_cfb_market_touch", None)

        clean_kwargs = dict(kwargs)
        clean_kwargs.pop("key", None)
        clean_kwargs.pop("index", None)
        return _ORIGINAL_SELECTBOX(
            "🎯 CFB Market",
            list(CFB_MARKETS),
            *args,
            key="ks_cfb_market_touch",
            **clean_kwargs,
        )

    return _ORIGINAL_SELECTBOX(label, options, *args, **kwargs)


def _render_cfb_ou_direct(market: str) -> None:
    if (
        str(st.session_state.get("ks_sport_touch") or "") != CFB_SPORT_LABEL
        or market != OVER_UNDER_MARKET
    ):
        return _ORIGINAL_RENDER_NFL(market)

    mod = root._import(ACTIVE_PAGE)
    mod.render_cfb_hub(
        market,
        root.section_header,
        root.status_info,
        root.team_logo,
        root.h,
    )


def _render_direct_cfb_ou() -> None:
    original_selectbox = root.st.selectbox
    original_render_nfl = root._render_nfl
    original_prefixes = root._ROUTE_MODULE_PREFIXES

    root.st.selectbox = _selectbox_v75
    root._render_nfl = _render_cfb_ou_direct
    if "cfb_" not in root._ROUTE_MODULE_PREFIXES:
        root._ROUTE_MODULE_PREFIXES = root._ROUTE_MODULE_PREFIXES + ("cfb_",)

    try:
        root.render_app()
    finally:
        root.st.selectbox = original_selectbox
        root._render_nfl = original_render_nfl
        root._ROUTE_MODULE_PREFIXES = original_prefixes


def render_app() -> None:
    if _fast_route_active():
        return _render_direct_cfb_ou()
    return prior.render_app()


__all__ = [
    "ACTIVE_PAGE",
    "CFB_MARKETS",
    "CFB_SPORT_LABEL",
    "FROZEN_ROUTER",
    "MODEL_VERSION",
    "OVER_UNDER_MARKET",
    "_fast_route_active",
    "_render_cfb_ou_direct",
    "_render_direct_cfb_ou",
    "_selectbox_v75",
    "render_app",
]
