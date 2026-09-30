"""Active-router wrapper for CFB Top Picks Research V2 Step 7.

Only College Football -> Top Picks advances from frozen Step 6 to Step 7.
All other sport routes delegate through the frozen Step-6 parent.
"""
from __future__ import annotations

from typing import Any

import streamlit_memory_lazy_router_cfb_top_picks_research_v2_step6 as prior
import streamlit_memory_lazy_router_v244 as top_picks_router

MODEL_VERSION = "KYRE STREAMLIT ROUTER • CFB TOP PICKS RESEARCH V2 STEP 7"
FROZEN_PARENT_ROUTER = "streamlit_memory_lazy_router_cfb_top_picks_research_v2_step6"
TOP_PICKS_PAGE = "cfb_top_picks_page_v7"
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
