"""Universal Sports Navigation V4 — atomic route commit + rerun-safe terminal guard.

V3 remains the steady-state canonical owner. V4 registers atomic callbacks on
the universal sport and market pills so a tap commits canonical session state,
canonical URL, and legacy compatibility state before the next body-render run
begins. That removes the Streamlit fast-rerun race that could update the URL
while leaving the outgoing sport body on screen.

Historical router overlays may still rewrite ``st.selectbox`` while delegating,
so V4 also protects the final legacy-root boundary. The guard is explicitly
rerun-safe: if a fast rerun interrupts cleanup, the next run unwraps any leaked
V4 guard back to its original delegate before installing exactly one new guard.
No parent-router wrapper or rerun wrapper is stacked across Streamlit runs.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

import streamlit_memory_lazy_router_universal_nav_v2 as v2
import streamlit_memory_lazy_router_universal_nav_v3 as prior
import universal_sports_nav_ui_v1 as stable_ui
from universal_sports_nav_registry_v1 import get_market, get_sport


MODEL_VERSION = "API2 UNIVERSAL SPORTS NAVIGATION V4.4 • RERUN-SAFE TERMINAL OWNER"
FROZEN_PARENT = "streamlit_memory_lazy_router_universal_nav_v3"
PENDING_INTENT_KEY = getattr(v2, "PENDING_INTENT_KEY", "ks_universal_pending_intent_v2")
UNIVERSAL_NAV_ENABLED = True
ROUTE_TRANSITION_KEY = "ks_universal_route_transition_v1"

# Keep the original V1 callable itself, not a module lookup. V2 temporarily
# assigns its renderer into the V1 module while delegating, so resolving the
# attribute later would recurse back into this bridge.
_STABLE_RENDERER = stable_ui.render_universal_nav
_ROOT_GUARD_MARKER = "_api2_v4_terminal_guard"
_ROOT_GUARD_DELEGATE = "_api2_v4_terminal_delegate"


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


def _record_route_transition(state: Any) -> None:
    """Persist the exact destination generation before Streamlit reruns."""
    st.session_state[ROUTE_TRANSITION_KEY] = {
        "sport_id": str(getattr(state, "sport_id", "") or "").strip().lower(),
        "market_id": str(getattr(state, "market_id", "") or "").strip().lower(),
        "epoch": int(getattr(state, "epoch", 0) or 0),
        "confirmed": False,
    }


def _transition_matches_state(transition: Any, state: Any) -> bool:
    if not isinstance(transition, dict):
        return False
    return (
        str(transition.get("sport_id") or "").strip().lower()
        == str(getattr(state, "sport_id", "") or "").strip().lower()
        and str(transition.get("market_id") or "").strip().lower()
        == str(getattr(state, "market_id", "") or "").strip().lower()
        and int(transition.get("epoch") or 0) == int(getattr(state, "epoch", 0) or 0)
    )


def _render_pending_transition_mask() -> Any:
    """Cover any stale outgoing body until the exact destination finishes rendering."""
    transition = st.session_state.get(ROUTE_TRANSITION_KEY)
    if not isinstance(transition, dict):
        return None

    sport_id = str(transition.get("sport_id") or "").strip().lower()
    market_id = str(transition.get("market_id") or "").strip().lower()
    if not sport_id or not market_id:
        st.session_state.pop(ROUTE_TRANSITION_KEY, None)
        return None

    sport = get_sport(sport_id)
    market = get_market(sport_id, market_id)
    sport_label = sport.label if sport is not None else sport_id.upper()
    market_label = market.label if market is not None else market_id.replace("-", " ").title()

    placeholder = st.empty()
    placeholder.markdown(
        f"""
<div class="ks-route-transition-v4">
  <div class="ks-route-transition-v4__brand">KYRE SPORTS AI</div>
  <div class="ks-route-transition-v4__card">
    <div class="ks-route-transition-v4__title">Loading {sport_label}</div>
    <div class="ks-route-transition-v4__market">{market_label}</div>
    <div class="ks-route-transition-v4__sub">Switching to the selected page…</div>
  </div>
</div>
<style>
.ks-route-transition-v4{{position:fixed;inset:0;z-index:2147483647;background:#060b13;display:flex;flex-direction:column;align-items:center;justify-content:flex-start;padding:calc(env(safe-area-inset-top,0px) + 54px) 20px 28px}}
.ks-route-transition-v4__brand{{width:min(650px,94vw);border:1px solid rgba(56,189,248,.25);border-radius:20px;padding:16px 22px;color:#eaf6ff;font-size:.86rem;font-weight:900;letter-spacing:.16em;box-sizing:border-box}}
.ks-route-transition-v4__brand::first-letter{{color:#7dd3fc}}
.ks-route-transition-v4__card{{margin-top:22px;width:min(650px,94vw);border:1px solid rgba(56,189,248,.24);border-radius:22px;background:#0c1420;padding:28px 24px;text-align:center;box-sizing:border-box;box-shadow:0 20px 60px rgba(0,0,0,.34)}}
.ks-route-transition-v4__title{{font-size:1.22rem;font-weight:900;color:#f8fafc}}
.ks-route-transition-v4__market{{margin-top:7px;font-size:.94rem;font-weight:800;color:#7dd3fc}}
.ks-route-transition-v4__sub{{margin-top:9px;font-size:.78rem;color:#94a3b8}}
</style>
""",
        unsafe_allow_html=True,
    )
    return placeholder


def _confirm_route_transition(state: Any) -> bool:
    transition = st.session_state.get(ROUTE_TRANSITION_KEY)
    if not _transition_matches_state(transition, state):
        return False
    updated = dict(transition)
    updated["confirmed"] = True
    st.session_state[ROUTE_TRANSITION_KEY] = updated
    return True


def _finish_route_transition(placeholder: Any) -> None:
    if placeholder is None:
        return
    transition = st.session_state.get(ROUTE_TRANSITION_KEY)
    if not isinstance(transition, dict) or not bool(transition.get("confirmed")):
        return
    placeholder.empty()
    st.session_state.pop(ROUTE_TRANSITION_KEY, None)


def _clear_route_transition_mask(placeholder: Any) -> None:
    """Expose a real rendering error instead of hiding it behind the mask."""
    if placeholder is None:
        return
    try:
        placeholder.empty()
    except Exception:
        pass


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

    # Commit session/compatibility state before URL mutation or rerun can
    # interrupt this callback. The next run starts with one complete owner.
    v2.prior._persist_state(next_state, st.session_state)
    v2.prior.apply_legacy_route_state(next_state, st.session_state)
    _record_route_transition(next_state)

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

    # The callback already advanced the epoch; replacement pill widgets receive
    # fresh identities, preventing a callback/rerun loop.
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
    # Callback commits are authoritative in Streamlit 1.66+. Returning an intent
    # remains a safe fallback for test doubles and non-callback environments.
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


def _unwrap_terminal_root(candidate: Any) -> Any:
    """Collapse leaked V4 guards from interrupted fast-rerun cleanup."""
    current = candidate
    seen: set[int] = set()
    while getattr(current, _ROOT_GUARD_MARKER, False):
        identity = id(current)
        if identity in seen:
            raise RuntimeError("API2_V4_ROOT_GUARD_CYCLE")
        seen.add(identity)
        delegate = getattr(current, _ROOT_GUARD_DELEGATE, None)
        if not callable(delegate):
            raise RuntimeError("API2_V4_ROOT_GUARD_DELEGATE_MISSING")
        current = delegate
    return current


def _terminal_root_guard(delegate: Any) -> Any:
    """Return one canonical root renderer and retain its original delegate."""
    delegate = _unwrap_terminal_root(delegate)

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
        _confirm_route_transition(state)

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
            return delegate()
        finally:
            v2.legacy_root.st.selectbox = downstream_selectbox

    setattr(_guarded_root_render, _ROOT_GUARD_MARKER, True)
    setattr(_guarded_root_render, _ROOT_GUARD_DELEGATE, delegate)
    return _guarded_root_render


def render_app() -> Any:
    transition_placeholder = _render_pending_transition_mask()
    original_renderer = v2.nav_ui.render_universal_nav

    # A fast rerun may interrupt the prior run before its finally block restores
    # the root. Normalize that leaked state first, then install exactly one guard.
    original_root_render = _unwrap_terminal_root(v2.legacy_root.render_app)
    guarded_root_render = _terminal_root_guard(original_root_render)

    _trace(
        "V4_ENTER",
        query_sport=_query_value("sport"),
        query_market=_query_value("market"),
        canonical_sport=st.session_state.get("ks_universal_sport"),
        canonical_market=st.session_state.get("ks_universal_market"),
        legacy_sport=st.session_state.get("ks_sport_touch"),
        leaked_root_guard=(v2.legacy_root.render_app is not original_root_render),
    )
    v2.nav_ui.render_universal_nav = _render_immediate_handoff
    v2.legacy_root.render_app = guarded_root_render
    try:
        result = prior.render_app()
        _finish_route_transition(transition_placeholder)
        return result
    except Exception:
        _clear_route_transition_mask(transition_placeholder)
        raise
    finally:
        # Restore only our exact guard. If a downstream owner deliberately moved
        # the root pointer, do not overwrite that newer authority.
        if v2.legacy_root.render_app is guarded_root_render:
            v2.legacy_root.render_app = original_root_render
        v2.nav_ui.render_universal_nav = original_renderer


__all__ = [
    "FROZEN_PARENT",
    "MODEL_VERSION",
    "PENDING_INTENT_KEY",
    "ROUTE_TRANSITION_KEY",
    "UNIVERSAL_NAV_ENABLED",
    "_commit_pill_intent",
    "_render_with_atomic_pill_callbacks",
    "_terminal_root_guard",
    "_unwrap_terminal_root",
    "record_bootstrap_import_ms",
    "render_app",
]
