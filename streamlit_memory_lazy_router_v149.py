"""KYRE Streamlit Router V149 — CFB Over/Under Monster compact dashboard.

Additive over frozen Router V148. Advances only exact College Football ->
Over/Under to Clean Page V38 while preserving the V148 CFB Moneyline dashboard,
NFL routes, every other certified market, and all frozen calculations.

V150 activation note: the certified V149 Over/Under path below is preserved;
only exact College Football -> Game Total is handed to the additive V150 router.
"""
from __future__ import annotations

import streamlit as st

import streamlit_memory_lazy_router_v1 as root
import streamlit_memory_lazy_router_v77 as cfb_route_base
import streamlit_memory_lazy_router_v148 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V149 • CFB O/U MONSTER COMPACT DASHBOARD"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v148"
CFB_SPORT_LABEL = "College Football"
OVER_UNDER_MARKET = "Over/Under"
GAME_TOTAL_MARKET = "Game Total"
ACTIVE_PAGE = "cfb_over_under_clean_page_v38"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False

_ORIGINAL_RENDER_NFL = root._render_nfl
_FROZEN_CFB_SELECTBOX = cfb_route_base._selectbox_v77


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def _over_under_route_active() -> bool:
    return (
        str(st.session_state.get("ks_sport_touch") or "") == CFB_SPORT_LABEL
        and str(st.session_state.get("ks_cfb_market_touch") or "") == OVER_UNDER_MARKET
    )


def _game_total_v150_route_active() -> bool:
    return (
        str(st.session_state.get("ks_sport_touch") or "") == CFB_SPORT_LABEL
        and str(st.session_state.get("ks_cfb_market_touch") or "") == GAME_TOTAL_MARKET
    )


def _persist_game_total_v150_query() -> None:
    """Persist exact Game Total before frozen V148 reruns away from Moneyline."""
    try:
        if cfb_route_base._query_value(cfb_route_base.ROUTE_QUERY_SPORT) != CFB_SPORT_LABEL:
            st.query_params[cfb_route_base.ROUTE_QUERY_SPORT] = CFB_SPORT_LABEL
        if cfb_route_base._query_value(cfb_route_base.ROUTE_QUERY_MARKET) != GAME_TOTAL_MARKET:
            st.query_params[cfb_route_base.ROUTE_QUERY_MARKET] = GAME_TOTAL_MARKET
    except Exception:
        pass


def _selectbox_v150_handoff(label, options, *args, **kwargs):
    """Preserve V77 behavior while making the Game Total transition restorable."""
    selected = _FROZEN_CFB_SELECTBOX(label, options, *args, **kwargs)
    if (
        label == "🎯 NFL Market"
        and str(st.session_state.get("ks_sport_touch") or "") == CFB_SPORT_LABEL
        and str(selected or "") == GAME_TOTAL_MARKET
    ):
        # The keyed CFB selectbox already owns ks_cfb_market_touch. Rewriting
        # that key after widget instantiation raises StreamlitWidgetAlreadyInstantiatedError.
        _persist_game_total_v150_query()
    return selected


def _restore_game_total_v150_from_query() -> bool:
    """Restore exact V150 Game Total before V77 considers its O/U-only query."""
    current_sport = str(st.session_state.get("ks_sport_touch") or "").strip()
    current_market = str(st.session_state.get("ks_cfb_market_touch") or "").strip()
    if current_sport or current_market:
        return False
    if (
        cfb_route_base._query_value(cfb_route_base.ROUTE_QUERY_SPORT) != CFB_SPORT_LABEL
        or cfb_route_base._query_value(cfb_route_base.ROUTE_QUERY_MARKET) != GAME_TOTAL_MARKET
    ):
        return False
    st.session_state["ks_sport_touch"] = CFB_SPORT_LABEL
    st.session_state["ks_cfb_market_touch"] = GAME_TOTAL_MARKET
    return True


def _render_cfb_over_under_v149(market: str) -> None:
    sport = str(st.session_state.get("ks_sport_touch") or "")
    market = str(market or "")

    if sport == CFB_SPORT_LABEL and market != OVER_UNDER_MARKET:
        # User changed CFB markets while V149 direct O/U render was active.
        # Stop this stale rerun; the next rerun delegates to V148 normally.
        cfb_route_base._clear_fast_route_query()
        st.rerun()

    if sport != CFB_SPORT_LABEL or market != OVER_UNDER_MARKET:
        return _ORIGINAL_RENDER_NFL(market)

    cfb_route_base._persist_fast_route_query()
    st.caption(
        "🛡️ CFB O/U • CLEAN PAGE V38 ACTIVE • FUTURE SLATE COVERAGE ACTIVE • "
        "OFFICIAL ESPN IDENTITY RECOVERY • NO FUZZY MATCHING • NO SYNTHETIC IDS • "
        "FRESHNESS FIREWALL ACTIVE • 0.0% PROJECTION INFLUENCE • "
        "FROZEN PROJECTION MATH PRESERVED • READABLE STEPS 4-12 ACTIVE"
    )
    page = root._import(ACTIVE_PAGE)
    return page.render_cfb_hub(
        market,
        root.section_header,
        root.status_info,
        root.team_logo,
        root.h,
    )


def _render_direct_cfb_over_under() -> None:
    original_selectbox = root.st.selectbox
    original_render_nfl = root._render_nfl
    original_prefixes = root._ROUTE_MODULE_PREFIXES

    # Reuse the certified CFB selector/query behavior from the frozen fast path.
    root.st.selectbox = cfb_route_base._selectbox_v77
    root._render_nfl = _render_cfb_over_under_v149
    if "cfb_" not in root._ROUTE_MODULE_PREFIXES:
        root._ROUTE_MODULE_PREFIXES = root._ROUTE_MODULE_PREFIXES + ("cfb_",)

    try:
        return root.render_app()
    finally:
        root.st.selectbox = original_selectbox
        root._render_nfl = original_render_nfl
        root._ROUTE_MODULE_PREFIXES = original_prefixes


def render_app() -> None:
    if not _over_under_route_active() and not _game_total_v150_route_active():
        if not _restore_game_total_v150_from_query():
            cfb_route_base._restore_fast_route_from_query()
    if _game_total_v150_route_active():
        # Late import avoids touching V149's certified O/U import path and avoids
        # an eager circular dependency while V150 freezes V149 as its prior router.
        from streamlit_memory_lazy_router_v150 import _render_direct_cfb_game_total
        return _render_direct_cfb_game_total()
    if _over_under_route_active():
        return _render_direct_cfb_over_under()

    # Frozen V148 owns Moneyline. It installs V77's selector while rendering,
    # so wrap that one selector reference only for the duration of delegation.
    # This lets a Moneyline -> Game Total click persist the exact V150 route
    # before V148 calls st.rerun(), then restores V77 byte-for-byte afterward.
    original_cfb_selectbox = cfb_route_base._selectbox_v77
    cfb_route_base._selectbox_v77 = _selectbox_v150_handoff
    try:
        return prior.render_app()
    finally:
        cfb_route_base._selectbox_v77 = original_cfb_selectbox


__all__ = [
    "ACTIVE_PAGE",
    "CFB_SPORT_LABEL",
    "FROZEN_ROUTER",
    "GAME_TOTAL_MARKET",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "OVER_UNDER_MARKET",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_game_total_v150_route_active",
    "_over_under_route_active",
    "_persist_game_total_v150_query",
    "_render_cfb_over_under_v149",
    "_render_direct_cfb_over_under",
    "_restore_game_total_v150_from_query",
    "_selectbox_v150_handoff",
    "record_bootstrap_import_ms",
    "render_app",
]
