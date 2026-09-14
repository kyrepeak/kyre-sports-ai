"""KYRE Streamlit Router V135 — NFL Spread visual-parity matchup board.

V135 is additive over certified Router V134. It preserves V134's exact Spread
route/query behavior, independent fair-margin model, deterministic 5M Monte
Carlo, and all safety flags while changing only the active NFL -> Spread page
owner from V3 to V4 visual-parity presentation. All non-Spread routes continue
through frozen V134 -> V133 -> V132 -> V131 unchanged.
"""
from __future__ import annotations

import streamlit_memory_lazy_router_v134 as prior


MODEL_VERSION = "KYRE STREAMLIT ROUTER V135 • NFL SPREAD V4 VISUAL PARITY"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v134"
ACTIVE_SPREAD_HUB = "nfl_spread_hub_v4"
SPREAD_MARKET = prior.SPREAD_MARKET
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
PROJECTION_MODEL_ENABLED = True
MONTE_CARLO_ENABLED = True
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
