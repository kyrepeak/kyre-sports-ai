"""CFB Game Total Page 2 same-page shell repair.

Selected-event analysis is rendered inside the current Page-1 V45 experience
instead of on the older V38 render base. The universal website shell is rendered
once through the existing Step-8 shared-shell bridge, V45 remains the Page-1
content owner, and the frozen Step-8 Page-2 injector still owns every analysis
surface.

This layer changes presentation/routing composition only. It adds no provider,
model, projection, probability, ranking, selection, market, or sportsbook logic.
"""
from __future__ import annotations

from typing import Any

import cfb_game_total_clean_page_v45 as page1
import cfb_game_total_page2_network_free_v2 as live_data
import cfb_game_total_page2_step8_final_runtime_v1 as page2
import streamlit_memory_lazy_router_cfb_game_total_page2_step8_final_v1 as cfb_router

MODEL_VERSION = "CFB GAME TOTAL PAGE2 SAME-PAGE SHELL REPAIR V1"
MARKET = page2.MARKET
SAME_PAGE_ROUTE = "cfb_game_total_page2_same_page_shell_repair_v1"
ACTIVE_MARKER = "CFB_GAME_TOTAL_PAGE2_SAME_PAGE_SHELL_REPAIR_V1_ACTIVE"
MAY_MODIFY_MODEL = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_SELECTION = False
MAY_MODIFY_MARKET_OWNERSHIP = False
MAY_MODIFY_OTHER_SPORTS = False
MAY_MODIFY_PAGE1 = False
NETWORK_CALLS_ADDED = 0
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0


def render_game_total_hub(section_header=None, status_info=None, team_logo=None, h=None):
    """Inject frozen Page-2 analysis into the current V45 Page-1 render base."""
    page2.st.markdown(page2.PAGE2_STEP8_CSS, unsafe_allow_html=True)
    with live_data.install_page2_live_data_repair():
        return page2._render_selected_page(
            page1.render_game_total_hub,
            section_header,
            status_info,
            team_logo,
            h,
        )


def render_cfb_hub(
    market: str,
    section_header=None,
    status_info=None,
    team_logo=None,
    h=None,
) -> None:
    if market != MARKET:
        raise ValueError(f"Same-page Page2 received unsupported market: {market}")
    return render_game_total_hub(section_header, status_info, team_logo, h)


def render_selected_in_shared_shell() -> Any:
    """Render one universal shell, then continue from Page 1 into selected analysis."""
    with cfb_router._ROUTE_POINTER_LOCK:
        original_page1 = cfb_router.PAGE1_NATIVE_ROUTE
        cfb_router.PAGE1_NATIVE_ROUTE = SAME_PAGE_ROUTE
        try:
            return cfb_router._render_page1_in_shared_shell()
        finally:
            cfb_router.PAGE1_NATIVE_ROUTE = original_page1


__all__ = [
    "ACTIVE_MARKER",
    "MARKET",
    "MAY_MODIFY_MARKET_OWNERSHIP",
    "MAY_MODIFY_MODEL",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_PAGE1",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_RANKING",
    "MAY_MODIFY_SELECTION",
    "MODEL_VERSION",
    "NETWORK_CALLS_ADDED",
    "SAME_PAGE_ROUTE",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "render_cfb_hub",
    "render_game_total_hub",
    "render_selected_in_shared_shell",
]
