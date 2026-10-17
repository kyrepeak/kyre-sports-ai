"""Universal Sports Navigation V4 — same-run + terminal ownership bridge.

V3 remains the steady-state canonical owner. V4 preserves the immediate V1
RouteIntent handoff and also guards the final legacy-root render boundary.
Historical router overlays may temporarily rewrite ``st.selectbox`` while they
delegate; the terminal guard therefore reapplies only the canonical global
sport/market selector bridge after those overlays have installed their seams and
immediately before the legacy root chooses the body owner. Page-level controls
still delegate through the downstream selector unchanged.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

import streamlit_memory_lazy_router_universal_nav_v2 as v2
import streamlit_memory_lazy_router_universal_nav_v3 as prior
import universal_sports_nav_ui_v1 as stable_ui


MODEL_VERSION = "API2 UNIVERSAL SPORTS NAVIGATION V4.2 • SAME-RUN TERMINAL OWNER"
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

    # Universal V1 must receive the tap itself so its local RouteState, URL,
    # legacy compatibility state, and destination render owner all advance in
    # the same Streamlit pass.
    return intent


def _terminal_root_guard(delegate: Any) -> Any:
    """Return a root renderer that makes canonical navigation the final owner.

    Lower historical overlays are free to wrap ``st.selectbox`` first. At the
    exact root boundary we capture that downstream selector, place the Universal
    V1 compatibility bridge above it for global sport/market controls only, run
    the unchanged root renderer, then restore the downstream selector exactly.
    """

    def _guarded_root_render() -> Any:
        state = v2.prior._resolve_initial_state(st.session_state, st.query_params)
        v2.prior._persist_state(state, st.session_state)
        v2.prior.apply_legacy_route_state(state, st.session_state)

        downstream_selectbox = v2.legacy_root.st.selectbox
        v2.legacy_root.st.selectbox = v2.prior.make_legacy_selectbox_bridge(
            downstream_selectbox,
            state,
        )
        try:
            return delegate()
        finally:
            v2.legacy_root.st.selectbox = downstream_selectbox

    return _guarded_root_render


def render_app() -> Any:
    original_renderer = v2.nav_ui.render_universal_nav
    original_root_render = v2.legacy_root.render_app

    v2.nav_ui.render_universal_nav = _render_immediate_handoff
    v2.legacy_root.render_app = _terminal_root_guard(original_root_render)
    try:
        return prior.render_app()
    finally:
        v2.legacy_root.render_app = original_root_render
        v2.nav_ui.render_universal_nav = original_renderer


__all__ = [
    "FROZEN_PARENT",
    "MODEL_VERSION",
    "PENDING_INTENT_KEY",
    "UNIVERSAL_NAV_ENABLED",
    "_terminal_root_guard",
    "record_bootstrap_import_ms",
    "render_app",
]
