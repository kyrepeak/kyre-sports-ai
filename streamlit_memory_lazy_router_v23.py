"""KYRE Streamlit Router V23 — College Football Step 1 foundation.

Additive wrapper over permanently frozen Router V22.

This router introduces a fourth sport option, `College Football`, with three
initial isolated pages:
- Moneyline
- Over/Under
- Game Total

The existing V1 shell hard-codes MLB/WNBA/NFL. Rather than editing that frozen
router, V23 temporarily adapts only the sport/market selectboxes and the NFL
fallback dispatch used by the frozen shell's final `else` branch.

Every existing MLB/WNBA/NFL route continues through Router V22 unchanged.
"""
from __future__ import annotations

import streamlit as st

import streamlit_memory_lazy_router_v22 as prior
import streamlit_memory_lazy_router_v1 as root
import cfb_hub_v1 as cfb

MODEL_VERSION = "KYRE STREAMLIT ROUTER V23 • CFB Step 1"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v22"

CFB_SPORT_LABEL = "College Football"
CFB_MARKETS = tuple(cfb.CFB_MARKETS)

_ORIGINAL_SELECTBOX = root.st.selectbox
_ORIGINAL_RENDER_NFL = root._render_nfl
_ORIGINAL_PREFIXES = root._ROUTE_MODULE_PREFIXES


def _selectbox_v23(label, options, *args, **kwargs):
    """Adapt only the frozen root sport/NFL-market selectors for CFB."""
    if label == "🏟️ Sport":
        choices = list(options)
        if CFB_SPORT_LABEL not in choices:
            choices.append(CFB_SPORT_LABEL)
        return _ORIGINAL_SELECTBOX(label, choices, *args, **kwargs)

    if (
        label == "🎯 NFL Market"
        and str(st.session_state.get("ks_sport_touch") or "") == CFB_SPORT_LABEL
    ):
        if str(st.session_state.get("ks_cfb_market_touch") or "") not in CFB_MARKETS:
            st.session_state.pop("ks_cfb_market_touch", None)

        clean_kwargs = dict(kwargs)
        clean_kwargs.pop("key", None)
        clean_kwargs.pop("index", None)
        return _ORIGINAL_SELECTBOX(
            "🎯 CFB Market",
            list(CFB_MARKETS),
            *args,
            key="ks_cfb_market_touch",
            **clean_kwargs,
        )

    return _ORIGINAL_SELECTBOX(label, options, *args, **kwargs)


def _render_nfl_or_cfb_v23(market: str) -> None:
    """Use the frozen root else-dispatch as CFB only when CFB is selected."""
    if str(st.session_state.get("ks_sport_touch") or "") != CFB_SPORT_LABEL:
        return _ORIGINAL_RENDER_NFL(market)

    mod = root._import("cfb_hub_v1")
    mod.render_cfb_hub(
        market,
        root.section_header,
        root.status_info,
        root.team_logo,
        root.h,
    )


def render_app() -> None:
    """Temporarily extend the frozen root shell, then restore it exactly."""
    original_selectbox = root.st.selectbox
    original_render_nfl = root._render_nfl
    original_prefixes = root._ROUTE_MODULE_PREFIXES

    root.st.selectbox = _selectbox_v23
    root._render_nfl = _render_nfl_or_cfb_v23
    if "cfb_" not in root._ROUTE_MODULE_PREFIXES:
        root._ROUTE_MODULE_PREFIXES = root._ROUTE_MODULE_PREFIXES + ("cfb_",)

    try:
        prior.render_app()
    finally:
        root.st.selectbox = original_selectbox
        root._render_nfl = original_render_nfl
        root._ROUTE_MODULE_PREFIXES = original_prefixes


__all__ = [
    "CFB_MARKETS",
    "CFB_SPORT_LABEL",
    "FROZEN_ROUTER",
    "MODEL_VERSION",
    "_render_nfl_or_cfb_v23",
    "_selectbox_v23",
    "render_app",
]
