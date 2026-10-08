"""CFB Game Total Page 1 V2 Step 4 runtime activation.

This changes only the in-memory page target used by frozen Router V190 for the
exact CFB Game Total route. The frozen V37 baseline is preserved for audit
compatibility, then the additive V38 runtime-repair page becomes the effective
target before routing.
"""
from __future__ import annotations

import streamlit_memory_lazy_router_v190 as cfb_router

BASE_PAGE = "cfb_game_total_clean_page_v36"
STEP4_PAGE = "cfb_game_total_clean_page_v37"
STEP4_REPAIR_PAGE = "cfb_game_total_clean_page_v38"
MAY_MODIFY_OTHER_SPORTS = False
MAY_MODIFY_PROJECTION = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0


def activate_step4_page() -> str:
    # Preserve the frozen Step-4 baseline assignment, then advance additively to
    # the exact runtime-repair owner in the same activation transaction.
    cfb_router.GAME_TOTAL_PAGE = STEP4_PAGE
    cfb_router.GAME_TOTAL_PAGE = STEP4_REPAIR_PAGE
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
