"""Universal Page Experience Runtime V4 — real-stage 0-100 loading progress."""
from __future__ import annotations

from time import perf_counter
from types import ModuleType

import streamlit as st

from universal_atomic_navigation_v1 import route_identity
from universal_page_experience_v3 import (
    page_experience_controller_markup_v3,
    page_experience_native_top_markup,
    page_experience_progress_markup,
    page_experience_progress_update_markup,
    page_experience_top_sentinel_markup,
)

MODEL_VERSION = "API2 UNIVERSAL PAGE EXPERIENCE RUNTIME V4 • LOADING PROGRESS"
LAST_RENDERED_ROUTE_KEY = "ks_universal_page_experience_last_rendered_route_v4"
MAY_MODIFY_PROJECTION = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0


def _mount_page_experience_controller_v4(route: object) -> bool:
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


def _emit_client_progress_v4(route: object, percent: int, status: str) -> bool:
    markup = page_experience_progress_update_markup(route, percent, status)
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


def _progress_stage_v4(slot: object, client_controller: bool, route: object, percent: int, status: str) -> None:
    if client_controller:
        _emit_client_progress_v4(route, percent, status)
        return
    slot.markdown(page_experience_progress_markup(route, percent, status), unsafe_allow_html=True)


def _render_page_experience_active_v4(core: ModuleType) -> object | None:
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
    core._render_destination_shell(runtime.active)

    transition_slot = st.empty()
    destination_slot = st.empty()

    if not core.can_commit(scope, runtime):
        core._record_health_event("stale_commit_attempt", scope.generation)
        return None

    if is_transition:
        transition_slot.markdown(
            page_experience_progress_markup(runtime.active, 15, "Routing page"),
            unsafe_allow_html=True,
        )

    client_controller = _mount_page_experience_controller_v4(runtime.active)
    if is_transition and client_controller:
        transition_slot.empty()
        _progress_stage_v4(transition_slot, client_controller, runtime.active, 15, "Routing page")

    adapter = core.resolve_destination(runtime.active)
    if is_transition and core.can_commit(scope, runtime):
        _progress_stage_v4(transition_slot, client_controller, runtime.active, 35, "Loading page module")

    refresh_started = perf_counter()
    try:
        loaded = core.load_destination(adapter)
        current = core._load_runtime() if core.RUNTIME_STATE_SESSION_KEY in st.session_state else runtime
        if not core.can_commit(scope, current):
            core._record_health_event("stale_commit_attempt", scope.generation)
            return None

        if is_transition:
            _progress_stage_v4(transition_slot, client_controller, runtime.active, 70, "Loading intelligence")
            _progress_stage_v4(transition_slot, client_controller, runtime.active, 90, "Preparing page")

        with destination_slot.container():
            result = core.commit_if_current(scope, current, lambda: adapter.renderer(loaded))

        if core.can_commit(scope, current):
            if is_transition:
                _progress_stage_v4(transition_slot, client_controller, runtime.active, 100, "Ready")
            st.session_state[LAST_RENDERED_ROUTE_KEY] = identity
            transition_slot.empty()
        core._record_health_event("live_refresh", runtime.generation, refresh_started)
        core._assert_active_runtime_health()
        return result
    except Exception:
        raise


def render_page_experience_app_v4(core: ModuleType) -> object | None:
    """Render exactly one current Runtime V5 destination with truthful progress."""
    mode = str(st.session_state.get(core.RUNTIME_MODE_SESSION_KEY) or core.DEFAULT_RUNTIME_MODE).strip().lower()
    if mode == core.V5_MODE_ACTIVE:
        return _render_page_experience_active_v4(core)
    return core._render_fallback()


__all__ = [
    "LAST_RENDERED_ROUTE_KEY",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "render_page_experience_app_v4",
]
