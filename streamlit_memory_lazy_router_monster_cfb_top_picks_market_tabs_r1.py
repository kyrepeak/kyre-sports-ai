"""MONSTER CFB Top Picks market-tabs route successor R1.

Only exact College Football -> Top Picks renders temporarily advance the frozen
Top Picks Step-9 page pointer to V10. Every other sport/market delegates through
the current API2 NFL active-slate terminal owner unchanged. That parent already
delegates to the frozen MONSTER CFB market-completeness chain. Pointer state is
restored in ``finally`` on every render.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

import streamlit_memory_lazy_router_api2_nfl_active_slate_v1 as prior
import streamlit_memory_lazy_router_cfb_top_picks_research_v2_step9 as top_picks_owner

MODEL_VERSION = "MONSTER CFB TOP PICKS MARKET TABS R1"
FROZEN_PARENT = "streamlit_memory_lazy_router_api2_nfl_active_slate_v1"
TOP_PICKS_PAGE = "cfb_top_picks_page_v10"
ROUTE_QUERY_SPORT = "ks_sport"
ROUTE_QUERY_MARKET = "ks_cfb_market"
CFB_SPORT_LABEL = "College Football"
TOP_PICKS_MARKET = "Top Picks"
MAY_MODIFY_OTHER_SPORTS = False
MAY_MODIFY_OTHER_CFB_MARKETS = False
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0


def _query_value(key: str) -> str:
    try:
        raw = st.query_params.get(key)
    except Exception:
        return ""
    if isinstance(raw, (list, tuple)):
        raw = raw[-1] if raw else ""
    return str(raw or "").strip()


def _is_cfb_top_picks_route() -> bool:
    return (
        _query_value(ROUTE_QUERY_SPORT) == CFB_SPORT_LABEL
        and _query_value(ROUTE_QUERY_MARKET) == TOP_PICKS_MARKET
    )


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def render_app() -> Any:
    if not _is_cfb_top_picks_route():
        return prior.render_app()

    original_page = top_picks_owner.TOP_PICKS_PAGE
    top_picks_owner.TOP_PICKS_PAGE = TOP_PICKS_PAGE
    try:
        return prior.render_app()
    finally:
        top_picks_owner.TOP_PICKS_PAGE = original_page


__all__ = [
    "CFB_SPORT_LABEL",
    "FROZEN_PARENT",
    "MAY_MODIFY_OTHER_CFB_MARKETS",
    "MAY_MODIFY_OTHER_SPORTS",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "ROUTE_QUERY_MARKET",
    "ROUTE_QUERY_SPORT",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "TOP_PICKS_MARKET",
    "TOP_PICKS_PAGE",
    "_is_cfb_top_picks_route",
    "_query_value",
    "record_bootstrap_import_ms",
    "render_app",
]
