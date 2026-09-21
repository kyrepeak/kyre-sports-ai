"""KYRE Streamlit Router V188 — Passing Yards layered production route.

Additive over frozen V187. Only Passing Yards advances from V42 to V43.
Every other NFL market and every non-NFL route delegates to V187 unchanged.
"""
from __future__ import annotations

import streamlit_memory_lazy_router_v187 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V188 • PASSING YARDS LAYERED PRODUCTION"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v187"
PASSING_MARKET = "Passing Yards"
PASSING_HUB = "nfl_passing_yards_hub_v43"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def _active_market() -> str:
    return prior._active_market()


def _render_passing_v188():
    original = prior.PROP_HUBS.get(PASSING_MARKET)
    prior.PROP_HUBS[PASSING_MARKET] = PASSING_HUB
    try:
        return prior._render_direct_prop()
    finally:
        if original is None:
            prior.PROP_HUBS.pop(PASSING_MARKET, None)
        else:
            prior.PROP_HUBS[PASSING_MARKET] = original


def render_app() -> None:
    market = _active_market()
    if market == PASSING_MARKET:
        return _render_passing_v188()
    return prior.render_app()


__all__ = [
    "FROZEN_ROUTER",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "PASSING_HUB",
    "PASSING_MARKET",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_active_market",
    "_render_passing_v188",
    "record_bootstrap_import_ms",
    "render_app",
]
