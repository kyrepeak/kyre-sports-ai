"""Active-router wrapper for CFB Top Picks Research V2 Step 6.

Only the College Football -> Top Picks page target changes. The current WNBA PRA
Speed V3 Step 3 router and all other routes remain frozen and delegated intact.
"""
from __future__ import annotations

from typing import Any

import streamlit_memory_lazy_router_v244 as top_picks_router
import streamlit_memory_lazy_router_wnba_pra_speed_v3_step3 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER • CFB TOP PICKS RESEARCH V2 STEP 6"
FROZEN_PARENT_ROUTER = "streamlit_memory_lazy_router_wnba_pra_speed_v3_step3"
TOP_PICKS_PAGE = "cfb_top_picks_page_v6"
MAY_MODIFY_OTHER_SPORTS = False
MAY_MODIFY_TOP_PICKS_RANKING = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def render_app() -> Any:
    original_page = top_picks_router.TOP_PICKS_PAGE
    top_picks_router.TOP_PICKS_PAGE = TOP_PICKS_PAGE
    try:
        return prior.render_app()
    finally:
        top_picks_router.TOP_PICKS_PAGE = original_page


__all__ = [
    "FROZEN_PARENT_ROUTER", "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_TOP_PICKS_RANKING", "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE", "TOP_PICKS_PAGE",
    "record_bootstrap_import_ms", "render_app",
]
