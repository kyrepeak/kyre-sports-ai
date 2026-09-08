"""KYRE Streamlit router V21 — strict no-TOUGH Hits hotfix.

Router V20 remains permanently frozen. Only MLB `1+ Hit` advances from
V13.20 to V13.21. All other markets delegate through frozen Router V20.
"""
from __future__ import annotations

import streamlit as st
import streamlit_memory_lazy_router_v20 as frozen_router

MODEL_VERSION = "KYRE STREAMLIT ROUTER V21 • Hits strict no-TOUGH hotfix"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v20"
_BASE_MLB_ROUTE = frozen_router._render_mlb_v20_base
_FROZEN = frozen_router._FROZEN


def _render_mlb_v21_base(market: str) -> None:
    if market != "1+ Hit":
        return _BASE_MLB_ROUTE(market)

    games_df, day = _FROZEN._load_mlb_schedule()
    st.caption(f"⚾ MLB • {day} • lazy route: {market}")
    _FROZEN._install_step8f_for_market(market)
    mod = _FROZEN._import("mlb_hit_hub_v1321")
    mod.render_hit_hub(
        games_df,
        _FROZEN.section_header,
        _FROZEN.status_info,
        _FROZEN.team_logo,
        _FROZEN.h,
    )


def render_app() -> None:
    original = frozen_router._render_mlb_v20_base
    frozen_router._render_mlb_v20_base = _render_mlb_v21_base
    try:
        frozen_router.render_app()
    finally:
        frozen_router._render_mlb_v20_base = original


__all__ = ["FROZEN_ROUTER", "MODEL_VERSION", "_render_mlb_v21_base", "render_app"]
