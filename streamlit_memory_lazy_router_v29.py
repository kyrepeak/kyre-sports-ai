"""KYRE Streamlit Router V29 — CFB full FBS slate fallback.

Additive wrapper over permanently frozen Router V28.

Only College Football -> Moneyline advances to cfb_moneyline_hub_v4 so the
frozen Step-5 model can see the complete verified FBS-scoped Saturday slate.
Every other route delegates through Router V28 unchanged.
"""
from __future__ import annotations

import streamlit as st

import streamlit_memory_lazy_router_v28 as prior
import streamlit_memory_lazy_router_v1 as root

MODEL_VERSION = "KYRE STREAMLIT ROUTER V29 • CFB full FBS slate fallback"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v28"
CFB_SPORT_LABEL = prior.CFB_SPORT_LABEL
CFB_MARKETS = prior.CFB_MARKETS
MONEYLINE_MARKET = "Moneyline"

_FROZEN_RENDER_NFL_OR_CFB = prior._render_nfl_or_cfb_v28


def _render_nfl_or_cfb_v29(market: str) -> None:
    sport = str(st.session_state.get("ks_sport_touch") or "")
    if sport != CFB_SPORT_LABEL or market != MONEYLINE_MARKET:
        return _FROZEN_RENDER_NFL_OR_CFB(market)

    mod = root._import("cfb_moneyline_hub_v4")
    mod.render_cfb_hub(
        market,
        root.section_header,
        root.status_info,
        root.team_logo,
        root.h,
    )


def render_app() -> None:
    original = prior._render_nfl_or_cfb_v28
    prior._render_nfl_or_cfb_v28 = _render_nfl_or_cfb_v29
    try:
        prior.render_app()
    finally:
        prior._render_nfl_or_cfb_v28 = original


__all__ = [
    "CFB_MARKETS",
    "CFB_SPORT_LABEL",
    "FROZEN_ROUTER",
    "MODEL_VERSION",
    "MONEYLINE_MARKET",
    "_render_nfl_or_cfb_v29",
    "render_app",
]
