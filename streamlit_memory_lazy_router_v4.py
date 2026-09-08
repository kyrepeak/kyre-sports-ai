"""KYRE Streamlit router V4 — additive MLB Moneyline Step 1 route.

Router V3 remains frozen. This wrapper changes only MLB `Moneyline` from the
historical V16.4 compatibility route to additive Moneyline UI V16.6. The frozen
Hits V13.16 route, Matchup Explorer route, and every other market continue through
Router V3/V2/V1 unchanged.
"""
from __future__ import annotations

import streamlit as st
import streamlit_memory_lazy_router_v3 as prior

frozen = prior.frozen
MODEL_VERSION = "KYRE STREAMLIT ROUTER V4 • Moneyline Step 1"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v3"
_BASE_MLB_ROUTE = prior._BASE_RENDER_MLB


def _render_mlb_v4_base(market: str) -> None:
    if market != "Moneyline":
        return _BASE_MLB_ROUTE(market)

    games_df, day = frozen._load_mlb_schedule()
    st.caption(f"⚾ MLB • {day} • lazy route: {market}")
    mod = frozen._import("mlb_moneyline_hub_v166")
    mod.render_moneyline_hub(
        games_df,
        frozen.section_header,
        frozen.status_info,
        frozen.team_logo,
        frozen.h,
    )


def render_app() -> None:
    original = prior._BASE_RENDER_MLB
    prior._BASE_RENDER_MLB = _render_mlb_v4_base
    try:
        prior.render_app()
    finally:
        prior._BASE_RENDER_MLB = original


__all__ = ["FROZEN_ROUTER", "MODEL_VERSION", "_render_mlb_v4_base", "render_app"]
