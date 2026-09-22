"""KYRE Streamlit Router V31 — CFB Step 7 Over/Under foundation.

Additive wrapper over permanently frozen Router V30.

Only College Football -> Over/Under advances to cfb_over_under_hub_v1.
College Football -> Moneyline remains on frozen Step 6 through Router V30.
College Football -> Game Total and all MLB/WNBA/NFL routes delegate unchanged.
"""
from __future__ import annotations

import streamlit as st

import streamlit_memory_lazy_router_v30 as prior
import streamlit_memory_lazy_router_v1 as root

MODEL_VERSION = "KYRE STREAMLIT ROUTER V31 • CFB Step 7 Over/Under Foundation"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v30"
CFB_SPORT_LABEL = prior.CFB_SPORT_LABEL
CFB_MARKETS = prior.CFB_MARKETS
OVER_UNDER_MARKET = "Over/Under"

_FROZEN_RENDER_NFL_OR_CFB = prior._render_nfl_or_cfb_v30


def _render_nfl_or_cfb_v31(market: str) -> None:
    sport = str(st.session_state.get("ks_sport_touch") or "")
    if sport != CFB_SPORT_LABEL or market != OVER_UNDER_MARKET:
        return _FROZEN_RENDER_NFL_OR_CFB(market)

    mod = root._import("cfb_over_under_hub_v1")
    mod.render_cfb_hub(
        market,
        root.section_header,
        root.status_info,
        root.team_logo,
        root.h,
    )


def render_app() -> None:
    original = prior._render_nfl_or_cfb_v30
    prior._render_nfl_or_cfb_v30 = _render_nfl_or_cfb_v31
    try:
        prior.render_app()
    finally:
        prior._render_nfl_or_cfb_v30 = original


__all__ = [
    "CFB_MARKETS",
    "CFB_SPORT_LABEL",
    "FROZEN_ROUTER",
    "MODEL_VERSION",
    "OVER_UNDER_MARKET",
    "_render_nfl_or_cfb_v31",
    "render_app",
]
