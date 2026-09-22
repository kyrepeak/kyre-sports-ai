"""KYRE Streamlit Router V190 — CFB Game Total universal theme route.

Additive over frozen V189. Moneyline remains owned by V189/V13, Passing Yards
by V188/V45. Only the exact active CFB Game Total page advances V181's page
binding from frozen V33 to presentation-only V34.
"""
from __future__ import annotations

import streamlit_memory_lazy_router_v181 as game_total_router
import streamlit_memory_lazy_router_v189 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V190 • CFB GAME TOTAL UNIVERSAL THEME"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v189"
GAME_TOTAL_PAGE = "cfb_game_total_clean_page_v34"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False

def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)

def render_app() -> None:
    if not game_total_router._game_total_route_active():
        return prior.render_app()
    original = game_total_router.ACTIVE_PAGE
    game_total_router.ACTIVE_PAGE = GAME_TOTAL_PAGE
    try:
        return prior.render_app()
    finally:
        game_total_router.ACTIVE_PAGE = original

__all__ = [
    "FROZEN_ROUTER",
    "GAME_TOTAL_PAGE",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "record_bootstrap_import_ms",
    "render_app",
]
