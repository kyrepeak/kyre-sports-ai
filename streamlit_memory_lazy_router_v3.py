"""KYRE Streamlit router V3 — additive MLB Hits presentation route.

All frozen V2/V1 router behavior is preserved. Only the MLB `1+ Hit` market is
redirected from certified Hit UI V13.15 to additive UI V13.16. Matchup Explorer
and every other market continue through the frozen router unchanged.
"""
from __future__ import annotations

import streamlit as st
import streamlit_memory_lazy_router_v2 as prior

frozen = prior.frozen
MODEL_VERSION = "KYRE STREAMLIT ROUTER V3 • Hits presentation upgrade"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v2"
_BASE_RENDER_MLB = frozen._render_mlb


def _render_mlb_v3(market: str) -> None:
    if market != "1+ Hit":
        return _BASE_RENDER_MLB(market)

    games_df, day = frozen._load_mlb_schedule()
    st.caption(f"⚾ MLB • {day} • lazy route: {market}")
    frozen._install_step8f_for_market(market)
    mod = frozen._import("mlb_hit_hub_v1316")
    mod.render_hit_hub(
        games_df,
        frozen.section_header,
        frozen.status_info,
        frozen.team_logo,
        frozen.h,
    )


def render_app() -> None:
    original = frozen._render_mlb
    frozen._render_mlb = _render_mlb_v3
    try:
        prior.render_app()
    finally:
        frozen._render_mlb = original


__all__ = ["FROZEN_ROUTER", "MODEL_VERSION", "_render_mlb_v3", "render_app"]
