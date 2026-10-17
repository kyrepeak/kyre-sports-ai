"""Sticky KYRE SPORTS renderer for Universal Sports Navigation V1."""
from __future__ import annotations

import streamlit as st

from universal_sports_nav_controller_v1 import RouteIntent, RouteState
from universal_sports_nav_registry_v1 import get_sport, visible_sports


NAV_CONTAINER_KEY = "ks_universal_nav_shell"
SPORT_CONTROL_KEY = "ks_universal_sport_pills"
MARKET_CONTROL_KEY = "ks_universal_market_pills"

_NAV_CSS = r"""
<style>
.st-key-ks_universal_nav_shell{
    position: sticky;
    top: .35rem;
    z-index: 950;
    margin: 0 0 .7rem 0;
    padding: .56rem .62rem .62rem;
    border: 1px solid rgba(148,163,184,.18);
    border-radius: 16px;
    background: rgba(8,13,22,.96);
    backdrop-filter: blur(16px);
    box-shadow: 0 10px 28px rgba(2,6,23,.28);
}
.st-key-ks_universal_nav_shell .ks-universal-brand{
    margin: 0 0 .32rem .16rem;
    color: #f8fafc;
    font-size: .76rem;
    font-weight: 950;
    letter-spacing: .10em;
    line-height: 1;
}
.st-key-ks_universal_nav_shell div[data-testid="stPills"]{
    max-width: 100%;
    overflow-x: auto;
    overflow-y: hidden;
    scrollbar-width: none;
    -webkit-overflow-scrolling: touch;
}
.st-key-ks_universal_nav_shell div[data-testid="stPills"]::-webkit-scrollbar{display:none}
.st-key-ks_universal_nav_shell div[data-testid="stPills"] [role="radiogroup"]{
    display: flex;
    flex-wrap: nowrap !important;
    width: max-content;
    min-width: 100%;
    gap: .34rem;
}
.st-key-ks_universal_nav_shell div[data-testid="stPills"] button{
    flex: 0 0 auto;
    min-height: 36px;
    border-radius: 999px !important;
    white-space: nowrap;
    font-weight: 800;
}
.st-key-ks_universal_nav_shell div[data-testid="stPills"] button[aria-checked="true"]{
    border-color: rgba(56,189,248,.88) !important;
    background: rgba(56,189,248,.16) !important;
    color: #e0f2fe !important;
}
.st-key-ks_universal_nav_shell div[data-testid="stPills"] button:focus-visible{
    outline: 2px solid #38bdf8 !important;
    outline-offset: 2px;
}
@media(max-width:640px){
    .st-key-ks_universal_nav_shell{top:.2rem;padding:.48rem .5rem .54rem;border-radius:14px}
    .st-key-ks_universal_nav_shell div[data-testid="stPills"] button{min-height:38px}
}
</style>
"""


def _sport_label(sport_id: str) -> str:
    sport = get_sport(sport_id)
    return f"{sport.icon} {sport.label}" if sport else sport_id.upper()


def _market_label(sport_id: str, market_id: str) -> str:
    sport = get_sport(sport_id)
    if sport is None:
        return market_id
    market = next((item for item in sport.markets if item.id == market_id), None)
    return market.label if market else market_id


def render_universal_nav(state: RouteState) -> RouteIntent | None:
    sports = visible_sports()
    sport_ids = [sport.id for sport in sports]
    active_sport = get_sport(state.sport_id)
    if active_sport is None:
        active_sport = sports[0]

    with st.container(key=NAV_CONTAINER_KEY):
        st.markdown(_NAV_CSS, unsafe_allow_html=True)
        st.markdown('<div class="ks-universal-brand">KYRE SPORTS</div>', unsafe_allow_html=True)
        selected_sport = st.pills(
            "Sport",
            sport_ids,
            default=state.sport_id if state.sport_id in sport_ids else active_sport.id,
            key=SPORT_CONTROL_KEY,
            format_func=_sport_label,
            selection_mode="single",
            label_visibility="collapsed",
        )

        market_ids = [market.id for market in active_sport.markets if market.live]
        selected_market = st.pills(
            "Market",
            market_ids,
            default=state.market_id if state.market_id in market_ids else active_sport.default_market_id,
            key=MARKET_CONTROL_KEY,
            format_func=lambda market_id: _market_label(active_sport.id, market_id),
            selection_mode="single",
            label_visibility="collapsed",
        )

    if selected_sport and selected_sport != state.sport_id:
        return RouteIntent(sport_id=str(selected_sport), source="tap")
    if selected_market and selected_market != state.market_id:
        return RouteIntent(sport_id=state.sport_id, market_id=str(selected_market), source="tap")
    return None


__all__ = [
    "MARKET_CONTROL_KEY", "NAV_CONTAINER_KEY", "SPORT_CONTROL_KEY", "render_universal_nav",
]
