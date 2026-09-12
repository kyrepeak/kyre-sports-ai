"""KYRE Streamlit Router V97 — NFL Passing Yards early-season bridge.

V96 owns the active precedence hotfix and, during render, installs its module
symbol `_render_nfl_v96` into V91's overwrite point. V97 therefore temporarily
replaces that exact V96 symbol with the V97 handler before delegating to V96.
This preserves the certified precedence fix while advancing only Passing Yards
to NFL Hub V3.5 / Passing Yards V17.
"""
from __future__ import annotations

import streamlit_memory_lazy_router_v1 as root
import streamlit_memory_lazy_router_v96 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V97 • NFL PASSING YARDS EARLY SEASON BRIDGE"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v96"
PRECEDENCE_ANCHOR = "streamlit_memory_lazy_router_v96._render_nfl_v96"
ACTIVE_NFL_HUB = "nfl_hub_v35"
PASSING_YARDS_MARKET = "Passing Yards"

_ORIGINAL_RENDER_NFL = root._render_nfl


def record_bootstrap_import_ms(value: float) -> None:
    prior.record_bootstrap_import_ms(value)


def _render_nfl_v97(market: str) -> None:
    market = str(market or "Slate")
    if market != PASSING_YARDS_MARKET:
        return _ORIGINAL_RENDER_NFL(market)
    mod = root._import(ACTIVE_NFL_HUB)
    return mod.render_nfl_hub(market)


def render_app() -> None:
    # V96 installs its own handler symbol into the proven V91 overwrite point.
    # Replace that symbol temporarily so V96 installs V97 instead.
    original_v96_handler = prior._render_nfl_v96
    prior._render_nfl_v96 = _render_nfl_v97
    try:
        return prior.render_app()
    finally:
        prior._render_nfl_v96 = original_v96_handler


__all__ = [
    "ACTIVE_NFL_HUB",
    "FROZEN_ROUTER",
    "MODEL_VERSION",
    "PASSING_YARDS_MARKET",
    "PRECEDENCE_ANCHOR",
    "_render_nfl_v97",
    "record_bootstrap_import_ms",
    "render_app",
]
