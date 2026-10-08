"""CFB Game Total Page 1 V2 Step 3 runtime activation.

This changes only the in-memory page target used by frozen Router V190 for the
exact CFB Game Total route. No frozen file is mutated.
"""
from __future__ import annotations

import streamlit_memory_lazy_router_v190 as cfb_router

BASE_PAGE = "cfb_game_total_clean_page_v35"
STEP3_PAGE = "cfb_game_total_clean_page_v36"
MAY_MODIFY_OTHER_SPORTS = False
MAY_MODIFY_PROJECTION = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0


def activate_step3_page() -> str:
    cfb_router.GAME_TOTAL_PAGE = STEP3_PAGE
    return STEP3_PAGE


__all__ = [
    "BASE_PAGE",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_PROJECTION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "STEP3_PAGE",
    "activate_step3_page",
]
