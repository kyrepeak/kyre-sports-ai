"""KYRE Streamlit Router V110 — Rushing detailed stack tiers and sorting.

V110 is additive over certified Router V109. It preserves every V109 routing
behavior and advances only NFL -> Rushing Yards from V13 to display-only V14.
"""
from __future__ import annotations

import streamlit_memory_lazy_router_v109 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V110 • NFL RUSHING DETAILED STACK TIERS"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v109"
ACTIVE_PAGE = "nfl_rushing_yards_hub_v14"
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
