"""KYRE Streamlit Router V92 — NFL Passing Yards cleanup step 1.

Additive wrapper over certified Router V91. It keeps the V91 deepest-handler
precedence fix intact and advances only NFL -> Passing Yards to NFL Hub V3.1.
All other sport/market routes remain delegated to V91.
"""
from __future__ import annotations

import streamlit_memory_lazy_router_v1 as root
import streamlit_memory_lazy_router_v80 as deepest_nfl_router
import streamlit_memory_lazy_router_v91 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V92 • NFL PASSING YARDS CLEANUP STEP 1"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v91"
PRECEDENCE_ANCHOR = "streamlit_memory_lazy_router_v80._render_nfl_v80"
ACTIVE_NFL_HUB = "nfl_hub_v31"
PASSING_YARDS_MARKET = "Passing Yards"

_ORIGINAL_RENDER_NFL = root._render_nfl


def record_bootstrap_import_ms(value: float) -> None:
    prior.record_bootstrap_import_ms(value)


def _render_nfl_v92(market: str) -> None:
    market = str(market or "Slate")
    if market != PASSING_YARDS_MARKET:
        return _ORIGINAL_RENDER_NFL(market)
    mod = root._import(ACTIVE_NFL_HUB)
    return mod.render_nfl_hub(market)


def render_app() -> None:
    original_deepest_handler = deepest_nfl_router._render_nfl_v80
    deepest_nfl_router._render_nfl_v80 = _render_nfl_v92
    try:
        return prior.render_app()
    finally:
        deepest_nfl_router._render_nfl_v80 = original_deepest_handler


__all__ = [
    "ACTIVE_NFL_HUB",
    "FROZEN_ROUTER",
    "MODEL_VERSION",
    "PASSING_YARDS_MARKET",
    "PRECEDENCE_ANCHOR",
    "_render_nfl_v92",
    "record_bootstrap_import_ms",
    "render_app",
]
