"""Streamlit Router WNBA-NAV-V2-STEP1 — WNBA Navigation V2 Step 1 foundation.

Additive over frozen V243. Only the exact WNBA -> PRA route receives the new
three-level navigation state controller.  The visible WNBA PRA product remains
the frozen production renderer until Step 2 builds the lightweight Slate page.

All CFB, NFL, MLB, and non-PRA WNBA routes delegate unchanged to V243.
"""
from __future__ import annotations

from typing import Any, Callable

import streamlit_memory_lazy_router_v1 as root
import streamlit_memory_lazy_router_v245 as prior
import wnba_pra_navigation_v2_step1 as navigation


MODEL_VERSION = "KYRE STREAMLIT ROUTER • WNBA NAVIGATION V2 STEP 1"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v245"
OWNED_SPORT = "WNBA"
OWNED_MARKET = "PRA"
ROUTE_OWNERSHIP_ONLY = True
MAY_MODIFY_WNBA_MODEL = False
MAY_MODIFY_OTHER_SPORTS = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def _render_wnba_v244(
    market: str,
    frozen_renderer: Callable[[str], Any],
) -> Any:
    normalized = str(market or "").strip()
    if normalized != OWNED_MARKET:
        return frozen_renderer(market)

    return navigation.render_step1_foundation(
        lambda: frozen_renderer(OWNED_MARKET)
    )


def render_app() -> None:
    original_render_wnba = root._render_wnba

    def owned_render_wnba(market: str) -> Any:
        return _render_wnba_v244(market, original_render_wnba)

    root._render_wnba = owned_render_wnba
    try:
        return prior.render_app()
    finally:
        root._render_wnba = original_render_wnba


__all__ = [
    "FROZEN_ROUTER",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_WNBA_MODEL",
    "MODEL_VERSION",
    "OWNED_MARKET",
    "OWNED_SPORT",
    "ROUTE_OWNERSHIP_ONLY",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_render_wnba_v244",
    "record_bootstrap_import_ms",
    "render_app",
]
