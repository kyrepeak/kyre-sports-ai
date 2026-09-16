"""KYRE Streamlit Router V152 — CFB Game Total production activation.

Additive over frozen Router V151. This router changes only the production
activation boundary: the real Streamlit entrypoint can now boot V152 while all
existing route behavior continues through V151. A visible heartbeat is emitted
only for exact College Football -> Game Total so production verification can
reject stale deployments instead of treating a generic HTTP 200 as success.

Frozen Game Total Step-11/Step-12 calculations remain untouched. Sportsbook
projection influence stays 0.0%.
"""
from __future__ import annotations

import streamlit as st

import streamlit_memory_lazy_router_v151 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V152 • CFB GAME TOTAL PRODUCTION REBUILD"
PRODUCTION_HEARTBEAT = "CFB_GAME_TOTAL_V152_PRODUCTION_ACTIVE"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v151"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def _game_total_route_active() -> bool:
    return prior._game_total_route_active()


def _restore_game_total_route_from_query() -> bool:
    return prior._restore_game_total_route_from_query()


def _render_production_heartbeat() -> None:
    st.markdown(
        f'<div data-testid="cfb-game-total-v152-heartbeat" '
        f'style="font-size:.58rem;font-weight:800;color:#a7b6c5;margin:0 0 4px 2px">'
        f'{PRODUCTION_HEARTBEAT}</div>',
        unsafe_allow_html=True,
    )


def render_app() -> None:
    if not _game_total_route_active():
        _restore_game_total_route_from_query()
    if _game_total_route_active():
        _render_production_heartbeat()
    return prior.render_app()


__all__ = [
    "FROZEN_ROUTER",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "PRODUCTION_HEARTBEAT",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_game_total_route_active",
    "_render_production_heartbeat",
    "_restore_game_total_route_from_query",
    "record_bootstrap_import_ms",
    "render_app",
]
