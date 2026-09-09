"""KYRE Streamlit Router V54 — CFB O/U deep current-data reconciliation."""
from __future__ import annotations

import streamlit as st

import streamlit_memory_lazy_router_v53 as prior
import streamlit_memory_lazy_router_v1 as root

MODEL_VERSION="KYRE STREAMLIT ROUTER V54 • CFB O/U DEEP DATA RECONCILIATION"
FROZEN_ROUTER="streamlit_memory_lazy_router_v53"
CFB_SPORT_LABEL=prior.CFB_SPORT_LABEL
CFB_MARKETS=prior.CFB_MARKETS
OVER_UNDER_MARKET="Over/Under"
_FROZEN_RENDER_NFL_OR_CFB=prior._render_nfl_or_cfb_v53


def _render_nfl_or_cfb_v54(market:str)->None:
    sport=str(st.session_state.get("ks_sport_touch") or "")
    if sport!=CFB_SPORT_LABEL or market!=OVER_UNDER_MARKET:
        return _FROZEN_RENDER_NFL_OR_CFB(market)
    mod=root._import("cfb_over_under_matchup_ui_v14_deep_data")
    mod.render_cfb_hub(market,root.section_header,root.status_info,root.team_logo,root.h)


def render_app()->None:
    original=prior._render_nfl_or_cfb_v53
    prior._render_nfl_or_cfb_v53=_render_nfl_or_cfb_v54
    try:
        prior.render_app()
    finally:
        prior._render_nfl_or_cfb_v53=original


__all__=[
    "CFB_MARKETS",
    "CFB_SPORT_LABEL",
    "FROZEN_ROUTER",
    "MODEL_VERSION",
    "OVER_UNDER_MARKET",
    "_render_nfl_or_cfb_v54",
    "render_app",
]
