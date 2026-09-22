"""KYRE Streamlit Router V56 — CFB O/U central runtime team-data handoff."""
from __future__ import annotations

import streamlit as st

import streamlit_memory_lazy_router_v55 as prior
import streamlit_memory_lazy_router_v1 as root

MODEL_VERSION="KYRE STREAMLIT ROUTER V56 • CFB O/U CENTRAL RUNTIME TEAM DATA"
FROZEN_ROUTER="streamlit_memory_lazy_router_v55"
CFB_SPORT_LABEL=prior.CFB_SPORT_LABEL
CFB_MARKETS=prior.CFB_MARKETS
OVER_UNDER_MARKET="Over/Under"
_FROZEN_RENDER_NFL_OR_CFB=prior._render_nfl_or_cfb_v55


def _render_nfl_or_cfb_v56(market:str)->None:
    sport=str(st.session_state.get("ks_sport_touch") or "")
    if sport!=CFB_SPORT_LABEL or market!=OVER_UNDER_MARKET:
        return _FROZEN_RENDER_NFL_OR_CFB(market)
    mod=root._import("cfb_over_under_matchup_ui_v16_runtime_team_data")
    mod.render_cfb_hub(
        market,
        root.section_header,
        root.status_info,
        root.team_logo,
        root.h,
    )


def render_app()->None:
    original=prior._render_nfl_or_cfb_v55
    prior._render_nfl_or_cfb_v55=_render_nfl_or_cfb_v56
    try:
        prior.render_app()
    finally:
        prior._render_nfl_or_cfb_v55=original


__all__=[
    "CFB_MARKETS",
    "CFB_SPORT_LABEL",
    "FROZEN_ROUTER",
    "MODEL_VERSION",
    "OVER_UNDER_MARKET",
    "_render_nfl_or_cfb_v56",
    "render_app",
]
