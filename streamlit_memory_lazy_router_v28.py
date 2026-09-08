"""KYRE Streamlit Router V28 — CFB mixed-division schedule/data hotfix.

Additive wrapper over permanently frozen Router V27.

Only College Football -> Moneyline advances to cfb_moneyline_hub_v3 so the
existing frozen Step-5 model can see verified FBS-vs-FCS crossover games.
Every other route delegates through Router V27 unchanged.
"""
from __future__ import annotations

import streamlit as st

import streamlit_memory_lazy_router_v27 as prior
import streamlit_memory_lazy_router_v1 as root

MODEL_VERSION = "KYRE STREAMLIT ROUTER V28 • CFB mixed-division hotfix"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v27"
CFB_SPORT_LABEL = prior.CFB_SPORT_LABEL
CFB_MARKETS = prior.CFB_MARKETS
MONEYLINE_MARKET = "Moneyline"

_FROZEN_RENDER_NFL_OR_CFB = prior._render_nfl_or_cfb_v27


def _render_nfl_or_cfb_v28(market: str) -> None:
    sport = str(st.session_state.get("ks_sport_touch") or "")
    if sport != CFB_SPORT_LABEL or market != MONEYLINE_MARKET:
        return _FROZEN_RENDER_NFL_OR_CFB(market)

    mod = root._import("cfb_moneyline_hub_v3")
    mod.render_cfb_hub(
        market,
        root.section_header,
        root.status_info,
        root.team_logo,
        root.h,
    )


def render_app() -> None:
    original = prior._render_nfl_or_cfb_v27
    prior._render_nfl_or_cfb_v27 = _render_nfl_or_cfb_v28
    try:
        prior.render_app()
    finally:
        prior._render_nfl_or_cfb_v27 = original


__all__ = [
    "CFB_MARKETS",
    "CFB_SPORT_LABEL",
    "FROZEN_ROUTER",
    "MODEL_VERSION",
    "MONEYLINE_MARKET",
    "_render_nfl_or_cfb_v28",
    "render_app",
]
