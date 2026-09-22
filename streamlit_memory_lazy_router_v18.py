"""KYRE Streamlit router V18 — additive MLB Hits Step 3 route.

Router V17 remains permanently frozen. This wrapper advances only MLB `1+ Hit`
from frozen Hits UI V13.17 Step 2 to additive UI V13.18 Step 3. MLB Moneyline
remains on frozen V17.8 Step 12 and every other route delegates through the
frozen Router V17 chain unchanged.
"""
from __future__ import annotations

import streamlit as st
import streamlit_memory_lazy_router_v17 as frozen_router

MODEL_VERSION = "KYRE STREAMLIT ROUTER V18 • Hits Step 3"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v17"
_BASE_MLB_ROUTE = frozen_router._render_mlb_v17_base
_FROZEN = frozen_router._FROZEN


def _render_mlb_v18_base(market: str) -> None:
    if market != "1+ Hit":
        return _BASE_MLB_ROUTE(market)

    games_df, day = _FROZEN._load_mlb_schedule()
    st.caption(f"⚾ MLB • {day} • lazy route: {market}")
    _FROZEN._install_step8f_for_market(market)
    mod = _FROZEN._import("mlb_hit_hub_v1318")
    mod.render_hit_hub(
        games_df,
        _FROZEN.section_header,
        _FROZEN.status_info,
        _FROZEN.team_logo,
        _FROZEN.h,
    )


def render_app() -> None:
    original = frozen_router._render_mlb_v17_base
    frozen_router._render_mlb_v17_base = _render_mlb_v18_base
    try:
        frozen_router.render_app()
    finally:
        frozen_router._render_mlb_v17_base = original


__all__ = ["FROZEN_ROUTER", "MODEL_VERSION", "_render_mlb_v18_base", "render_app"]
