"""KYRE Streamlit Router V135 — NFL Spread visual-parity matchup board.

V135 is additive over certified Router V134. It preserves V134's exact Spread
route/query behavior, independent fair-margin model, deterministic 5M Monte
Carlo, and all safety flags while changing only the active NFL -> Spread page
owner from V3 to V4 visual-parity presentation. All non-Spread routes continue
through frozen V134 -> V133 -> V132 -> V131 unchanged.
"""
from __future__ import annotations

from typing import Any

import streamlit_memory_lazy_router_v132 as direct_spread
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
HTML_RENDER_GUARD = "patch_fresh_route_import"


def _flatten_generated_html(value: str) -> str:
    """Keep generated V4 markup out of Markdown's indented-code path."""
    return "".join(line.strip() for line in str(value or "").splitlines())


def _install_html_render_guard(module: Any) -> Any:
    """Patch the exact fresh V4 module that V132 imports for the live route."""
    if getattr(module, "__name__", "") != ACTIVE_SPREAD_HUB:
        return module
    if bool(getattr(module, "_v135_html_render_guard_installed", False)):
        return module

    raw_matchup_card = getattr(module, "_matchup_card", None)
    raw_summary_html = getattr(module, "_summary_html", None)
    if not callable(raw_matchup_card) or not callable(raw_summary_html):
        raise RuntimeError("NFL Spread V4 HTML guard could not find generated markup helpers.")

    def _html_safe_matchup_card(*args: Any, **kwargs: Any) -> str:
        return _flatten_generated_html(raw_matchup_card(*args, **kwargs))

    def _html_safe_summary_html(*args: Any, **kwargs: Any) -> str:
        return _flatten_generated_html(raw_summary_html(*args, **kwargs))

    module._matchup_card = _html_safe_matchup_card
    module._summary_html = _html_safe_summary_html
    module._v135_html_render_guard_installed = True
    return module


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def render_app() -> None:
    original_active_hub = prior.ACTIVE_SPREAD_HUB
    original_route_import = direct_spread.root._import

    def _guarded_route_import(module_name: str):
        module = original_route_import(module_name)
        if module_name == ACTIVE_SPREAD_HUB:
            module = _install_html_render_guard(module)
        return module

    prior.ACTIVE_SPREAD_HUB = ACTIVE_SPREAD_HUB
    direct_spread.root._import = _guarded_route_import
    try:
        return prior.render_app()
    finally:
        direct_spread.root._import = original_route_import
        prior.ACTIVE_SPREAD_HUB = original_active_hub


__all__ = [
    "ACTIVE_SPREAD_HUB",
    "FROZEN_ROUTER",
    "HTML_RENDER_GUARD",
    "MODEL_VERSION",
    "MONTE_CARLO_ENABLED",
    "PROJECTION_MODEL_ENABLED",
    "SPREAD_MARKET",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "WAGER_ACTIONS_ENABLED",
    "_flatten_generated_html",
    "_install_html_render_guard",
    "record_bootstrap_import_ms",
    "render_app",
]
