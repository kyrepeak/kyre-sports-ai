"""MONSTER CFB Game Total market-completeness route successor R1.

Exact CFB -> Game Total renders keep the frozen V4 ownership gate and production
chain, but temporarily redirect only the Page-2 runtime pointer to the additive
same-book market-completeness successor. Every non-CFB route delegates unchanged.
The prior runtime pointer is restored in ``finally`` on every render.
"""
from __future__ import annotations

from typing import Any

import streamlit_memory_lazy_router_monster_cfb_v4_route_ownership_r1 as prior
import streamlit_memory_lazy_router_nfl_spread_mobile_repair_v1 as cfb_production

MODEL_VERSION = "MONSTER CFB GAME TOTAL MARKET COMPLETENESS ROUTE R1"
FROZEN_PARENT = "streamlit_memory_lazy_router_monster_cfb_v4_route_ownership_r1"
CFB_PAGE2_RUNTIME = "cfb_game_total_page2_market_completeness_r1"
MAY_MODIFY_PAGE1 = False
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_SELECTION = False
MAY_MODIFY_OTHER_SPORTS = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def render_app() -> Any:
    if not prior._is_cfb_game_total_route():
        return prior.render_app()

    fast_switch = cfb_production.prior
    original_runtime = fast_switch.CFB_PAGE2_RUNTIME
    fast_switch.CFB_PAGE2_RUNTIME = CFB_PAGE2_RUNTIME
    try:
        return prior.render_app()
    finally:
        fast_switch.CFB_PAGE2_RUNTIME = original_runtime


__all__ = [
    "CFB_PAGE2_RUNTIME",
    "FROZEN_PARENT",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_PAGE1",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_RANKING",
    "MAY_MODIFY_SELECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "record_bootstrap_import_ms",
    "render_app",
]
