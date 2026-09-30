"""Active-router wrapper for CFB Top Picks Research V2 Step 9.

Preserves the current WNBA PRA Speed V3 Step 4 parent and advances only the
nested CFB Top Picks page owned by frozen Step 8 from V8 to V9.
"""
from __future__ import annotations

from typing import Any

import streamlit_memory_lazy_router_cfb_top_picks_research_v2_step8 as cfb_step8_parent
import streamlit_memory_lazy_router_wnba_pra_speed_v3_step4 as current_parent

MODEL_VERSION = "KYRE STREAMLIT ROUTER • CFB TOP PICKS RESEARCH V2 STEP 9"
CURRENT_PARENT_ROUTER = "streamlit_memory_lazy_router_wnba_pra_speed_v3_step4"
FROZEN_CFB_PARENT_ROUTER = "streamlit_memory_lazy_router_cfb_top_picks_research_v2_step8"
TOP_PICKS_PAGE = "cfb_top_picks_page_v9"
MAY_MODIFY_OTHER_SPORTS = False
MAY_MODIFY_WNBA_SPEED_STEP4 = False
MAY_MODIFY_TOP_PICKS_RANKING = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0


def record_bootstrap_import_ms(value: float) -> None:
    return current_parent.record_bootstrap_import_ms(value)


def render_app() -> Any:
    original_page = cfb_step8_parent.TOP_PICKS_PAGE
    cfb_step8_parent.TOP_PICKS_PAGE = TOP_PICKS_PAGE
    try:
        return current_parent.render_app()
    finally:
        cfb_step8_parent.TOP_PICKS_PAGE = original_page


__all__ = [
    "CURRENT_PARENT_ROUTER", "FROZEN_CFB_PARENT_ROUTER",
    "MAY_MODIFY_OTHER_SPORTS", "MAY_MODIFY_TOP_PICKS_RANKING",
    "MAY_MODIFY_WNBA_SPEED_STEP4", "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE", "TOP_PICKS_PAGE",
    "record_bootstrap_import_ms", "render_app",
]
