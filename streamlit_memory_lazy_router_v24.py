"""KYRE Streamlit Router V24 — College Football Step 2 schedule + identity.

Additive wrapper over permanently frozen Router V23. Only the College Football
dispatch advances from CFB Hub V1 to CFB Hub V2. MLB, WNBA, NFL, and frozen CFB
Step 1 routing behavior remain delegated through the existing chain.
"""
from __future__ import annotations

import streamlit as st

import streamlit_memory_lazy_router_v23 as prior
import streamlit_memory_lazy_router_v1 as root

MODEL_VERSION = "KYRE STREAMLIT ROUTER V24 • CFB Step 2"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v23"
CFB_SPORT_LABEL = prior.CFB_SPORT_LABEL
CFB_MARKETS = prior.CFB_MARKETS

_FROZEN_RENDER_NFL_OR_CFB = prior._render_nfl_or_cfb_v23


def _render_nfl_or_cfb_v24(market: str) -> None:
    """Advance only the College Football route to CFB Hub V2."""
    if str(st.session_state.get("ks_sport_touch") or "") != CFB_SPORT_LABEL:
        return _FROZEN_RENDER_NFL_OR_CFB(market)

    mod = root._import("cfb_hub_v2")
    mod.render_cfb_hub(
        market,
        root.section_header,
        root.status_info,
        root.team_logo,
        root.h,
    )


def render_app() -> None:
    """Temporarily replace only V23's CFB dispatch, then restore it exactly."""
    original = prior._render_nfl_or_cfb_v23
    prior._render_nfl_or_cfb_v23 = _render_nfl_or_cfb_v24
    try:
        prior.render_app()
    finally:
        prior._render_nfl_or_cfb_v23 = original


__all__ = [
    "CFB_MARKETS",
    "CFB_SPORT_LABEL",
    "FROZEN_ROUTER",
    "MODEL_VERSION",
    "_render_nfl_or_cfb_v24",
    "render_app",
]
