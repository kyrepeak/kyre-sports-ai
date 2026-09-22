"""KYRE Streamlit router V20 — additive MLB Hits Step 5 route.

Router V19 remains permanently frozen. This wrapper advances only MLB `1+ Hit`
from frozen Hits UI V13.19 Step 4 to additive UI V13.20 Step 5. MLB Moneyline
remains frozen on V17.8 Step 12 and every non-Hits route delegates through the
frozen Router V19 chain unchanged.
"""
from __future__ import annotations

import streamlit as st
import streamlit_memory_lazy_router_v19 as frozen_router

MODEL_VERSION = "KYRE STREAMLIT ROUTER V20 • Hits Step 5"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v19"
_BASE_MLB_ROUTE = frozen_router._render_mlb_v19_base
_FROZEN = frozen_router._FROZEN


def _render_mlb_v20_base(market: str) -> None:
    if market != "1+ Hit":
        return _BASE_MLB_ROUTE(market)

    games_df, day = _FROZEN._load_mlb_schedule()
    st.caption(f"⚾ MLB • {day} • lazy route: {market}")
    _FROZEN._install_step8f_for_market(market)
    mod = _FROZEN._import("mlb_hit_hub_v1320")
    mod.render_hit_hub(
        games_df,
        _FROZEN.section_header,
        _FROZEN.status_info,
        _FROZEN.team_logo,
        _FROZEN.h,
    )


def render_app() -> None:
    original = frozen_router._render_mlb_v19_base
    frozen_router._render_mlb_v19_base = _render_mlb_v20_base
    try:
        frozen_router.render_app()
    finally:
        frozen_router._render_mlb_v19_base = original


__all__ = ["FROZEN_ROUTER", "MODEL_VERSION", "_render_mlb_v20_base", "render_app"]
