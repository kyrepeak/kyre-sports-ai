"""Universal Page Experience Runtime V5 — server-authoritative loading progress.

Repairs the production blank-body gap in V4. Browser JS remains an optional
instant-start enhancement, but the Streamlit server overlay is the authority
from route acceptance through destination commit. A mounted zero-height
component is never treated as proof that parent-DOM JavaScript executed.
"""
from __future__ import annotations

from time import perf_counter
from types import ModuleType

import streamlit as st

from universal_atomic_navigation_v1 import route_identity
from universal_page_experience_v3 import (
    page_experience_controller_markup_v3,
    page_experience_native_top_markup,
    page_experience_progress_markup,
    page_experience_top_sentinel_markup,
)

MODEL_VERSION = "API2 UNIVERSAL PAGE EXPERIENCE RUNTIME V5 • SERVER AUTHORITATIVE PROGRESS"
# Reuse V4's key intentionally so deployment of this repair does not erase the
# last rendered destination and misclassify the first post-deploy transition.
LAST_RENDERED_ROUTE_KEY = "ks_universal_page_experience_last_rendered_route_v4"
MAY_MODIFY_PROJECTION = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0


def _mount_page_experience_controller_v5(route: object) -> bool:
    """Mount browser helpers best-effort; never make server progress depend on them."""
    st.markdown(page_experience_native_top_markup(), unsafe_allow_html=True)
    markup = page_experience_controller_markup_v3(route)
    html = getattr(st, "html", None)
    if callable(html):
        try:
            html(markup, unsafe_allow_javascript=True)
            return True
        except TypeError:
            pass
    try:
        import streamlit.components.v1 as components
        components.html(markup, height=0, scrolling=False)
        return True
    except Exception:
        return False


def _server_progress(slot: object, route: object, percent: int, status: str) -> None:
    slot.markdown(page_experience_progress_markup(route, percent, status), unsafe_allow_html=True)


def _render_page_experience_active_v5(core: ModuleType) -> object | None:
    before_runtime = core._load_runtime()
    before_identity = route_identity(before_runtime.active)

    runtime = before_runtime
    pending = core._consume_pending_intent()
    if pending is not None:
        runtime = core._commit_navigation_intent(pending)
    runtime = core._reconcile_query_navigation(runtime)
    scope = core._normalize_active_scope(st.session_state, runtime)

    identity = route_identity(runtime.active)
    previous_identity = st.session_state.get(LAST_RENDERED_ROUTE_KEY)
    is_transition = before_identity != identity or (
        previous_identity is not None and previous_identity != identity
    )

    st.markdown(page_experience_top_sentinel_markup(), unsafe_allow_html=True)
    core._render_site_shell()
    core._render_destination_shell(runtime.active)

    transition_slot = st.empty()
    destination_slot = st.empty()

    if not core.can_commit(scope, runtime):
        core._record_health_event("stale_commit_attempt", scope.generation)
        return None

    # Server overlay is authoritative for the full load. The browser controller
    # can show an earlier 0% surface on pointerdown, but its success/failure never
    # clears this slot before the destination has committed.
    if is_transition:
        _server_progress(transition_slot, runtime.active, 15, "Routing page")

    _mount_page_experience_controller_v5(runtime.active)
    adapter = core.resolve_destination(runtime.active)

    if is_transition and core.can_commit(scope, runtime):
        _server_progress(transition_slot, runtime.active, 35, "Loading page module")

    refresh_started = perf_counter()
    loaded = core.load_destination(adapter)
    current = core._load_runtime() if core.RUNTIME_STATE_SESSION_KEY in st.session_state else runtime
    if not core.can_commit(scope, current):
        core._record_health_event("stale_commit_attempt", scope.generation)
        return None

    if is_transition:
        _server_progress(transition_slot, runtime.active, 70, "Loading intelligence")
        _server_progress(transition_slot, runtime.active, 90, "Preparing page")

    with destination_slot.container():
        result = core.commit_if_current(scope, current, lambda: adapter.renderer(loaded))

    if core.can_commit(scope, current):
        if is_transition:
            _server_progress(transition_slot, runtime.active, 100, "Ready")
        st.session_state[LAST_RENDERED_ROUTE_KEY] = identity
        # This is the only server-loader clear. It happens strictly after the
        # destination renderer has committed for the current generation.
        transition_slot.empty()

    core._record_health_event("live_refresh", runtime.generation, refresh_started)
    core._assert_active_runtime_health()
    return result


def render_page_experience_app_v5(core: ModuleType) -> object | None:
    """Render one current Runtime V5 destination with fail-closed server progress."""
    mode = str(st.session_state.get(core.RUNTIME_MODE_SESSION_KEY) or core.DEFAULT_RUNTIME_MODE).strip().lower()
    if mode == core.V5_MODE_ACTIVE:
        return _render_page_experience_active_v5(core)
    return core._render_fallback()


__all__ = [
    "LAST_RENDERED_ROUTE_KEY",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "render_page_experience_app_v5",
]
