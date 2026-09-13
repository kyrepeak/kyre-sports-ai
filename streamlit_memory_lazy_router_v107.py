"""KYRE Streamlit Router V107 — Rushing Yards HTML render repair.

V107 is additive over certified performance Router V106. It preserves V106 for
all routing behavior and changes only the active NFL -> Rushing Yards page owner
from V10 to display-only V11 while rendering. Every non-Rushing route remains
owned by frozen V106/V105 history.
"""
from __future__ import annotations

import streamlit_memory_lazy_router_v106 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V107 • NFL RUSHING YARDS HTML RENDER REPAIR"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v106"
ACTIVE_PAGE = "nfl_rushing_yards_hub_v11"
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
