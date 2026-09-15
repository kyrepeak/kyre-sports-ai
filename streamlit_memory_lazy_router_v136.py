"""KYRE Streamlit Router V136 — fresh standalone NFL Spread V4 fast route.

V136 preserves V132's exact NFL -> Spread route/query behavior and V135's
certified purge-safe V4 HTML presentation guard, but deliberately reimplements
that tiny presentation-only guard inside a brand-new router module. The active
NFL -> Spread path never imports or dereferences V135, so a stale V135 object in
``sys.modules`` cannot preserve the raw-HTML bug after deployment.

Every non-Spread route lazy-delegates to frozen V135 unchanged. V4 analytics,
the independent projection model, deterministic 5M Monte Carlo, market
transport, exact event identity, and every safety flag remain frozen.
Sportsbook projection influence stays exactly 0.0%.
"""
from __future__ import annotations

import importlib
from typing import Any, Callable

import nfl_spread_hub_v4 as spread_v4
import streamlit_memory_lazy_router_v132 as route_v132


MODEL_VERSION = "KYRE STREAMLIT ROUTER V136 • NFL SPREAD FRESH STANDALONE V4 ROUTE"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v135"
ACTIVE_SPREAD_HUB = "nfl_spread_hub_v4"
SPREAD_MARKET = route_v132.SPREAD_MARKET
ROUTE_QUERY_SPORT = route_v132.ROUTE_QUERY_SPORT
ROUTE_QUERY_MARKET = route_v132.ROUTE_QUERY_MARKET
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
PROJECTION_MODEL_ENABLED = True
MONTE_CARLO_ENABLED = True
STAKE_SIZING_ENABLED = False
WAGER_ACTIONS_ENABLED = False
HTML_RENDER_GUARD = "flatten_generated_html"
HTML_RENDER_GUARD_SCOPE = "route_purge_reimport_safe"
STANDALONE_SPREAD_ROUTE = True
ACTIVE_SPREAD_V135_DEPENDENCY = False


_RAW_MATCHUP_CARD = spread_v4._matchup_card
_RAW_SUMMARY_HTML = spread_v4._summary_html


def _flatten_generated_html(value: str) -> str:
    """Keep generated V4 markup out of Markdown's indented-code path."""
    return "".join(line.strip() for line in str(value or "").splitlines())


def _html_safe_matchup_card(*args, **kwargs) -> str:
    return _flatten_generated_html(_RAW_MATCHUP_CARD(*args, **kwargs))


def _html_safe_summary_html(*args, **kwargs) -> str:
    return _flatten_generated_html(_RAW_SUMMARY_HTML(*args, **kwargs))


def _install_html_guard(module: Any) -> Any:
    """Install the V4 presentation guard on initial and post-purge imports."""
    if getattr(module, "_KSP4_HTML_RENDER_GUARD", None) == HTML_RENDER_GUARD:
        return module

    if module is spread_v4:
        module._matchup_card = _html_safe_matchup_card
        module._summary_html = _html_safe_summary_html
    else:
        raw_matchup_card = module._matchup_card
        raw_summary_html = module._summary_html

        def safe_matchup_card(*args, **kwargs) -> str:
            return _flatten_generated_html(raw_matchup_card(*args, **kwargs))

        def safe_summary_html(*args, **kwargs) -> str:
            return _flatten_generated_html(raw_summary_html(*args, **kwargs))

        module._matchup_card = safe_matchup_card
        module._summary_html = safe_summary_html

    module._KSP4_HTML_RENDER_GUARD = HTML_RENDER_GUARD
    return module


def _guard_route_import(importer: Callable[[str], Any], name: str) -> Any:
    """Re-apply the V4 guard after V132/root purges NFL route modules."""
    module = importer(name)
    if str(name or "") == ACTIVE_SPREAD_HUB:
        return _install_html_guard(module)
    return module


def _load_frozen_non_spread() -> Any:
    """Lazy-load V135 only after V136 has proven the route is not NFL Spread."""
    return importlib.import_module(FROZEN_ROUTER)


# Protect the initial V4 import. The direct route also protects post-purge imports.
_install_html_guard(spread_v4)


def record_bootstrap_import_ms(value: float) -> None:
    # V132 owns the direct Spread cold-start telemetry used by this fast route.
    return route_v132.record_bootstrap_import_ms(value)


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
    """Own exact NFL -> Spread; lazy-delegate every other route to frozen V135."""
    if not route_v132._fast_route_active():
        route_v132._restore_spread_route_from_query()
    if route_v132._fast_route_active():
        return _render_direct_spread()
    return _load_frozen_non_spread().render_app()


__all__ = [
    "ACTIVE_SPREAD_HUB",
    "ACTIVE_SPREAD_V135_DEPENDENCY",
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
