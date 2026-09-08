"""KYRE Streamlit Router V32 — CFB Step 8 Over/Under Model V1.

Additive wrapper over permanently frozen Router V31.

Only College Football -> Over/Under advances to cfb_over_under_hub_v2.
College Football -> Moneyline remains on frozen Step 6.
College Football -> Game Total and all MLB/WNBA/NFL routes delegate unchanged.
"""
from __future__ import annotations

import streamlit as st

import streamlit_memory_lazy_router_v31 as prior
import streamlit_memory_lazy_router_v1 as root

MODEL_VERSION = "KYRE STREAMLIT ROUTER V32 • CFB Step 8 Over/Under Model V1"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v31"
CFB_SPORT_LABEL = prior.CFB_SPORT_LABEL
CFB_MARKETS = prior.CFB_MARKETS
OVER_UNDER_MARKET = "Over/Under"

_FROZEN_RENDER_NFL_OR_CFB = prior._render_nfl_or_cfb_v31


def _render_nfl_or_cfb_v32(market: str) -> None:
    sport = str(st.session_state.get("ks_sport_touch") or "")
    if sport != CFB_SPORT_LABEL or market != OVER_UNDER_MARKET:
        return _FROZEN_RENDER_NFL_OR_CFB(market)

    mod = root._import("cfb_over_under_hub_v2")
    mod.render_cfb_hub(
        market,
        root.section_header,
        root.status_info,
        root.team_logo,
        root.h,
    )


def render_app() -> None:
    original = prior._render_nfl_or_cfb_v31
    prior._render_nfl_or_cfb_v31 = _render_nfl_or_cfb_v32
    try:
        prior.render_app()
    finally:
        prior._render_nfl_or_cfb_v31 = original


__all__ = [
    "CFB_MARKETS",
    "CFB_SPORT_LABEL",
    "FROZEN_ROUTER",
    "MODEL_VERSION",
    "OVER_UNDER_MARKET",
    "_render_nfl_or_cfb_v32",
    "render_app",
]
