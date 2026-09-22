"""KYRE Streamlit router V10 — additive MLB Moneyline Step 6 route.

Router V9 remains permanently frozen. This wrapper advances only MLB `Moneyline`
from frozen V17.1 Step 5L to additive V17.2 Step 6. Every non-Moneyline route
continues through the frozen V9/V8/V7/V6/V5/V4/V3/V2/V1 chain unchanged.
"""
from __future__ import annotations

import streamlit as st
import streamlit_memory_lazy_router_v9 as frozen_router

MODEL_VERSION = "KYRE STREAMLIT ROUTER V10 • Moneyline Step 6"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v9"
_BASE_MLB_ROUTE = frozen_router._render_mlb_v9_base
_FROZEN = frozen_router._FROZEN


def _render_mlb_v10_base(market: str) -> None:
    if market != "Moneyline":
        return _BASE_MLB_ROUTE(market)

    games_df, day = _FROZEN._load_mlb_schedule()
    st.caption(f"⚾ MLB • {day} • lazy route: {market}")
    mod = _FROZEN._import("mlb_moneyline_hub_v172")
    mod.render_moneyline_hub(
        games_df,
        _FROZEN.section_header,
        _FROZEN.status_info,
        _FROZEN.team_logo,
        _FROZEN.h,
    )


def render_app() -> None:
    original = frozen_router._render_mlb_v9_base
    frozen_router._render_mlb_v9_base = _render_mlb_v10_base
    try:
        frozen_router.render_app()
    finally:
        frozen_router._render_mlb_v9_base = original


__all__ = ["FROZEN_ROUTER", "MODEL_VERSION", "_render_mlb_v10_base", "render_app"]
