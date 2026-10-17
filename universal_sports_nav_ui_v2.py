"""Tap-first Universal Sports Navigation V2 renderer.

Widget callbacks record the user's route intent before Streamlit starts the
next full script run. The V2 activation overlay consumes that one-shot intent
before the frozen V1 route resolver or any nested legacy router can render.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

import universal_sports_nav_ui_v1 as v1
from universal_sports_nav_controller_v1 import RouteState
from universal_sports_nav_registry_v1 import get_sport


MODEL_VERSION = "API2 UNIVERSAL SPORTS NAVIGATION V2 • TAP-FIRST HANDOFF"
PENDING_INTENT_KEY = "ks_universal_pending_intent_v2"
NAV_CONTAINER_KEY = v1.NAV_CONTAINER_KEY
SPORT_CONTROL_KEY = v1.SPORT_CONTROL_KEY
MARKET_CONTROL_KEY = v1.MARKET_CONTROL_KEY


def _queue_sport_intent(widget_key: str) -> None:
    sport_id = str(st.session_state.get(widget_key) or "").strip().lower()
    if get_sport(sport_id) is None:
        return
    st.session_state[PENDING_INTENT_KEY] = {
        "sport_id": sport_id,
        "market_id": None,
        "source": "tap",
    }


def _queue_market_intent(widget_key: str, sport_id: str) -> None:
    market_id = str(st.session_state.get(widget_key) or "").strip().lower()
    sport = get_sport(sport_id)
    if sport is None or market_id not in v1._MARKET_IDS_BY_SPORT.get(sport.id, ()):
        return
    st.session_state[PENDING_INTENT_KEY] = {
        "sport_id": sport.id,
        "market_id": market_id,
        "source": "tap",
    }


def render_universal_nav(state: RouteState) -> None:
    sports = v1._NAV_SPORTS
    sport_ids = v1._SPORT_IDS
    active_sport = get_sport(state.sport_id) or sports[0]
    sport_widget_key = f"{SPORT_CONTROL_KEY}__{state.epoch}"
    market_widget_key = f"{MARKET_CONTROL_KEY}__{state.epoch}"

    with st.container(key=NAV_CONTAINER_KEY):
        st.markdown(v1._NAV_CSS, unsafe_allow_html=True)
        st.markdown('<div class="ks-universal-brand">KYRE SPORTS</div>', unsafe_allow_html=True)
        st.pills(
            "Sport",
            sport_ids,
            default=state.sport_id if state.sport_id in sport_ids else active_sport.id,
            key=sport_widget_key,
            format_func=v1._SPORT_LABELS.get,
            selection_mode="single",
            label_visibility="collapsed",
            on_change=_queue_sport_intent,
            args=(sport_widget_key,),
        )

        market_ids = v1._MARKET_IDS_BY_SPORT[active_sport.id]
        st.pills(
            "Market",
            market_ids,
            default=state.market_id if state.market_id in market_ids else active_sport.default_market_id,
            key=market_widget_key,
            format_func=v1._MARKET_LABELS_BY_SPORT[active_sport.id].get,
            selection_mode="single",
            label_visibility="collapsed",
            on_change=_queue_market_intent,
            args=(market_widget_key, active_sport.id),
        )


__all__ = [
    "MARKET_CONTROL_KEY",
    "MODEL_VERSION",
    "NAV_CONTAINER_KEY",
    "PENDING_INTENT_KEY",
    "SPORT_CONTROL_KEY",
    "render_universal_nav",
]
