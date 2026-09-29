"""Streamlit Router V245 — CFB Top Picks normal dropdown ownership.

Additive over frozen V244. It changes only the rendered College Football market
selector so the already-certified Top Picks route is visible from normal app
navigation. Existing CFB markets and every non-CFB route delegate unchanged.
"""
from __future__ import annotations

from typing import Any, Callable

import streamlit as st

import streamlit_memory_lazy_router_v244 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V245 • CFB TOP PICKS NAV STEP 1 DROPDOWN"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v244"
CFB_MARKET_LABEL = "🎯 CFB Market"
TOP_PICKS_MARKET = "Top Picks"
MAY_MODIFY_TOP_PICKS_PRODUCT = False
MAY_MODIFY_EXISTING_CFB_PRODUCTS = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
HISTORY_PROJECTION_INFLUENCE = 0.0


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def _with_top_picks_selectbox(callback: Callable[[], Any]):
    """Append Top Picks only to the visible CFB market selector."""
    original_selectbox = st.selectbox

    def selectbox_with_top_picks(label, options, *args, **kwargs):
        resolved = list(options)
        if str(label or "").strip() == CFB_MARKET_LABEL:
            if TOP_PICKS_MARKET not in resolved:
                resolved.append(TOP_PICKS_MARKET)
        return original_selectbox(label, resolved, *args, **kwargs)

    st.selectbox = selectbox_with_top_picks
    try:
        return callback()
    finally:
        st.selectbox = original_selectbox


def render_app() -> None:
    return _with_top_picks_selectbox(prior.render_app)


__all__ = [
    "CFB_MARKET_LABEL",
    "FROZEN_ROUTER",
    "HISTORY_PROJECTION_INFLUENCE",
    "MAY_MODIFY_EXISTING_CFB_PRODUCTS",
    "MAY_MODIFY_TOP_PICKS_PRODUCT",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "TOP_PICKS_MARKET",
    "_with_top_picks_selectbox",
    "record_bootstrap_import_ms",
    "render_app",
]
