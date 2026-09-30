"""Active-router wrapper for WNBA PRA Speed V3 Step 4 server bundle cache.

The current CFB Top Picks Research V2 Step 6 router remains the frozen parent.
Only the WNBA PRA cold-pair loader symbol is substituted while rendering.
"""
from __future__ import annotations

from typing import Any

import streamlit_memory_lazy_router_cfb_top_picks_research_v2_step6 as frozen_parent
import wnba_pra_speed_v3_step3_bundle as frozen_step3_bundle
import wnba_pra_speed_v3_step4_cache as step4_cache


MODEL_VERSION = "KYRE STREAMLIT ROUTER • WNBA PRA SPEED V3 STEP 4 SERVER BUNDLE CACHE"
FROZEN_PARENT_ROUTER = "streamlit_memory_lazy_router_cfb_top_picks_research_v2_step6"
FROZEN_SPEED_V3_STEP3_MODULE = "wnba_pra_speed_v3_step3_bundle"
MAY_MODIFY_WNBA_MODEL = False
MAY_MODIFY_OTHER_SPORTS = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0


def record_bootstrap_import_ms(value: float) -> None:
    return frozen_parent.record_bootstrap_import_ms(value)


def render_app() -> Any:
    original_loader = frozen_step3_bundle.load_bundle_pair
    frozen_step3_bundle.load_bundle_pair = step4_cache.load_cached_bundle_pair
    try:
        return step4_cache.render_step4_route(frozen_parent.render_app)
    finally:
        frozen_step3_bundle.load_bundle_pair = original_loader


__all__ = [
    "FROZEN_PARENT_ROUTER",
    "FROZEN_SPEED_V3_STEP3_MODULE",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_WNBA_MODEL",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "record_bootstrap_import_ms",
    "render_app",
]
