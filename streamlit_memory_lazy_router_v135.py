"""KYRE Streamlit Router V135 — NFL Spread visual-parity matchup board.

V135 is additive over certified Router V134. It preserves V134's exact Spread
route/query behavior, independent fair-margin model, deterministic 5M Monte
Carlo, and all safety flags while changing only the active NFL -> Spread page
owner from V3 to V4 visual-parity presentation. All non-Spread routes continue
through frozen V134 -> V133 -> V132 -> V131 unchanged.
"""
from __future__ import annotations

from typing import Any, Callable

import nfl_spread_hub_v4 as spread_v4
import streamlit_memory_lazy_router_v132 as route_v132
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
HTML_RENDER_GUARD = "flatten_generated_html"
HTML_RENDER_GUARD_SCOPE = "route_purge_reimport_safe"


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
    """Install the presentation guard on both initial and freshly re-imported V4."""
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
    """Re-apply the V4 HTML guard after the memory router purges NFL modules."""
    module = importer(name)
    if str(name or "") == ACTIVE_SPREAD_HUB:
        return _install_html_guard(module)
    return module


# Protect the initial import. render_app() also protects any post-purge re-import.
# V4's football analytics, market transport, and certified 5M engine stay frozen.
_install_html_guard(spread_v4)


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def render_app() -> None:
    original_active_hub = prior.ACTIVE_SPREAD_HUB
    original_route_import = route_v132.root._import

    def guarded_route_import(name: str) -> Any:
        return _guard_route_import(original_route_import, name)

    prior.ACTIVE_SPREAD_HUB = ACTIVE_SPREAD_HUB
    route_v132.root._import = guarded_route_import
    try:
        return prior.render_app()
    finally:
        route_v132.root._import = original_route_import
        prior.ACTIVE_SPREAD_HUB = original_active_hub


__all__ = [
    "ACTIVE_SPREAD_HUB",
    "FROZEN_ROUTER",
    "HTML_RENDER_GUARD",
    "HTML_RENDER_GUARD_SCOPE",
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
