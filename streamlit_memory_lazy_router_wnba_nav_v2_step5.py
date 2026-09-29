"""Streamlit router for WNBA Navigation V2 Step 5 performance layer."""
from __future__ import annotations

from typing import Any, Callable

import streamlit_memory_lazy_router_v1 as root
import streamlit_memory_lazy_router_v245 as prior
import wnba_pra_performance_v2_step5 as performance


MODEL_VERSION = "KYRE STREAMLIT ROUTER • WNBA NAVIGATION V2 STEP 5"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v245"
FROZEN_NAVIGATION = "wnba_pra_navigation_v2_step1"
FROZEN_SLATE = "wnba_pra_slate_v2_step2"
FROZEN_GAME_CENTER = "wnba_pra_game_center_v2_step3"
FROZEN_PLAYER_INTELLIGENCE = "wnba_pra_player_intelligence_v2_step4"
OWNED_SPORT = "WNBA"
OWNED_MARKET = "PRA"
MAY_MODIFY_WNBA_MODEL = False
MAY_MODIFY_OTHER_SPORTS = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def _render_wnba_step5(
    market: str,
    frozen_renderer: Callable[[str], Any],
) -> Any:
    normalized = str(market or "").strip()
    if normalized != OWNED_MARKET:
        return frozen_renderer(market)
    return performance.render_step5_route()


def render_app() -> None:
    original_render_wnba = root._render_wnba

    def owned_render_wnba(market: str) -> Any:
        return _render_wnba_step5(market, original_render_wnba)

    root._render_wnba = owned_render_wnba
    try:
        return prior.render_app()
    finally:
        root._render_wnba = original_render_wnba


__all__ = [
    "FROZEN_GAME_CENTER",
    "FROZEN_NAVIGATION",
    "FROZEN_PLAYER_INTELLIGENCE",
    "FROZEN_ROUTER",
    "FROZEN_SLATE",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_WNBA_MODEL",
    "MODEL_VERSION",
    "OWNED_MARKET",
    "OWNED_SPORT",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_render_wnba_step5",
    "record_bootstrap_import_ms",
    "render_app",
]
