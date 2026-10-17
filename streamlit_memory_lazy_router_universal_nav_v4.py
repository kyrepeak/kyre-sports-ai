"""Universal Sports Navigation V4 — immediate same-run handoff bridge.

V3 remains the steady-state canonical owner. V4 only replaces the renderer
used by V2 during the current run with the stable V1 renderer that returns a
RouteIntent immediately. A fresh cross-sport tap is therefore committed and
masked before the legacy body can continue rendering the outgoing sport.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

import streamlit_memory_lazy_router_universal_nav_v2 as v2
import streamlit_memory_lazy_router_universal_nav_v3 as prior
import universal_sports_nav_ui_v1 as stable_ui


MODEL_VERSION = "API2 UNIVERSAL SPORTS NAVIGATION V4 • IMMEDIATE SAME-RUN HANDOFF"
FROZEN_PARENT = "streamlit_memory_lazy_router_universal_nav_v3"
PENDING_INTENT_KEY = getattr(v2, "PENDING_INTENT_KEY", "ks_universal_pending_intent_v2")
UNIVERSAL_NAV_ENABLED = True

# Keep the original V1 callable itself, not a module lookup. V2 temporarily
# assigns its renderer into the V1 module while delegating, so resolving the
# attribute later would recurse back into this bridge.
_STABLE_RENDERER = stable_ui.render_universal_nav


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def _render_immediate_handoff(state: Any) -> None:
    intent = _STABLE_RENDERER(state)
    if intent is None:
        return None

    destination = v2._prepare_pending_handoff(intent, st.session_state, st.query_params)
    v2._render_handoff_mask(destination)
    rerun = getattr(st, "rerun", None)
    if callable(rerun):
        rerun()
    return None


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
