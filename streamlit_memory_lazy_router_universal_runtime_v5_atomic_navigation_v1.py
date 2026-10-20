"""Terminal Universal Runtime V5 overlay with atomic destination replacement.

One selected route owns the destination surface. Route changes cover and clear
the outgoing surface before the selected destination is loaded. No non-selected
destination is proactively loaded from this terminal.
"""
from __future__ import annotations

from time import perf_counter

import streamlit as st

# Importing the current terminal first preserves its complete loader-overlay
# chain and patches the frozen Runtime V5 resolver to the latest destination
# ownership without changing any individual sport page.
import streamlit_memory_lazy_router_universal_runtime_v5_nfl_daily_picks_v3 as upstream
import streamlit_memory_lazy_router_universal_runtime_v5 as core
from universal_atomic_navigation_v1 import route_identity, transition_markup

MODEL_VERSION = "MONSTER UNIVERSAL ATOMIC NAVIGATION V1 • TERMINAL"
UPSTREAM_RUNTIME = "streamlit_memory_lazy_router_universal_runtime_v5_nfl_daily_picks_v3"
MAY_MODIFY_PROJECTION = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
LAST_RENDERED_ROUTE_KEY = "ks_atomic_navigation_last_rendered_route_v1"

record_bootstrap_import_ms = upstream.record_bootstrap_import_ms


def _render_atomic_active() -> object | None:
    runtime = core._load_runtime()
    pending = core._consume_pending_intent()
    if pending is not None:
        runtime = core._commit_navigation_intent(pending)
    runtime = core._reconcile_query_navigation(runtime)
    scope = core._normalize_active_scope(st.session_state, runtime)

    identity = route_identity(runtime.active)
    previous_identity = st.session_state.get(LAST_RENDERED_ROUTE_KEY)
    is_transition = previous_identity is not None and previous_identity != identity

    core._render_site_shell()
    core._render_destination_shell(runtime.active)

    # These placeholders keep one stable destination surface across reruns.
    # On a route handoff, the opaque shield is emitted before the old content
    # slot is cleared and before the selected destination begins loading.
    transition_slot = st.empty()
    destination_slot = st.empty()
    if is_transition:
        transition_slot.markdown(transition_markup(runtime.active), unsafe_allow_html=True)
        destination_slot.empty()

    adapter = core.resolve_destination(runtime.active)
    if not core.can_commit(scope, runtime):
        core._record_health_event("stale_commit_attempt", scope.generation)
        return None

    refresh_started = perf_counter()
    try:
        loaded = core.load_destination(adapter)
        current = core._load_runtime() if core.RUNTIME_STATE_SESSION_KEY in st.session_state else runtime
        if not core.can_commit(scope, current):
            core._record_health_event("stale_commit_attempt", scope.generation)
            return None

        with destination_slot.container():
            result = core.commit_if_current(scope, current, lambda: adapter.renderer(loaded))

        if core.can_commit(scope, current):
            st.session_state[LAST_RENDERED_ROUTE_KEY] = identity
            transition_slot.empty()
        core._record_health_event("live_refresh", runtime.generation, refresh_started)
        core._assert_active_runtime_health()
        return result
    except Exception:
        # Never uncover the outgoing route after a failed destination handoff.
        if is_transition:
            transition_slot.markdown(transition_markup(runtime.active), unsafe_allow_html=True)
        raise


def render_app() -> object | None:
    mode = str(
        st.session_state.get(core.RUNTIME_MODE_SESSION_KEY) or core.DEFAULT_RUNTIME_MODE
    ).strip().lower()
    if mode == core.V5_MODE_ACTIVE:
        return _render_atomic_active()
    return core._render_fallback()


__all__ = [
    "LAST_RENDERED_ROUTE_KEY",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "UPSTREAM_RUNTIME",
    "record_bootstrap_import_ms",
    "render_app",
]
