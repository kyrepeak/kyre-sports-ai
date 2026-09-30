"""Active router wrapper for WNBA PRA Speed V3 Step 5."""
from __future__ import annotations

from typing import Any

import streamlit_memory_lazy_router_cfb_top_picks_research_v2_step9 as current_parent
import wnba_pra_performance_v2_step5 as performance
import wnba_pra_speed_v3_step5_consumer_reuse as step5

MODEL_VERSION = "KYRE STREAMLIT ROUTER • WNBA PRA SPEED V3 STEP 5 CONSUMER REUSE"
CURRENT_PARENT_ROUTER = "streamlit_memory_lazy_router_cfb_top_picks_research_v2_step9"
FROZEN_SPEED_STEP4_PARENT = "streamlit_memory_lazy_router_wnba_pra_speed_v3_step4"
MAY_MODIFY_WNBA_MODEL = False
MAY_MODIFY_OTHER_SPORTS = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0


def record_bootstrap_import_ms(value: float) -> None:
    return current_parent.record_bootstrap_import_ms(value)


def render_app() -> Any:
    original_loader = performance.load_player_intelligence_same_session
    performance.load_player_intelligence_same_session = (
        step5.load_player_intelligence_cross_player_reuse
    )
    try:
        return step5.render_step5_route(current_parent.render_app)
    finally:
        performance.load_player_intelligence_same_session = original_loader


__all__ = [
    "CURRENT_PARENT_ROUTER",
    "FROZEN_SPEED_STEP4_PARENT",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_WNBA_MODEL",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "record_bootstrap_import_ms",
    "render_app",
]
