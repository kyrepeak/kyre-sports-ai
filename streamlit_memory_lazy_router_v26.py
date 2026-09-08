"""KYRE Streamlit Router V26 — College Football Step 4 Moneyline page UI.

Additive wrapper over permanently frozen Router V25.

Only College Football -> Moneyline advances to the dedicated Step-4
`cfb_moneyline_hub_v1` presentation layer. College Football Over/Under and
Game Total continue through the frozen V25 -> CFB Hub V3 path unchanged.
Every MLB/WNBA/NFL route also continues through the frozen chain unchanged.
"""
from __future__ import annotations

import streamlit as st

import streamlit_memory_lazy_router_v25 as prior
import streamlit_memory_lazy_router_v1 as root

MODEL_VERSION = "KYRE STREAMLIT ROUTER V26 • CFB Step 4 Moneyline UI"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v25"
CFB_SPORT_LABEL = prior.CFB_SPORT_LABEL
CFB_MARKETS = prior.CFB_MARKETS
MONEYLINE_MARKET = "Moneyline"

_FROZEN_RENDER_NFL_OR_CFB = prior._render_nfl_or_cfb_v25


def _render_nfl_or_cfb_v26(market: str) -> None:
    """Advance only College Football Moneyline to the Step-4 UI."""
    sport = str(st.session_state.get("ks_sport_touch") or "")
    if sport != CFB_SPORT_LABEL or market != MONEYLINE_MARKET:
        return _FROZEN_RENDER_NFL_OR_CFB(market)

    mod = root._import("cfb_moneyline_hub_v1")
    mod.render_cfb_hub(
        market,
        root.section_header,
        root.status_info,
        root.team_logo,
        root.h,
    )


def render_app() -> None:
    """Temporarily replace only V25's CFB dispatch, then restore it exactly."""
    original = prior._render_nfl_or_cfb_v25
    prior._render_nfl_or_cfb_v25 = _render_nfl_or_cfb_v26
    try:
        prior.render_app()
    finally:
        prior._render_nfl_or_cfb_v25 = original


__all__ = [
    "CFB_MARKETS",
    "CFB_SPORT_LABEL",
    "FROZEN_ROUTER",
    "MODEL_VERSION",
    "MONEYLINE_MARKET",
    "_render_nfl_or_cfb_v26",
    "render_app",
]
