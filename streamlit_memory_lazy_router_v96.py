"""KYRE Streamlit Router V96 — Passing Yards cleanup route precedence hotfix.

V92–V95 patched V80's deepest NFL handler before delegating to V91. But V91
then reassigned that same deepest handler to its own `_render_nfl_v91`, so the
older Step 10 page still won at runtime. V96 fixes the actual overwrite point:
it temporarily replaces V91's handler symbol itself with the current V96 handler.
When V91 later installs its handler into V80, it therefore installs V96 and the
latest V16 cleanup page reaches production.

No model, loader, probability, market, grading, CFB, or other sport logic changes.
"""
from __future__ import annotations

import streamlit_memory_lazy_router_v1 as root
import streamlit_memory_lazy_router_v91 as precedence_owner
import streamlit_memory_lazy_router_v95 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V96 • NFL PASSING YARDS ROUTE PRECEDENCE HOTFIX V2"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v95"
PRECEDENCE_ANCHOR = "streamlit_memory_lazy_router_v91._render_nfl_v91"
ACTIVE_NFL_HUB = "nfl_hub_v34"
PASSING_YARDS_MARKET = "Passing Yards"

_ORIGINAL_RENDER_NFL = root._render_nfl


def record_bootstrap_import_ms(value: float) -> None:
    prior.record_bootstrap_import_ms(value)


def _render_nfl_v96(market: str) -> None:
    market = str(market or "Slate")
    if market != PASSING_YARDS_MARKET:
        return _ORIGINAL_RENDER_NFL(market)
    mod = root._import(ACTIVE_NFL_HUB)
    return mod.render_nfl_hub(market)


def render_app() -> None:
    # V91 is the actual last writer to V80's deepest handler during the nested
    # V95 -> ... -> V91 chain. Patch V91's symbol, not V80 prematurely.
    original_v91_handler = precedence_owner._render_nfl_v91
    precedence_owner._render_nfl_v91 = _render_nfl_v96
    try:
        return prior.render_app()
    finally:
        precedence_owner._render_nfl_v91 = original_v91_handler


__all__ = [
    "ACTIVE_NFL_HUB",
    "FROZEN_ROUTER",
    "MODEL_VERSION",
    "PASSING_YARDS_MARKET",
    "PRECEDENCE_ANCHOR",
    "_render_nfl_v96",
    "record_bootstrap_import_ms",
    "render_app",
]
