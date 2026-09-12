"""KYRE Streamlit Router V90 — NFL Passing Yards Step 10 final route.

Additive wrapper over Router V89. Preserves every existing sport/market route,
changing only NFL -> Passing Yards to use NFL Hub V2.9 / Passing Yards V11.
"""
from __future__ import annotations

import streamlit_memory_lazy_router_v1 as root
import streamlit_memory_lazy_router_v89 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V90 • NFL PASSING YARDS STEP 10 MARKET EDGE FINAL"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v89"
ACTIVE_NFL_HUB = "nfl_hub_v29"
PASSING_YARDS_MARKET = "Passing Yards"

_ORIGINAL_RENDER_NFL = root._render_nfl


def record_bootstrap_import_ms(value: float) -> None:
    prior.record_bootstrap_import_ms(value)


def _render_nfl_v90(market: str) -> None:
    market = str(market or "Slate")
    if market != PASSING_YARDS_MARKET:
        return _ORIGINAL_RENDER_NFL(market)
    mod = root._import(ACTIVE_NFL_HUB)
    return mod.render_nfl_hub(market)


def render_app() -> None:
    original_render_nfl = root._render_nfl
    root._render_nfl = _render_nfl_v90
    try:
        return prior.render_app()
    finally:
        root._render_nfl = original_render_nfl


__all__ = [
    "ACTIVE_NFL_HUB",
    "FROZEN_ROUTER",
    "MODEL_VERSION",
    "PASSING_YARDS_MARKET",
    "_render_nfl_v90",
    "record_bootstrap_import_ms",
    "render_app",
]
