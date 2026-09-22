"""KYRE Streamlit Router V109 — Rushing Yards matchup tiers and favorable-first sorting.

V109 is additive over certified Router V108. It preserves every V108 routing
behavior and changes only the active NFL -> Rushing Yards page owner from V12
to display-only V13. Every non-Rushing route remains owned by the frozen chain.
"""
from __future__ import annotations

import streamlit_memory_lazy_router_v108 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V109 • NFL RUSHING YARDS MATCHUP TIERS"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v108"
ACTIVE_PAGE = "nfl_rushing_yards_hub_v13"
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
