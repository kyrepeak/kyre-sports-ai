"""KYRE Streamlit Router V81 — NFL Passing Yards Step 1 identity route.

Additive wrapper over Router V80. It preserves every existing sport/market route,
changing only NFL -> Passing Yards to use NFL Hub V2.0 / Passing Yards V2.
"""
from __future__ import annotations

import streamlit_memory_lazy_router_v1 as root
import streamlit_memory_lazy_router_v80 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V81 • NFL PASSING YARDS STEP 1 IDENTITY"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v80"
ACTIVE_NFL_HUB = "nfl_hub_v20"
PASSING_YARDS_MARKET = "Passing Yards"

_ORIGINAL_RENDER_NFL = root._render_nfl


def record_bootstrap_import_ms(value: float) -> None:
    prior.record_bootstrap_import_ms(value)


def _render_nfl_v81(market: str) -> None:
    market = str(market or "Slate")
    if market != PASSING_YARDS_MARKET:
        return _ORIGINAL_RENDER_NFL(market)
    mod = root._import(ACTIVE_NFL_HUB)
    return mod.render_nfl_hub(market)


def render_app() -> None:
    original_render_nfl = root._render_nfl
    root._render_nfl = _render_nfl_v81
    try:
        return prior.render_app()
    finally:
        root._render_nfl = original_render_nfl


__all__ = [
    "ACTIVE_NFL_HUB",
    "FROZEN_ROUTER",
    "MODEL_VERSION",
    "PASSING_YARDS_MARKET",
    "_render_nfl_v81",
    "record_bootstrap_import_ms",
    "render_app",
]
