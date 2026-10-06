"""KYRE Streamlit Router V97 — NFL Passing Yards + Game Totals bridge.

V96 owns the active precedence hotfix and, during render, installs its module
symbol `_render_nfl_v96` into V91's overwrite point. V97 therefore temporarily
replaces that exact V96 symbol with the V97 handler before delegating to V96.
This preserves the certified precedence fix while advancing Passing Yards and
Game Total through the current NFL hub wrapper without changing other markets.
"""
from __future__ import annotations

import streamlit_memory_lazy_router_v1 as root
import streamlit_memory_lazy_router_v96 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V97 • NFL PASSING YARDS + GAME TOTALS BRIDGE"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v96"
PRECEDENCE_ANCHOR = "streamlit_memory_lazy_router_v96._render_nfl_v96"
ACTIVE_NFL_HUB = "nfl_hub_v36"
PASSING_YARDS_MARKET = "Passing Yards"
GAME_TOTAL_MARKET = "Game Total"

_ORIGINAL_RENDER_NFL = root._render_nfl


def record_bootstrap_import_ms(value: float) -> None:
    prior.record_bootstrap_import_ms(value)


def _render_nfl_v97(market: str) -> None:
    market = str(market or "Slate")
    if market not in {PASSING_YARDS_MARKET, GAME_TOTAL_MARKET}:
        return _ORIGINAL_RENDER_NFL(market)
    mod = root._import(ACTIVE_NFL_HUB)
    return mod.render_nfl_hub(market)


def render_app() -> None:
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
    "GAME_TOTAL_MARKET",
    "PRECEDENCE_ANCHOR",
    "_render_nfl_v97",
    "record_bootstrap_import_ms",
    "render_app",
]
