"""CFB Game Total Page 1 V2 Step 4 runtime activation.

Converges the already-proven V38 Step-4 page onto every live CFB Game Total
route owner that can dispatch the exact surface. Router source files remain
untouched; only their in-memory page pointers are advanced for the CFB Game
Total route before rendering.
"""
from __future__ import annotations

import streamlit_memory_lazy_router_v160 as render_owner
import streamlit_memory_lazy_router_v181 as live_owner
import streamlit_memory_lazy_router_v190 as cfb_router

BASE_PAGE = "cfb_game_total_clean_page_v36"
STEP4_PAGE = "cfb_game_total_clean_page_v37"
STEP4_REPAIR_PAGE = "cfb_game_total_clean_page_v38"
MAY_MODIFY_OTHER_SPORTS = False
MAY_MODIFY_PROJECTION = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0


def activate_step4_page() -> str:
    # Preserve the frozen Step-4 baseline assignment, then converge all known
    # exact Game Total route owners onto the proven V38 presentation target.
    cfb_router.GAME_TOTAL_PAGE = STEP4_PAGE
    cfb_router.GAME_TOTAL_PAGE = STEP4_REPAIR_PAGE
    live_owner.ACTIVE_PAGE = STEP4_REPAIR_PAGE
    render_owner.ACTIVE_PAGE = STEP4_REPAIR_PAGE
    return STEP4_REPAIR_PAGE


__all__ = [
    "BASE_PAGE",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_PROJECTION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP4_PAGE",
    "STEP4_REPAIR_PAGE",
    "activate_step4_page",
]
