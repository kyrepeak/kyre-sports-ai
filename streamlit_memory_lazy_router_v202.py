"""KYRE Streamlit Router V202 — Passing Yards universal theme ownership Step 1.

Additive over frozen V201. Only active NFL Passing Yards advances from frozen
V50 to presentation-only V51. NFL Moneyline and every unrelated route continue
through V201 unchanged.
"""
from __future__ import annotations

import streamlit_memory_lazy_router_v201 as prior
import streamlit_memory_lazy_router_v196 as passing_owner

MODEL_VERSION = "KYRE STREAMLIT ROUTER V202 • PASSING YARDS UNIVERSAL OWNER STEP 1"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v201"
FROZEN_PASSING_ROUTER = "streamlit_memory_lazy_router_v196"
PASSING_MARKET = "Passing Yards"
PASSING_HUB = "nfl_passing_yards_hub_v51"
PRESENTATION_ONLY = True
MAY_MODIFY_PROJECTION = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def _active_route() -> tuple[str, str]:
    return prior._active_route()


def render_app() -> None:
    sport, market = _active_route()
    if sport != "NFL" or market != PASSING_MARKET:
        return prior.render_app()

    original = passing_owner.PASSING_HUB
    passing_owner.PASSING_HUB = PASSING_HUB
    try:
        return prior.render_app()
    finally:
        passing_owner.PASSING_HUB = original


__all__ = [
    "FROZEN_PASSING_ROUTER",
    "FROZEN_ROUTER",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "PASSING_HUB",
    "PASSING_MARKET",
    "PRESENTATION_ONLY",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_active_route",
    "record_bootstrap_import_ms",
    "render_app",
]
