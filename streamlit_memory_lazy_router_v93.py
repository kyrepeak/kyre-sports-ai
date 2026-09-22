"""KYRE Streamlit Router V93 — NFL Passing Yards cleanup step 2.

Additive wrapper over certified Router V92. It preserves the V91/V92 deepest-
handler precedence fix and advances only NFL -> Passing Yards to NFL Hub V3.2.
All other sport/market routes remain delegated to V92.
"""
from __future__ import annotations

import streamlit_memory_lazy_router_v1 as root
import streamlit_memory_lazy_router_v80 as deepest_nfl_router
import streamlit_memory_lazy_router_v92 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V93 • NFL PASSING YARDS CLEANUP STEP 2"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v92"
PRECEDENCE_ANCHOR = "streamlit_memory_lazy_router_v80._render_nfl_v80"
ACTIVE_NFL_HUB = "nfl_hub_v32"
PASSING_YARDS_MARKET = "Passing Yards"

_ORIGINAL_RENDER_NFL = root._render_nfl


def record_bootstrap_import_ms(value: float) -> None:
    prior.record_bootstrap_import_ms(value)


def _render_nfl_v93(market: str) -> None:
    market = str(market or "Slate")
    if market != PASSING_YARDS_MARKET:
        return _ORIGINAL_RENDER_NFL(market)
    mod = root._import(ACTIVE_NFL_HUB)
    return mod.render_nfl_hub(market)


def render_app() -> None:
    original_deepest_handler = deepest_nfl_router._render_nfl_v80
    deepest_nfl_router._render_nfl_v80 = _render_nfl_v93
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
    "_render_nfl_v93",
    "record_bootstrap_import_ms",
    "render_app",
]
