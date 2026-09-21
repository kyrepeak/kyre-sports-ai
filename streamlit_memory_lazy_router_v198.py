"""KYRE Streamlit Router V198 — NFL Moneyline visual upgrade Step 2.

Additive over frozen V197. Only active NFL Moneyline advances from V14 to
presentation-only V15. Every unrelated route remains delegated to V197.
"""
from __future__ import annotations

import streamlit_memory_lazy_router_v197 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V198 • NFL MONEYLINE VISUAL STEP 2"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v197"
MONEYLINE_MARKET = "Moneyline"
MONEYLINE_HUB = "nfl_moneyline_hub_v15"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
PRESENTATION_ONLY = True

def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)

def _active_route() -> tuple[str, str]:
    return prior._active_route()

def render_app() -> None:
    sport, market = _active_route()
    if sport != "NFL" or market != MONEYLINE_MARKET:
        return prior.render_app()

    # V197 is the frozen Step 1 owner. Override its hub selector so its own
    # render_app forwards V15 into the V189 Moneyline owner. This prevents the
    # nested V197 render from overwriting Step 2 back to V14.
    original = prior.MONEYLINE_HUB
    prior.MONEYLINE_HUB = MONEYLINE_HUB
    try:
        return prior.render_app()
    finally:
        prior.MONEYLINE_HUB = original

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
