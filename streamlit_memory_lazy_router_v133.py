"""KYRE Streamlit Router V133 — NFL Spread matchup-board presentation.

V133 is additive over certified Router V132. It preserves V132's exact Spread
route/query behavior and changes only the active NFL -> Spread page owner from
V1 transport presentation to V2 matchup-board presentation. All non-Spread
routes continue through frozen V132 -> V131 unchanged.
"""
from __future__ import annotations

import streamlit_memory_lazy_router_v132 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V133 • NFL SPREAD MATCHUP BOARD"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v132"
ACTIVE_SPREAD_HUB = "nfl_spread_hub_v2"
SPREAD_MARKET = prior.SPREAD_MARKET
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
PROJECTION_MODEL_ENABLED = False
MONTE_CARLO_ENABLED = False
STAKE_SIZING_ENABLED = False
WAGER_ACTIONS_ENABLED = False


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def render_app() -> None:
    original_active_hub = prior.ACTIVE_SPREAD_HUB
    prior.ACTIVE_SPREAD_HUB = ACTIVE_SPREAD_HUB
    try:
        return prior.render_app()
    finally:
        prior.ACTIVE_SPREAD_HUB = original_active_hub


__all__ = [
    "ACTIVE_SPREAD_HUB",
    "FROZEN_ROUTER",
    "MODEL_VERSION",
    "MONTE_CARLO_ENABLED",
    "PROJECTION_MODEL_ENABLED",
    "SPREAD_MARKET",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "WAGER_ACTIONS_ENABLED",
    "record_bootstrap_import_ms",
    "render_app",
]
