"""KYRE Streamlit Router V199 — NFL Moneyline visual upgrade Step 3.

Additive over frozen V198. Only active NFL Moneyline advances from V15 to
presentation-only V16. Every unrelated route remains delegated to V198.
"""
from __future__ import annotations

import streamlit_memory_lazy_router_v198 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V199 • NFL MONEYLINE VISUAL STEP 3"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v198"
MONEYLINE_MARKET = "Moneyline"
MONEYLINE_HUB = "nfl_moneyline_hub_v16"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
PRESENTATION_ONLY = True


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def _active_route() -> tuple[str, str]:
    return prior._active_route()


def render_app() -> None:
    sport, market = _active_route()
    if sport != "NFL" or market != MONEYLINE_MARKET:
        return prior.render_app()

    # V198 is the frozen Step 2 owner. Override its selector only for the
    # active NFL Moneyline route so nested routing forwards V16 into V197/V189.
    original = prior.MONEYLINE_HUB
    prior.MONEYLINE_HUB = MONEYLINE_HUB
    try:
        return prior.render_app()
    finally:
        prior.MONEYLINE_HUB = original


__all__ = [
    "FROZEN_ROUTER",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "MONEYLINE_HUB",
    "MONEYLINE_MARKET",
    "PRESENTATION_ONLY",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_active_route",
    "record_bootstrap_import_ms",
    "render_app",
]
