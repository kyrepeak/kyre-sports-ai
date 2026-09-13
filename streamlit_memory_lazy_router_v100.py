"""KYRE Streamlit Router V100 — Rushing Yards Page Build Step 1.

Certified Router V99 remains frozen as the Step 4 owner. V100 temporarily
replaces V99's NFL handler only long enough to intercept the exact
``Rushing Yards`` market and route it to additive V4 compact player cards.
Every other market delegates to the original V99 handler unchanged.
"""
from __future__ import annotations

import streamlit_memory_lazy_router_v1 as root
import streamlit_memory_lazy_router_v99 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V100 • NFL RUSHING YARDS PAGE STEP 1 COMPACT PLAYER CARDS"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v99"
PRECEDENCE_ANCHOR = "streamlit_memory_lazy_router_v99._render_nfl_v99"
ACTIVE_RUSHING_YARDS_HUB = "nfl_rushing_yards_hub_v4"
RUSHING_YARDS_MARKET = "Rushing Yards"

_PRIOR_RENDER_NFL = prior._render_nfl_v99


def record_bootstrap_import_ms(value: float) -> None:
    prior.record_bootstrap_import_ms(value)


def _render_nfl_v100(market: str) -> None:
    market = str(market or "Slate")
    if market == RUSHING_YARDS_MARKET:
        mod = root._import(ACTIVE_RUSHING_YARDS_HUB)
        return mod.render_nfl_hub(market)
    return _PRIOR_RENDER_NFL(market)


def render_app() -> None:
    original_v99_handler = prior._render_nfl_v99
    prior._render_nfl_v99 = _render_nfl_v100
    try:
        return prior.render_app()
    finally:
        prior._render_nfl_v99 = original_v99_handler


__all__ = [
    "ACTIVE_RUSHING_YARDS_HUB",
    "FROZEN_ROUTER",
    "MODEL_VERSION",
    "PRECEDENCE_ANCHOR",
    "RUSHING_YARDS_MARKET",
    "_render_nfl_v100",
    "record_bootstrap_import_ms",
    "render_app",
]
