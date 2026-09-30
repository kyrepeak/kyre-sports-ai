"""Active-router wrapper for CFB Top Picks Research V2 Step 9.

Preserves the current WNBA PRA Speed V3 Step 4 router and advances only the
frozen CFB Step-8 Top Picks page target from V8 to V9 during render.
"""
from __future__ import annotations

from typing import Any

import streamlit_memory_lazy_router_cfb_top_picks_research_v2_step8 as step8_router
import streamlit_memory_lazy_router_wnba_pra_speed_v3_step4 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER • CFB TOP PICKS RESEARCH V2 STEP 9"
FROZEN_PARENT_ROUTER = "streamlit_memory_lazy_router_wnba_pra_speed_v3_step4"
FROZEN_CFB_STEP8_ROUTER = "streamlit_memory_lazy_router_cfb_top_picks_research_v2_step8"
TOP_PICKS_PAGE = "cfb_top_picks_page_v9"
MAY_MODIFY_OTHER_SPORTS = False
MAY_MODIFY_TOP_PICKS_RANKING = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def render_app() -> Any:
    original_page = step8_router.TOP_PICKS_PAGE
    step8_router.TOP_PICKS_PAGE = TOP_PICKS_PAGE
    try:
        return prior.render_app()
    finally:
        step8_router.TOP_PICKS_PAGE = original_page


__all__ = [
    "FROZEN_CFB_STEP8_ROUTER", "FROZEN_PARENT_ROUTER",
    "MAY_MODIFY_OTHER_SPORTS", "MAY_MODIFY_TOP_PICKS_RANKING",
    "MODEL_VERSION", "SPORTSBOOK_PROJECTION_INFLUENCE", "TOP_PICKS_PAGE",
    "record_bootstrap_import_ms", "render_app",
]
