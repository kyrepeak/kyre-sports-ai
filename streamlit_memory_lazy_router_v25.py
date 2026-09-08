"""KYRE Streamlit Router V25 — College Football Step 3 team data foundation.

Additive wrapper over permanently frozen Router V24. Only the College Football
dispatch advances from CFB Hub V2 to CFB Hub V3. MLB, WNBA, NFL, and frozen
CFB Steps 1–2 continue through the existing chain unchanged.
"""
from __future__ import annotations

import streamlit as st

import streamlit_memory_lazy_router_v24 as prior
import streamlit_memory_lazy_router_v1 as root

MODEL_VERSION = "KYRE STREAMLIT ROUTER V25 • CFB Step 3"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v24"
CFB_SPORT_LABEL = prior.CFB_SPORT_LABEL
CFB_MARKETS = prior.CFB_MARKETS

_FROZEN_RENDER_NFL_OR_CFB = prior._render_nfl_or_cfb_v24


def _render_nfl_or_cfb_v25(market: str) -> None:
    """Advance only College Football to CFB Hub V3."""
    if str(st.session_state.get("ks_sport_touch") or "") != CFB_SPORT_LABEL:
        return _FROZEN_RENDER_NFL_OR_CFB(market)

    mod = root._import("cfb_hub_v3")
    mod.render_cfb_hub(
        market,
        root.section_header,
        root.status_info,
        root.team_logo,
        root.h,
    )


def render_app() -> None:
    """Temporarily replace only V24's CFB dispatch, then restore it exactly."""
    original = prior._render_nfl_or_cfb_v24
    prior._render_nfl_or_cfb_v24 = _render_nfl_or_cfb_v25
    try:
        prior.render_app()
    finally:
        prior._render_nfl_or_cfb_v24 = original


__all__ = [
    "CFB_MARKETS",
    "CFB_SPORT_LABEL",
    "FROZEN_ROUTER",
    "MODEL_VERSION",
    "_render_nfl_or_cfb_v25",
    "render_app",
]
