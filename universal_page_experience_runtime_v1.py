"""Universal Page Experience Runtime V1 — universal TOP + fail-closed route handoff."""
from __future__ import annotations

from time import perf_counter
from types import ModuleType

import streamlit as st

from universal_atomic_navigation_v1 import route_identity
from universal_page_experience_v1 import (
    page_experience_controller_markup,
    page_experience_fallback_markup,
    page_experience_native_top_markup,
    page_experience_top_sentinel_markup,
)

MODEL_VERSION = "API2 UNIVERSAL PAGE EXPERIENCE RUNTIME V1"
LAST_RENDERED_ROUTE_KEY = "ks_universal_page_experience_last_rendered_route_v1"
MAY_MODIFY_PROJECTION = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0


def _mount_page_experience_controller(route: object) -> bool:
    st.markdown(page_experience_native_top_markup(), unsafe_allow_html=True)
    markup = page_experience_controller_markup(route)
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


def _render_page_experience_active(core: ModuleType) -> object | None:
    runtime = core._load_runtime()
    pending = core._consume_pending_intent()
    if pending is not None:
        runtime = core._commit_navigation_intent(pending)
    runtime = core._reconcile_query_navigation(runtime)
    scope = core._normalize_active_scope(st.session_state, runtime)

    identity = route_identity(runtime.active)
    previous_identity = st.session_state.get(LAST_RENDERED_ROUTE_KEY)
    is_transition = previous_identity is not None and previous_identity != identity

    st.markdown(page_experience_top_sentinel_markup(), unsafe_allow_html=True)
    core._render_site_shell()

    # Header V3 ordering contract: the universal navigation is rendered before
    # any placeholder that can later receive destination content. Streamlit
    # preserves element creation order, so this keeps the header physically at
    # the top of every route instead of below the filled destination slot.
    core._render_destination_shell(runtime.active)

    transition_slot = st.empty()
    destination_slot = st.empty()
    if is_transition:
        transition_slot.markdown(
            page_experience_fallback_markup(runtime.active),
            unsafe_allow_html=True,
        )

    client_controller = _mount_page_experience_controller(runtime.active)

    # Preserve the prior fail-closed client-mount seam as a redundant safety path.
    # The server takeover above is now unconditional for transitions.
    if is_transition and not client_controller:
        transition_slot.markdown(
            page_experience_fallback_markup(runtime.active),
            unsafe_allow_html=True,
        )

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
        # Fail closed: keep the server takeover covering the outgoing page while
        # Streamlit reports the destination error.
        raise


def render_page_experience_app(core: ModuleType) -> object | None:
    """Render Runtime V5 through the universal Page Experience shell."""
    mode = str(st.session_state.get(core.RUNTIME_MODE_SESSION_KEY) or core.DEFAULT_RUNTIME_MODE).strip().lower()
    if mode == core.V5_MODE_ACTIVE:
        return _render_page_experience_active(core)
    return core._render_fallback()


__all__ = [
    "LAST_RENDERED_ROUTE_KEY",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "render_page_experience_app",
]
