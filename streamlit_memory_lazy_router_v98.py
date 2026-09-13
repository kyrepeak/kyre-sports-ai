"""KYRE Streamlit Router V98 — NFL Rushing Yards additive route.

V97 remains the certified Passing Yards owner. V98 is additive: it temporarily
replaces V97's handler symbol only long enough to intercept Rushing Yards and
route that market to the active isolated Rushing Yards page. Every other NFL
market delegates back to V97's original handler, preserving Passing Yards and
the established router chain exactly.

Step 4 advances only the Rushing Yards target from V2 to V3. No Passing Yards,
projection math, probability, EV, grading, CFB, or other sport logic is changed
here. The V3 market layer remains post-projection context only and sportsbook
projection influence remains 0.0%.
"""
from __future__ import annotations

import streamlit_memory_lazy_router_v1 as root
import streamlit_memory_lazy_router_v97 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V98 • NFL RUSHING YARDS STEP 4 MARKET CONTEXT TARGET"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v97"
PRECEDENCE_ANCHOR = "streamlit_memory_lazy_router_v97._render_nfl_v97"
ACTIVE_RUSHING_YARDS_HUB = "nfl_rushing_yards_hub_v3"
RUSHING_YARDS_MARKET = "Rushing Yards"

_PRIOR_RENDER_NFL = prior._render_nfl_v97


def record_bootstrap_import_ms(value: float) -> None:
    prior.record_bootstrap_import_ms(value)


def _render_nfl_v98(market: str) -> None:
    market = str(market or "Slate")
    if market == RUSHING_YARDS_MARKET:
        mod = root._import(ACTIVE_RUSHING_YARDS_HUB)
        return mod.render_nfl_hub(market)
    return _PRIOR_RENDER_NFL(market)


def render_app() -> None:
    # V97 is the certified owner directly above this additive route. Replace
    # only its handler symbol for the duration of one render, then restore it.
    original_v97_handler = prior._render_nfl_v97
    prior._render_nfl_v97 = _render_nfl_v98
    try:
        return prior.render_app()
    finally:
        prior._render_nfl_v97 = original_v97_handler


__all__ = [
    "ACTIVE_RUSHING_YARDS_HUB",
    "FROZEN_ROUTER",
    "MODEL_VERSION",
    "PRECEDENCE_ANCHOR",
    "RUSHING_YARDS_MARKET",
    "_render_nfl_v98",
    "record_bootstrap_import_ms",
    "render_app",
]
