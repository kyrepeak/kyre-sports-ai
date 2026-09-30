"""WNBA PRA Speed V3 — Step 2 persistent pooled HTTP transport layer."""
from __future__ import annotations

from html import escape
from typing import Any, Callable

import streamlit as st

import wnba_pra_navigation_v2_step1 as navigation


MODEL_VERSION = "WNBA PRA SPEED V3 • STEP 2 POOLED HTTP"
TRANSPORT_CONTRACT = {
    "project": "WNBA PRA Speed V3",
    "step": "2/9",
    "scope": "persistent_https_pool_only",
    "http_pool_connections": 8,
    "http_pool_maxsize": 16,
    "adapter_hidden_retries": 0,
    "network_reads_added": 0,
    "reruns_added": 0,
    "model_runs_added": 0,
    "sportsbook_calls_added": 0,
    "monte_carlo_runs_added": 0,
    "projection_math_changed": False,
    "market_math_changed": False,
    "sportsbook_projection_influence": 0.0,
    "frozen_navigation_steps_1_through_7_modified": False,
    "frozen_speed_v3_step1_modified": False,
}


def _render_marker(state: navigation.NavigationState) -> None:
    st.markdown(
        '<span data-wnba-pra-speed-v3-step2="pooled-http" '
        f'data-wnba-pra-speed-v3-step2-page="{escape(state.page, quote=True)}" '
        'data-pool-connections="8" data-pool-maxsize="16" '
        'data-hidden-retries="0" style="display:none" aria-hidden="true"></span>',
        unsafe_allow_html=True,
    )


def render_step2_route(frozen_renderer: Callable[[], Any]) -> Any:
    state = navigation.current_state()
    _render_marker(state)
    return frozen_renderer()


__all__ = [
    "MODEL_VERSION",
    "TRANSPORT_CONTRACT",
    "render_step2_route",
]
