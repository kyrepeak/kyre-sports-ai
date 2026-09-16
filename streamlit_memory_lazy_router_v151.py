"""KYRE Streamlit Router V151 — CFB Game Total live recovery.

Additive over frozen Router V150. Only exact College Football -> Game Total is
advanced to the V151 recovery page. All other V150/V149/NFL routes are delegated
unchanged. Frozen Game Total formulas remain untouched and sportsbook projection
influence remains 0.0%.
"""
from __future__ import annotations

import streamlit_memory_lazy_router_v150 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V151 • CFB GAME TOTAL LIVE RECOVERY"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v150"
ACTIVE_PAGE = "cfb_game_total_monster_page_v2"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def render_app() -> None:
    """Delegate V150 routing while swapping only the exact Game Total page."""
    frozen_page = prior.ACTIVE_PAGE
    prior.ACTIVE_PAGE = ACTIVE_PAGE
    try:
        return prior.render_app()
    finally:
        prior.ACTIVE_PAGE = frozen_page


__all__ = [
    "ACTIVE_PAGE",
    "FROZEN_ROUTER",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "record_bootstrap_import_ms",
    "render_app",
]
