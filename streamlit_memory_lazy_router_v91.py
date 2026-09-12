"""KYRE Streamlit Router V91 — NFL Passing Yards route-precedence hotfix.

Routers V81–V90 wrapped V80 recursively and each temporarily replaced
``root._render_nfl`` before calling its predecessor. Because V80 is the deepest
NFL-specific wrapper, its original Passing Yards V1 handler was the final
assignment before the root app rendered. In production this made the compact
foundation page win even though V90 correctly named NFL Hub V2.9.

V91 fixes only that precedence problem without rewriting frozen predecessors:
during the existing V90 render chain, it temporarily replaces V80's deepest
Passing Yards handler with the current V91 handler. All other routing and every
certified model/protection remain preserved.
"""
from __future__ import annotations

import streamlit_memory_lazy_router_v1 as root
import streamlit_memory_lazy_router_v80 as deepest_nfl_router
import streamlit_memory_lazy_router_v90 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V91 • NFL PASSING YARDS ROUTE PRECEDENCE HOTFIX"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v90"
PRECEDENCE_ANCHOR = "streamlit_memory_lazy_router_v80._render_nfl_v80"
ACTIVE_NFL_HUB = "nfl_hub_v30"
PASSING_YARDS_MARKET = "Passing Yards"

_ORIGINAL_RENDER_NFL = root._render_nfl


def record_bootstrap_import_ms(value: float) -> None:
    prior.record_bootstrap_import_ms(value)


def _render_nfl_v91(market: str) -> None:
    market = str(market or "Slate")
    if market != PASSING_YARDS_MARKET:
        return _ORIGINAL_RENDER_NFL(market)
    mod = root._import(ACTIVE_NFL_HUB)
    return mod.render_nfl_hub(market)


def render_app() -> None:
    # V80 is the deepest router in the V80→V90 NFL Passing Yards wrapper chain.
    # Patching its handler (not the frozen file) makes the current handler the
    # final assignment seen by root.render_app, so V12 actually reaches users.
    original_deepest_handler = deepest_nfl_router._render_nfl_v80
    deepest_nfl_router._render_nfl_v80 = _render_nfl_v91
    try:
        return prior.render_app()
    finally:
        deepest_nfl_router._render_nfl_v80 = original_deepest_handler


__all__ = [
    "ACTIVE_NFL_HUB",
    "FROZEN_ROUTER",
    "MODEL_VERSION",
    "PASSING_YARDS_MARKET",
    "PRECEDENCE_ANCHOR",
    "_render_nfl_v91",
    "record_bootstrap_import_ms",
    "render_app",
]
