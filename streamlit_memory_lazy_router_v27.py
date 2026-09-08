"""KYRE Streamlit Router V27 — College Football Step 5 Moneyline Model V1.

Additive wrapper over permanently frozen Router V26.

Only College Football -> Moneyline advances from the frozen Step-4 page to the
raw pre-calibration Moneyline Model V1 UI. College Football Over/Under and
Game Total remain on their frozen prior routes. MLB/WNBA/NFL are untouched.
"""
from __future__ import annotations

import streamlit as st

import streamlit_memory_lazy_router_v26 as prior
import streamlit_memory_lazy_router_v1 as root

MODEL_VERSION = "KYRE STREAMLIT ROUTER V27 • CFB Step 5 Moneyline Model V1"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v26"
CFB_SPORT_LABEL = prior.CFB_SPORT_LABEL
CFB_MARKETS = prior.CFB_MARKETS
MONEYLINE_MARKET = "Moneyline"

_FROZEN_RENDER_NFL_OR_CFB = prior._render_nfl_or_cfb_v26


def _render_nfl_or_cfb_v27(market: str) -> None:
    """Advance only College Football Moneyline to Step 5."""
    sport = str(st.session_state.get("ks_sport_touch") or "")
    if sport != CFB_SPORT_LABEL or market != MONEYLINE_MARKET:
        return _FROZEN_RENDER_NFL_OR_CFB(market)

    mod = root._import("cfb_moneyline_hub_v2")
    mod.render_cfb_hub(
        market,
        root.section_header,
        root.status_info,
        root.team_logo,
        root.h,
    )


def render_app() -> None:
    """Temporarily replace only V26's CFB dispatch, then restore it exactly."""
    original = prior._render_nfl_or_cfb_v26
    prior._render_nfl_or_cfb_v26 = _render_nfl_or_cfb_v27
    try:
        prior.render_app()
    finally:
        prior._render_nfl_or_cfb_v26 = original


__all__ = [
    "CFB_MARKETS",
    "CFB_SPORT_LABEL",
    "FROZEN_ROUTER",
    "MODEL_VERSION",
    "MONEYLINE_MARKET",
    "_render_nfl_or_cfb_v27",
    "render_app",
]
