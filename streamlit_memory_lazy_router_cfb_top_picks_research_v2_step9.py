"""Active-router wrapper for CFB Top Picks Research V2 Step 9.

Preserves the current WNBA PRA Speed V3 Step 4 parent and advances only the
nested CFB Top Picks page owned by the frozen CFB wrapper chain to V9.

Step 9 must propagate its page selection through Steps 8, 7, and 6 because
each nested wrapper owns a TOP_PICKS_PAGE selector and otherwise overwrites
the outer selection before the base Top Picks router renders.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

import streamlit_memory_lazy_router_cfb_top_picks_research_v2_step6 as cfb_step6_parent
import streamlit_memory_lazy_router_cfb_top_picks_research_v2_step7 as cfb_step7_parent
import streamlit_memory_lazy_router_cfb_top_picks_research_v2_step8 as cfb_step8_parent
import streamlit_memory_lazy_router_wnba_pra_speed_v3_step4 as current_parent
import streamlit_memory_lazy_router_v241 as top_picks_base

MODEL_VERSION = "KYRE STREAMLIT ROUTER • CFB TOP PICKS RESEARCH V2 STEP 9"
CURRENT_PARENT_ROUTER = "streamlit_memory_lazy_router_wnba_pra_speed_v3_step4"
FROZEN_CFB_PARENT_ROUTER = "streamlit_memory_lazy_router_cfb_top_picks_research_v2_step8"
TOP_PICKS_PAGE = "cfb_top_picks_page_v9"
TOP_PICK_DETAIL_QUERY = "top_pick_detail"
UNIVERSAL_SPORT_JUMP_QUERY_KEY = "ks_jump_sport"
UNIVERSAL_MARKET_JUMP_QUERY_KEY = "ks_jump_market"
MAY_MODIFY_OTHER_SPORTS = False
MAY_MODIFY_WNBA_SPEED_STEP4 = False
MAY_MODIFY_TOP_PICKS_RANKING = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0


def record_bootstrap_import_ms(value: float) -> None:
    return current_parent.record_bootstrap_import_ms(value)


def _query_value(key: str) -> str:
    try:
        raw = st.query_params.get(key)
    except Exception:
        return ""
    if isinstance(raw, (list, tuple)):
        raw = raw[-1] if raw else ""
    return str(raw or "").strip()


def _protect_cfb_detail_route() -> bool:
    """Preserve CFB Top Picks ownership across unrelated universal shell reruns."""
    if (
        not _query_value(TOP_PICK_DETAIL_QUERY)
        or _query_value(top_picks_base.ROUTE_QUERY_SPORT) != top_picks_base.CFB_SPORT_LABEL
        or _query_value(top_picks_base.ROUTE_QUERY_MARKET) != top_picks_base.TOP_PICKS_MARKET
    ):
        return False

    try:
        st.query_params.pop(UNIVERSAL_SPORT_JUMP_QUERY_KEY, None)
        st.query_params.pop(UNIVERSAL_MARKET_JUMP_QUERY_KEY, None)
    except Exception:
        pass

    top_picks_base._prime_top_picks_state_from_query()
    return True


def _page_owner_chain() -> tuple[Any, ...]:
    return (cfb_step8_parent, cfb_step7_parent, cfb_step6_parent)


def render_app() -> Any:
    _protect_cfb_detail_route()
    owners = _page_owner_chain()
    original_pages = [owner.TOP_PICKS_PAGE for owner in owners]
    for owner in owners:
        owner.TOP_PICKS_PAGE = TOP_PICKS_PAGE
    try:
        return current_parent.render_app()
    finally:
        for owner, original_page in zip(reversed(owners), reversed(original_pages)):
            owner.TOP_PICKS_PAGE = original_page


__all__ = [
    "CURRENT_PARENT_ROUTER", "FROZEN_CFB_PARENT_ROUTER",
    "MAY_MODIFY_OTHER_SPORTS", "MAY_MODIFY_TOP_PICKS_RANKING",
    "MAY_MODIFY_WNBA_SPEED_STEP4", "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE", "TOP_PICKS_PAGE",
    "TOP_PICK_DETAIL_QUERY", "UNIVERSAL_SPORT_JUMP_QUERY_KEY",
    "UNIVERSAL_MARKET_JUMP_QUERY_KEY", "_protect_cfb_detail_route",
    "_page_owner_chain", "record_bootstrap_import_ms", "render_app",
]
