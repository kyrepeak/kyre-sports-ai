"""KYRE Streamlit router V8 — additive MLB Moneyline Step 5 route.

Router V7 remains permanently frozen. This wrapper advances only MLB `Moneyline`
from frozen V16.9 Step 4 to additive V17.0 Step 5. Hits, Matchup Explorer, and
all other markets continue through the frozen V7/V6/V5/V4/V3/V2/V1 chain unchanged.
"""
from __future__ import annotations

import streamlit as st
import streamlit_memory_lazy_router_v7 as frozen_router

MODEL_VERSION = "KYRE STREAMLIT ROUTER V8 • Moneyline Step 5"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v7"
_BASE_MLB_ROUTE = frozen_router._render_mlb_v7_base
_FROZEN = frozen_router._FROZEN


def _render_mlb_v8_base(market: str) -> None:
    if market != "Moneyline":
        return _BASE_MLB_ROUTE(market)

    games_df, day = _FROZEN._load_mlb_schedule()
    st.caption(f"⚾ MLB • {day} • lazy route: {market}")
    mod = _FROZEN._import("mlb_moneyline_hub_v170")
    mod.render_moneyline_hub(
        games_df,
        _FROZEN.section_header,
        _FROZEN.status_info,
        _FROZEN.team_logo,
        _FROZEN.h,
    )


def render_app() -> None:
    original = frozen_router._render_mlb_v7_base
    frozen_router._render_mlb_v7_base = _render_mlb_v8_base
    try:
        frozen_router.render_app()
    finally:
        frozen_router._render_mlb_v7_base = original


__all__ = ["FROZEN_ROUTER", "MODEL_VERSION", "_render_mlb_v8_base", "render_app"]
