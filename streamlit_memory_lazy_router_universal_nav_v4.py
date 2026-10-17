"""Universal Sports Navigation V4 — atomic same-run route ownership bridge.

V3 remains the steady-state canonical owner. V4 preserves the immediate V1
RouteIntent fallback and registers atomic callbacks on the universal sport and
market pills. A pill change commits canonical session state, canonical URL, and
legacy compatibility state *before* the next body-render run begins, then issues
one explicit full rerun. This avoids Streamlit fast-rerun races that can update
the URL while leaving the outgoing sport body on screen.

The final legacy-root guard remains as defense in depth: historical router
overlays may temporarily rewrite ``st.selectbox`` while they delegate, so the
canonical global selector bridge is reapplied immediately before the legacy
root chooses the body owner. Page-level controls continue to delegate through
the downstream selector unchanged.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

import streamlit_memory_lazy_router_universal_nav_v2 as v2
import streamlit_memory_lazy_router_universal_nav_v3 as prior
import universal_sports_nav_ui_v1 as stable_ui


MODEL_VERSION = "API2 UNIVERSAL SPORTS NAVIGATION V4.3 • ATOMIC PILL COMMIT"
FROZEN_PARENT = "streamlit_memory_lazy_router_universal_nav_v3"
PENDING_INTENT_KEY = getattr(v2, "PENDING_INTENT_KEY", "ks_universal_pending_intent_v2")
UNIVERSAL_NAV_ENABLED = True

# Keep the original V1 callable itself, not a module lookup. V2 temporarily
# assigns its renderer into the V1 module while delegating, so resolving the
# attribute later would recurse back into this bridge.
_STABLE_RENDERER = stable_ui.render_universal_nav


def _query_value(key: str) -> str:
    try:
        raw = st.query_params.get(key)
    except Exception:
        raw = None
    if isinstance(raw, (list, tuple)):
        raw = raw[-1] if raw else None
    return str(raw or "")


def _trace(marker: str, **values: Any) -> None:
    """Emit compact server-side diagnostics for the authoritative browser proof."""
    payload = " ".join(f"{key}={value!r}" for key, value in values.items())
    print(f"API2_V4_TRACE {marker} {payload}".rstrip(), flush=True)


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def _commit_pill_intent(
    state: Any,
    *,
    sport_widget_key: str | None = None,
    market_widget_key: str | None = None,
) -> None:
    """Commit one widget change before body rendering, then rerun exactly once."""
    sport_id = None
    market_id = None
    if sport_widget_key:
        sport_id = str(st.session_state.get(sport_widget_key) or "").strip().lower() or None
    if market_widget_key:
        market_id = str(st.session_state.get(market_widget_key) or "").strip().lower() or None

    if sport_id and sport_id == str(getattr(state, "sport_id", "") or "").strip().lower():
        sport_id = None
    if market_id and market_id == str(getattr(state, "market_id", "") or "").strip().lower():
        market_id = None
    if sport_id is None and market_id is None:
        return

    outgoing_sport = str(getattr(state, "sport_id", "") or "").strip().lower()
    intent = v2.prior.RouteIntent(
        sport_id=sport_id or getattr(state, "sport_id", None),
        market_id=market_id,
        source="tap",
    )
    next_state = v2.prior._apply_intent(state, intent)
    incoming_sport = str(getattr(next_state, "sport_id", "") or "").strip().lower()

    if outgoing_sport and incoming_sport and incoming_sport != outgoing_sport:
        v2._clear_cross_route_query_context(st.query_params)
        v2._clear_cross_route_session_context(st.session_state, outgoing_sport)

    # Session and compatibility state are committed before URL mutation or any
    # rerun can interrupt this callback.  The next run therefore starts with a
    # complete single-owner route even under Streamlit's runner.fastReruns.
    v2.prior._persist_state(next_state, st.session_state)
    v2.prior.apply_legacy_route_state(next_state, st.session_state)

    patch = v2.prior.query_patch_for_state(next_state, st.query_params)
    _trace(
        "CALLBACK_COMMIT",
        outgoing=outgoing_sport,
        incoming=incoming_sport,
        market=getattr(next_state, "market_id", None),
        epoch=getattr(next_state, "epoch", None),
        query_sport=_query_value("sport"),
        query_market=_query_value("market"),
    )
    v2.prior.apply_query_patch(st.query_params, patch)

    # A single explicit full rerun is intentional here. The callback already
    # advanced the epoch, so the replacement pill widgets have new identities
    # and cannot re-fire this callback in a loop.
    st.rerun()


def _render_with_atomic_pill_callbacks(state: Any) -> Any:
    """Render stable V1 pills while registering pre-render route callbacks."""
    native_pills = getattr(st, "pills", None)
    if not callable(native_pills):
        return _STABLE_RENDERER(state)

    def atomic_pills(label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
        widget_key = str(kwargs.get("key") or "")
        clean_label = str(label or "").strip()
        if clean_label == "Sport" and widget_key:
            kwargs["on_change"] = lambda key=widget_key, snapshot=state: _commit_pill_intent(
                snapshot,
                sport_widget_key=key,
            )
        elif clean_label == "Market" and widget_key:
            kwargs["on_change"] = lambda key=widget_key, snapshot=state: _commit_pill_intent(
                snapshot,
                market_widget_key=key,
            )
        return native_pills(label, options, *args, **kwargs)

    st.pills = atomic_pills
    try:
        return _STABLE_RENDERER(state)
    finally:
        st.pills = native_pills


def _render_immediate_handoff(state: Any) -> Any:
    # The callback path is authoritative in Streamlit 1.66+. Returning an intent
    # remains a safe fallback for test doubles or any environment where the
    # widget callback was not the source of the current route change.
    intent = _render_with_atomic_pill_callbacks(state)
    if intent is None:
        return None

    outgoing_sport = str(getattr(state, "sport_id", "") or "").strip().lower()
    incoming_sport = str(getattr(intent, "sport_id", "") or outgoing_sport).strip().lower()
    _trace(
        "INTENT_FALLBACK",
        outgoing=outgoing_sport,
        incoming=incoming_sport,
        query_sport=_query_value("sport"),
        query_market=_query_value("market"),
        canonical_sport=st.session_state.get("ks_universal_sport"),
        legacy_sport=st.session_state.get("ks_sport_touch"),
    )
    if outgoing_sport and incoming_sport and incoming_sport != outgoing_sport:
        v2._clear_cross_route_query_context(st.query_params)
        v2._clear_cross_route_session_context(st.session_state, outgoing_sport)
    return intent


def _terminal_root_guard(delegate: Any) -> Any:
    """Return a root renderer that makes canonical navigation the final owner."""

    def _guarded_root_render() -> Any:
        state = v2.prior._resolve_initial_state(st.session_state, st.query_params)
        _trace(
            "ROOT_ENTER",
            delegate_module=getattr(delegate, "__module__", ""),
            delegate_name=getattr(delegate, "__name__", ""),
            state_sport=getattr(state, "sport_id", None),
            state_market=getattr(state, "market_id", None),
            query_sport=_query_value("sport"),
            query_market=_query_value("market"),
            canonical_sport=st.session_state.get("ks_universal_sport"),
            canonical_market=st.session_state.get("ks_universal_market"),
            legacy_sport=st.session_state.get("ks_sport_touch"),
            mlb_live=st.session_state.get("ks_mlb_live_odds_route"),
        )
        v2.prior._persist_state(state, st.session_state)
        v2.prior.apply_legacy_route_state(state, st.session_state)

        downstream_selectbox = v2.legacy_root.st.selectbox
        canonical_selectbox = v2.prior.make_legacy_selectbox_bridge(downstream_selectbox, state)

        def traced_selectbox(label: Any, options: Any, *args: Any, **kwargs: Any) -> Any:
            selected = canonical_selectbox(label, options, *args, **kwargs)
            if str(label or "") == "🏟️ Sport":
                _trace(
                    "ROOT_SPORT_SELECT",
                    selected=selected,
                    state_sport=getattr(state, "sport_id", None),
                    canonical_sport=st.session_state.get("ks_universal_sport"),
                    legacy_sport=st.session_state.get("ks_sport_touch"),
                    query_sport=_query_value("sport"),
                )
            return selected

        v2.legacy_root.st.selectbox = traced_selectbox
        try:
            result = delegate()
            _trace(
                "ROOT_EXIT",
                state_sport=getattr(state, "sport_id", None),
                canonical_sport=st.session_state.get("ks_universal_sport"),
                legacy_sport=st.session_state.get("ks_sport_touch"),
                query_sport=_query_value("sport"),
            )
            return result
        finally:
            v2.legacy_root.st.selectbox = downstream_selectbox

    return _guarded_root_render


def _traced_parent_guard(delegate: Any) -> Any:
    def _guarded_parent_render() -> Any:
        _trace(
            "PARENT_ENTER",
            module=getattr(delegate, "__module__", ""),
            name=getattr(delegate, "__name__", ""),
            query_sport=_query_value("sport"),
            query_market=_query_value("market"),
            canonical_sport=st.session_state.get("ks_universal_sport"),
            canonical_market=st.session_state.get("ks_universal_market"),
            legacy_sport=st.session_state.get("ks_sport_touch"),
        )
        try:
            result = delegate()
        except BaseException as exc:
            _trace(
                "PARENT_ABORT",
                exc_type=type(exc).__name__,
                query_sport=_query_value("sport"),
                canonical_sport=st.session_state.get("ks_universal_sport"),
                legacy_sport=st.session_state.get("ks_sport_touch"),
            )
            raise
        _trace(
            "PARENT_EXIT",
            query_sport=_query_value("sport"),
            canonical_sport=st.session_state.get("ks_universal_sport"),
            legacy_sport=st.session_state.get("ks_sport_touch"),
        )
        return result

    return _guarded_parent_render


def render_app() -> Any:
    original_renderer = v2.nav_ui.render_universal_nav
    original_root_render = v2.legacy_root.render_app
    immediate_parent = getattr(v2.prior, "prior", None)
    original_parent_render = getattr(immediate_parent, "render_app", None)
    original_rerun = st.rerun

    def traced_rerun(*args: Any, **kwargs: Any) -> Any:
        _trace(
            "RERUN",
            query_sport=_query_value("sport"),
            query_market=_query_value("market"),
            canonical_sport=st.session_state.get("ks_universal_sport"),
            canonical_market=st.session_state.get("ks_universal_market"),
            legacy_sport=st.session_state.get("ks_sport_touch"),
        )
        return original_rerun(*args, **kwargs)

    _trace(
        "V4_ENTER",
        query_sport=_query_value("sport"),
        query_market=_query_value("market"),
        canonical_sport=st.session_state.get("ks_universal_sport"),
        canonical_market=st.session_state.get("ks_universal_market"),
        legacy_sport=st.session_state.get("ks_sport_touch"),
    )
    v2.nav_ui.render_universal_nav = _render_immediate_handoff
    v2.legacy_root.render_app = _terminal_root_guard(original_root_render)
    if immediate_parent is not None and original_parent_render is not None:
        immediate_parent.render_app = _traced_parent_guard(original_parent_render)
    st.rerun = traced_rerun
    try:
        return prior.render_app()
    finally:
        st.rerun = original_rerun
        if immediate_parent is not None and original_parent_render is not None:
            immediate_parent.render_app = original_parent_render
        v2.legacy_root.render_app = original_root_render
        v2.nav_ui.render_universal_nav = original_renderer


__all__ = [
    "FROZEN_PARENT",
    "MODEL_VERSION",
    "PENDING_INTENT_KEY",
    "UNIVERSAL_NAV_ENABLED",
    "_commit_pill_intent",
    "_render_with_atomic_pill_callbacks",
    "_terminal_root_guard",
    "record_bootstrap_import_ms",
    "render_app",
]
