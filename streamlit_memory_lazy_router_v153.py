"""KYRE Streamlit Router V153 — CFB Game Total connected all-steps flow.

Additive over frozen Router V152. V153 preserves V152 navigation, route latch,
query repair, selector behavior, and every unrelated market. Only the exact
College Football -> Game Total renderer is redirected to clean page V9, which
is presentation-only over frozen V8.
"""
from __future__ import annotations

import streamlit as st

import streamlit_memory_lazy_router_v152 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V153 • CFB GAME TOTAL CONNECTED FLOW"
PRODUCTION_HEARTBEAT = "CFB_GAME_TOTAL_V153_CONNECTED_FLOW_ACTIVE"
LEGACY_PRODUCTION_HEARTBEAT = "CFB_GAME_TOTAL_V152_PRODUCTION_ACTIVE"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v152"
ACTIVE_PAGE = "cfb_game_total_clean_page_v9"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False

CFB_SPORT_LABEL = prior.CFB_SPORT_LABEL
GAME_TOTAL_MARKET = prior.GAME_TOTAL_MARKET
ROUTE_LATCH_KEY = prior.ROUTE_LATCH_KEY

_FROZEN_GAME_TOTAL_RENDER = prior._render_cfb_game_total_v152


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def _render_production_heartbeat() -> None:
    st.markdown(
        f'<div data-testid="cfb-game-total-v153-heartbeat" '
        f'style="font-size:.58rem;font-weight:800;color:#a7b6c5;margin:0 0 4px 2px">'
        f'{PRODUCTION_HEARTBEAT} · {LEGACY_PRODUCTION_HEARTBEAT}</div>',
        unsafe_allow_html=True,
    )


def _render_cfb_game_total_v153(market: str) -> None:
    """Render exact Game Total through V9; delegate every other case to V152."""
    sport = str(st.session_state.get("ks_sport_touch") or "")
    market = str(market or "")

    if sport != CFB_SPORT_LABEL or market != GAME_TOTAL_MARKET:
        return _FROZEN_GAME_TOTAL_RENDER(market)

    # Preserve V152 route ownership/query behavior, then import the additive V9
    # page directly so Streamlit reruns cannot fall back through a temporary
    # ACTIVE_PAGE mutation.
    prior._latch_game_total_route()
    prior._persist_game_total_route_query()
    _render_production_heartbeat()
    page = prior.root._import(ACTIVE_PAGE)
    return page.render_cfb_hub(
        market,
        prior.root.section_header,
        prior.root.status_info,
        prior.root.team_logo,
        prior.root.h,
    )


def render_app() -> None:
    """Delegate the full app to V152 with one exact Game Total renderer swap."""
    original_renderer = prior._render_cfb_game_total_v152
    prior._render_cfb_game_total_v152 = _render_cfb_game_total_v153
    try:
        return prior.render_app()
    finally:
        prior._render_cfb_game_total_v152 = original_renderer


__all__ = [
    "ACTIVE_PAGE",
    "CFB_SPORT_LABEL",
    "FROZEN_ROUTER",
    "GAME_TOTAL_MARKET",
    "LEGACY_PRODUCTION_HEARTBEAT",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "PRODUCTION_HEARTBEAT",
    "ROUTE_LATCH_KEY",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_render_cfb_game_total_v153",
    "_render_production_heartbeat",
    "record_bootstrap_import_ms",
    "render_app",
]
