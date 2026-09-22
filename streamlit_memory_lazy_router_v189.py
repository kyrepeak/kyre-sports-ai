"""KYRE Streamlit Router V189 — universal Moneyline presentation route.

Additive over frozen V188. Passing Yards remains owned by V188/V45.
Only active NFL Moneyline temporarily advances Router V131's Moneyline hub
from frozen V12 to presentation-only V13.
"""
from __future__ import annotations

import streamlit_memory_lazy_router_v131 as moneyline_router
import streamlit_memory_lazy_router_v188 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V189 • NFL MONEYLINE UNIVERSAL THEME"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v188"
MONEYLINE_MARKET = "Moneyline"
MONEYLINE_HUB = "nfl_moneyline_hub_v13"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False

def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)

def _active_market() -> str:
    return prior._active_market()

def render_app() -> None:
    if _active_market() != MONEYLINE_MARKET:
        return prior.render_app()
    original = moneyline_router.ACTIVE_MONEYLINE_HUB
    moneyline_router.ACTIVE_MONEYLINE_HUB = MONEYLINE_HUB
    try:
        return prior.render_app()
    finally:
        moneyline_router.ACTIVE_MONEYLINE_HUB = original

__all__ = [
    "FROZEN_ROUTER",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "MONEYLINE_HUB",
    "MONEYLINE_MARKET",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_active_market",
    "record_bootstrap_import_ms",
    "render_app",
]
