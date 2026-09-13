"""KYRE Streamlit Router V111 — Phoenix game-time display for Rushing Yards.

V111 is additive over certified Router V110. It preserves every V110 routing
behavior and advances only NFL -> Rushing Yards from V14 to display-only V15.
"""
from __future__ import annotations

import streamlit_memory_lazy_router_v110 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V111 • NFL RUSHING PHOENIX GAME TIMES"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v110"
ACTIVE_PAGE = "nfl_rushing_yards_hub_v15"
RUSHING_YARDS_MARKET = prior.RUSHING_YARDS_MARKET


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def render_app() -> None:
    original_active_page = prior.ACTIVE_PAGE
    prior.ACTIVE_PAGE = ACTIVE_PAGE
    try:
        return prior.render_app()
    finally:
        prior.ACTIVE_PAGE = original_active_page


__all__ = [
    "ACTIVE_PAGE",
    "FROZEN_ROUTER",
    "MODEL_VERSION",
    "RUSHING_YARDS_MARKET",
    "record_bootstrap_import_ms",
    "render_app",
]
