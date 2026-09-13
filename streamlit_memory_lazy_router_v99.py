"""KYRE Streamlit Router V99 — NFL Rushing Yards Step 4 additive route.

Certified Router V98 remains frozen as the Step 3 owner. V99 temporarily
replaces V98's NFL handler only long enough to intercept the exact
``Rushing Yards`` market and route it to the additive V3 Step 4 page. Every
other market delegates to the original V98 handler and therefore preserves the
entire V98 -> V97 chain unchanged.

No Passing Yards, Rushing Step 3 projection math, probability, EV, grading,
CFB, or other sport logic is changed here. The live market layer is strictly
post-projection and sportsbook projection influence remains 0.0%.
"""
from __future__ import annotations

import streamlit_memory_lazy_router_v1 as root
import streamlit_memory_lazy_router_v98 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V99 • NFL RUSHING YARDS STEP 4 MARKET CONTEXT TARGET"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v98"
PRECEDENCE_ANCHOR = "streamlit_memory_lazy_router_v98._render_nfl_v98"
ACTIVE_RUSHING_YARDS_HUB = "nfl_rushing_yards_hub_v3"
RUSHING_YARDS_MARKET = "Rushing Yards"

_PRIOR_RENDER_NFL = prior._render_nfl_v98


def record_bootstrap_import_ms(value: float) -> None:
    prior.record_bootstrap_import_ms(value)


def _render_nfl_v99(market: str) -> None:
    market = str(market or "Slate")
    if market == RUSHING_YARDS_MARKET:
        mod = root._import(ACTIVE_RUSHING_YARDS_HUB)
        return mod.render_nfl_hub(market)
    return _PRIOR_RENDER_NFL(market)


def render_app() -> None:
    original_v98_handler = prior._render_nfl_v98
    prior._render_nfl_v98 = _render_nfl_v99
    try:
        return prior.render_app()
    finally:
        prior._render_nfl_v98 = original_v98_handler


__all__ = [
    "ACTIVE_RUSHING_YARDS_HUB",
    "FROZEN_ROUTER",
    "MODEL_VERSION",
    "PRECEDENCE_ANCHOR",
    "RUSHING_YARDS_MARKET",
    "_render_nfl_v99",
    "record_bootstrap_import_ms",
    "render_app",
]
