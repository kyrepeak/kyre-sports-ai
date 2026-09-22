"""KYRE Streamlit router V5 — additive MLB Moneyline Step 2 route.

Router V4 remains frozen. This wrapper advances only MLB `Moneyline` from the
frozen V16.6 Step 1 presentation to additive Moneyline UI V16.7 Step 2.
Hits, Matchup Explorer, and every other market continue through Router V4/V3/V2/V1
unchanged.
"""
from __future__ import annotations

import streamlit as st
import streamlit_memory_lazy_router_v4 as frozen_router

MODEL_VERSION = "KYRE STREAMLIT ROUTER V5 • Moneyline Step 2"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v4"


def _render_mlb_v5_base(market: str) -> None:
    """Route only Moneyline to V16.7; delegate every other MLB market unchanged."""
    if market != "Moneyline":
        return frozen_router._BASE_MLB_ROUTE(market)

    games_df, day = frozen_router.frozen._load_mlb_schedule()
    st.caption(f"⚾ MLB • {day} • lazy route: {market}")
    mod = frozen_router.frozen._import("mlb_moneyline_hub_v167")
    mod.render_moneyline_hub(
        games_df,
        frozen_router.frozen.section_header,
        frozen_router.frozen.status_info,
        frozen_router.frozen.team_logo,
        frozen_router.frozen.h,
    )


def render_app() -> None:
    """Delegate through frozen Router V4 while swapping only its Moneyline hook."""
    original = frozen_router._render_mlb_v4_base
    frozen_router._render_mlb_v4_base = _render_mlb_v5_base
    try:
        frozen_router.render_app()
    finally:
        frozen_router._render_mlb_v4_base = original


__all__ = ["FROZEN_ROUTER", "MODEL_VERSION", "_render_mlb_v5_base", "render_app"]
