"""KYRE Streamlit Router V108 — full FanDuel Rushing Yards lineup board.

V108 is additive over certified Router V107. It preserves every V107 routing
behavior and changes only the active NFL -> Rushing Yards page owner from V11
to display-only V12. Every non-Rushing route remains owned by the frozen chain.
"""
from __future__ import annotations

import streamlit_memory_lazy_router_v107 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V108 • NFL RUSHING YARDS FANDUEL FULL LINEUP"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v107"
ACTIVE_PAGE = "nfl_rushing_yards_hub_v12"
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
