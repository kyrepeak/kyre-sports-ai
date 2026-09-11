"""KYRE Streamlit Router V85 — NFL Passing Yards Step 5 personnel route.

Additive wrapper over Router V84. Preserves every existing sport/market route,
changing only NFL -> Passing Yards to use NFL Hub V2.4 / Passing Yards V6.
"""
from __future__ import annotations

import streamlit_memory_lazy_router_v1 as root
import streamlit_memory_lazy_router_v84 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V85 • NFL PASSING YARDS STEP 5 PERSONNEL"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v84"
ACTIVE_NFL_HUB = "nfl_hub_v24"
PASSING_YARDS_MARKET = "Passing Yards"

_ORIGINAL_RENDER_NFL = root._render_nfl


def record_bootstrap_import_ms(value: float) -> None:
    prior.record_bootstrap_import_ms(value)


def _render_nfl_v85(market: str) -> None:
    market = str(market or "Slate")
    if market != PASSING_YARDS_MARKET:
        return _ORIGINAL_RENDER_NFL(market)
    mod = root._import(ACTIVE_NFL_HUB)
    return mod.render_nfl_hub(market)


def render_app() -> None:
    original_render_nfl = root._render_nfl
    root._render_nfl = _render_nfl_v85
    try:
        return prior.render_app()
    finally:
        root._render_nfl = original_render_nfl


__all__ = [
    "ACTIVE_NFL_HUB",
    "FROZEN_ROUTER",
    "MODEL_VERSION",
    "PASSING_YARDS_MARKET",
    "_render_nfl_v85",
    "record_bootstrap_import_ms",
    "render_app",
]
