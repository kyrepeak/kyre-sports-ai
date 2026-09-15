"""KYRE Streamlit Router V136 — standalone NFL Spread V4 fast route.

V136 is additive over certified Router V135. It preserves V132's exact NFL ->
Spread route/query behavior and V135's purge-safe V4 HTML guard, while removing
the active Spread route's dependency on the V134 -> V133 owner-swap ladder.
Every non-Spread route continues through frozen V135 unchanged.

V135, V4 analytics, the independent projection model, deterministic 5M Monte
Carlo, market transport, exact event identity, and every safety flag remain
frozen. Sportsbook projection influence stays exactly 0.0%.
"""
from __future__ import annotations

from typing import Any, Callable

import streamlit_memory_lazy_router_v132 as route_v132
import streamlit_memory_lazy_router_v135 as frozen


MODEL_VERSION = "KYRE STREAMLIT ROUTER V136 • NFL SPREAD STANDALONE V4 FAST ROUTE"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v135"
ACTIVE_SPREAD_HUB = frozen.ACTIVE_SPREAD_HUB
SPREAD_MARKET = route_v132.SPREAD_MARKET
ROUTE_QUERY_SPORT = route_v132.ROUTE_QUERY_SPORT
ROUTE_QUERY_MARKET = route_v132.ROUTE_QUERY_MARKET
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
PROJECTION_MODEL_ENABLED = True
MONTE_CARLO_ENABLED = True
STAKE_SIZING_ENABLED = False
WAGER_ACTIONS_ENABLED = False
HTML_RENDER_GUARD = frozen.HTML_RENDER_GUARD
HTML_RENDER_GUARD_SCOPE = frozen.HTML_RENDER_GUARD_SCOPE
STANDALONE_SPREAD_ROUTE = True


def record_bootstrap_import_ms(value: float) -> None:
    return frozen.record_bootstrap_import_ms(value)


def _guard_route_import(importer: Callable[[str], Any], name: str) -> Any:
    """Reuse V135's certified purge-safe V4 guard without rewriting it."""
    return frozen._guard_route_import(importer, name)


def _render_direct_spread() -> None:
    """Render exact NFL -> Spread directly through V132's certified fast route."""
    original_active_hub = route_v132.ACTIVE_SPREAD_HUB
    original_route_import = route_v132.root._import

    def guarded_route_import(name: str) -> Any:
        return _guard_route_import(original_route_import, name)

    route_v132.ACTIVE_SPREAD_HUB = ACTIVE_SPREAD_HUB
    route_v132.root._import = guarded_route_import
    try:
        return route_v132._render_direct_spread()
    finally:
        route_v132.root._import = original_route_import
        route_v132.ACTIVE_SPREAD_HUB = original_active_hub


def render_app() -> None:
    """Own exact NFL -> Spread; delegate every other route to frozen V135."""
    if not route_v132._fast_route_active():
        route_v132._restore_spread_route_from_query()
    if route_v132._fast_route_active():
        return _render_direct_spread()
    return frozen.render_app()


__all__ = [
    "ACTIVE_SPREAD_HUB",
    "FROZEN_ROUTER",
    "HTML_RENDER_GUARD",
    "HTML_RENDER_GUARD_SCOPE",
    "MODEL_VERSION",
    "MONTE_CARLO_ENABLED",
    "PROJECTION_MODEL_ENABLED",
    "ROUTE_QUERY_MARKET",
    "ROUTE_QUERY_SPORT",
    "SPREAD_MARKET",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "STANDALONE_SPREAD_ROUTE",
    "WAGER_ACTIONS_ENABLED",
    "record_bootstrap_import_ms",
    "render_app",
]
