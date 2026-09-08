"""KYRE Streamlit router V19 — additive MLB Hits Step 4 route.

Router V18 remains permanently frozen. This wrapper advances only MLB `1+ Hit`
from frozen Hits UI V13.18 Step 3 to additive UI V13.19 Step 4. MLB Moneyline
remains frozen on V17.8 Step 12 and every non-Hits route delegates through the
frozen Router V18 chain unchanged.
"""
from __future__ import annotations

import streamlit as st
import streamlit_memory_lazy_router_v18 as frozen_router

MODEL_VERSION = "KYRE STREAMLIT ROUTER V19 • Hits Step 4"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v18"
_BASE_MLB_ROUTE = frozen_router._render_mlb_v18_base
_FROZEN = frozen_router._FROZEN


def _render_mlb_v19_base(market: str) -> None:
    if market != "1+ Hit":
        return _BASE_MLB_ROUTE(market)

    games_df, day = _FROZEN._load_mlb_schedule()
    st.caption(f"⚾ MLB • {day} • lazy route: {market}")
    _FROZEN._install_step8f_for_market(market)
    mod = _FROZEN._import("mlb_hit_hub_v1319")
    mod.render_hit_hub(
        games_df,
        _FROZEN.section_header,
        _FROZEN.status_info,
        _FROZEN.team_logo,
        _FROZEN.h,
    )


def render_app() -> None:
    original = frozen_router._render_mlb_v18_base
    frozen_router._render_mlb_v18_base = _render_mlb_v19_base
    try:
        frozen_router.render_app()
    finally:
        frozen_router._render_mlb_v18_base = original


__all__ = ["FROZEN_ROUTER", "MODEL_VERSION", "_render_mlb_v19_base", "render_app"]
