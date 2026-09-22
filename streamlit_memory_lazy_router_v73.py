"""KYRE Streamlit Router V73 — direct CFB O/U fast route.

Step 2 of the College Football Over/Under performance work.

When Streamlit session state already identifies the active route as
College Football -> Over/Under, V73 bypasses the historical V2-V72 wrapper
traversal and runs the frozen V1 shell directly with only the two adaptations
required for the certified CFB route:

1. extend the frozen sport/market selectors with the current CFB choices;
2. dispatch the frozen NFL fallback slot directly to certified Clean Page V32.

Every other route delegates to certified Router V72 unchanged. The fast path
changes no schedule, market, team-data, projection, ranking, qualification, or
selection behavior.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

import streamlit_memory_lazy_router_v72 as prior
import streamlit_memory_lazy_router_v1 as root

MODEL_VERSION = "KYRE STREAMLIT ROUTER V73 • DIRECT CFB O/U FAST ROUTE"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v72"
CFB_SPORT_LABEL = prior.CFB_SPORT_LABEL
CFB_MARKETS = tuple(prior.CFB_MARKETS)
OVER_UNDER_MARKET = "Over/Under"
ACTIVE_PAGE = "cfb_over_under_clean_page_v32"

_ORIGINAL_SELECTBOX = root.st.selectbox
_ORIGINAL_RENDER_NFL = root._render_nfl


def _fast_route_active() -> bool:
    return (
        str(st.session_state.get("ks_sport_touch") or "") == CFB_SPORT_LABEL
        and str(st.session_state.get("ks_cfb_market_touch") or "") == OVER_UNDER_MARKET
    )


def _selectbox_v73(label: Any, options: Any, *args: Any, **kwargs: Any):
    """Apply only the already-certified CFB selector adaptation."""
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
    """Dispatch only certified CFB Over/Under directly to Clean Page V32."""
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
    """Run the frozen V1 shell without traversing the historical router stack."""
    original_selectbox = root.st.selectbox
    original_render_nfl = root._render_nfl
    original_prefixes = root._ROUTE_MODULE_PREFIXES

    root.st.selectbox = _selectbox_v73
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
    "_selectbox_v73",
    "render_app",
]
