"""KYRE Streamlit Router V197 — NFL Moneyline visual upgrade Step 1.

Additive over frozen V196. Only active NFL Moneyline advances from V13 to
presentation-only V14. Every unrelated route remains delegated to V196.
"""
from __future__ import annotations

import streamlit_memory_lazy_router_v189 as moneyline_owner
import streamlit_memory_lazy_router_v196 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V197 • NFL MONEYLINE VISUAL STEP 1"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v196"
MONEYLINE_MARKET = "Moneyline"
MONEYLINE_HUB = "nfl_moneyline_hub_v14"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
PRESENTATION_ONLY = True

def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)

def _active_route() -> tuple[str, str]:
    return prior._active_route()

def render_app() -> None:
    # Follow the already-certified V189 Moneyline activation predicate so a
    # cold public deep link reaches V14 before session-state route touches exist.
    if moneyline_owner._active_market() != MONEYLINE_MARKET:
        return prior.render_app()

    original = moneyline_owner.MONEYLINE_HUB
    moneyline_owner.MONEYLINE_HUB = MONEYLINE_HUB
    try:
        return prior.render_app()
    finally:
        moneyline_owner.MONEYLINE_HUB = original

__all__ = [
    "FROZEN_ROUTER",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "MONEYLINE_HUB",
    "MONEYLINE_MARKET",
    "PRESENTATION_ONLY",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_active_route",
    "record_bootstrap_import_ms",
    "render_app",
]
