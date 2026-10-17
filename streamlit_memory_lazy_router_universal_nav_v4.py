"""Universal Sports Navigation V4 — immediate same-run handoff bridge.

V3 remains the steady-state canonical owner. V4 replaces the renderer used by
V2 during the current run with the stable V1 renderer that returns a RouteIntent
immediately. Cross-sport cleanup happens before the intent is returned to V1 so
V1 can update canonical state and the legacy render owner in the same pass.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

import streamlit_memory_lazy_router_universal_nav_v2 as v2
import streamlit_memory_lazy_router_universal_nav_v3 as prior
import universal_sports_nav_ui_v1 as stable_ui


MODEL_VERSION = "API2 UNIVERSAL SPORTS NAVIGATION V4.1 • SAME-RUN SINGLE OWNER"
FROZEN_PARENT = "streamlit_memory_lazy_router_universal_nav_v3"
PENDING_INTENT_KEY = getattr(v2, "PENDING_INTENT_KEY", "ks_universal_pending_intent_v2")
UNIVERSAL_NAV_ENABLED = True

# Keep the original V1 callable itself, not a module lookup. V2 temporarily
# assigns its renderer into the V1 module while delegating, so resolving the
# attribute later would recurse back into this bridge.
_STABLE_RENDERER = stable_ui.render_universal_nav


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def _render_immediate_handoff(state: Any) -> Any:
    intent = _STABLE_RENDERER(state)
    if intent is None:
        return None

    outgoing_sport = str(getattr(state, "sport_id", "") or "").strip().lower()
    incoming_sport = str(getattr(intent, "sport_id", "") or outgoing_sport).strip().lower()
    if outgoing_sport and incoming_sport and incoming_sport != outgoing_sport:
        v2._clear_cross_route_query_context(st.query_params)
        v2._clear_cross_route_session_context(st.session_state, outgoing_sport)

    # This renderer is called from inside Universal Nav V1. Returning the tap
    # intent preserves V1's single-owner contract: V1 applies the intent to its
    # local RouteState before it patches the URL, bridges legacy selectors, and
    # renders the destination body. Consuming the intent here and forcing an
    # extra rerun can leave URL/session on the new sport while V1 still holds
    # the outgoing sport in its local state for the current pass.
    return intent


def render_app() -> Any:
    original_renderer = v2.nav_ui.render_universal_nav
    v2.nav_ui.render_universal_nav = _render_immediate_handoff
    try:
        return prior.render_app()
    finally:
        v2.nav_ui.render_universal_nav = original_renderer


__all__ = [
    "FROZEN_PARENT",
    "MODEL_VERSION",
    "PENDING_INTENT_KEY",
    "UNIVERSAL_NAV_ENABLED",
    "record_bootstrap_import_ms",
    "render_app",
]
