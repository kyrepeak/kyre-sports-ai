"""KYRE Streamlit Router V36 — CFB Step 12 Final Game Total.

Additive wrapper over permanently frozen Router V35.

Only College Football -> Game Total advances to cfb_game_total_hub_v3.
Moneyline remains frozen Step 6. Over/Under remains frozen Step 9.
All MLB/WNBA/NFL routes delegate unchanged.
"""
from __future__ import annotations

import streamlit as st

import streamlit_memory_lazy_router_v35 as prior
import streamlit_memory_lazy_router_v1 as root

MODEL_VERSION = "KYRE STREAMLIT ROUTER V36 • CFB Step 12 Final"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v35"
CFB_SPORT_LABEL = prior.CFB_SPORT_LABEL
CFB_MARKETS = prior.CFB_MARKETS
GAME_TOTAL_MARKET = "Game Total"

_FROZEN_RENDER_NFL_OR_CFB = prior._render_nfl_or_cfb_v35


def _render_nfl_or_cfb_v36(market: str) -> None:
    sport = str(st.session_state.get("ks_sport_touch") or "")
    if sport != CFB_SPORT_LABEL or market != GAME_TOTAL_MARKET:
        return _FROZEN_RENDER_NFL_OR_CFB(market)

    mod = root._import("cfb_game_total_hub_v3")
    mod.render_cfb_hub(
        market,
        root.section_header,
        root.status_info,
        root.team_logo,
        root.h,
    )


def render_app() -> None:
    original = prior._render_nfl_or_cfb_v35
    prior._render_nfl_or_cfb_v35 = _render_nfl_or_cfb_v36
    try:
        prior.render_app()
    finally:
        prior._render_nfl_or_cfb_v35 = original


__all__ = [
    "CFB_MARKETS",
    "CFB_SPORT_LABEL",
    "FROZEN_ROUTER",
    "GAME_TOTAL_MARKET",
    "MODEL_VERSION",
    "_render_nfl_or_cfb_v36",
    "render_app",
]
