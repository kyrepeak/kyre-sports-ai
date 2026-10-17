"""Universal Sports Navigation V1 additive production activation overlay.

This layer is the single authority for global sport/market navigation. Existing
router ancestry remains the renderer/compatibility implementation underneath;
its route-hygiene and top-level selector ownership are neutralized only for the
duration of delegation and restored in ``finally``.
"""
from __future__ import annotations

from typing import Any, Mapping

import streamlit as st

import streamlit_memory_lazy_router_nfl_spread_mobile_repair_v1 as prior
import universal_sports_nav_ui_v1 as nav_ui
from universal_sports_nav_compat_v1 import (
    apply_legacy_route_state,
    make_legacy_markdown_bridge,
    make_legacy_selectbox_bridge,
)
from universal_sports_nav_controller_v1 import (
    RouteIntent,
    RouteState,
    apply_market_intent,
    apply_sport_intent,
    resolve_route,
)
from universal_sports_nav_url_v1 import (
    apply_query_patch,
    normalize_legacy_query,
    query_patch_for_state,
)


MODEL_VERSION = "API2 UNIVERSAL SPORTS NAVIGATION V1"
FROZEN_PARENT = "streamlit_memory_lazy_router_nfl_spread_mobile_repair_v1"
UNIVERSAL_NAV_ENABLED = True

_MEMORY_KEY = "ks_universal_last_market_by_sport"
_SPORT_KEY = "ks_universal_sport"
_MARKET_KEY = "ks_universal_market"
_SOURCE_KEY = "ks_universal_nav_source"
_EPOCH_KEY = "ks_universal_epoch"


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def _memory_from_session(session: Mapping[str, Any]) -> dict[str, str]:
    raw = session.get(_MEMORY_KEY, {})
    if not isinstance(raw, Mapping):
        return {}
    return {str(key): str(value) for key, value in raw.items()}


def _epoch_from_session(session: Mapping[str, Any]) -> int:
    try:
        return int(session.get(_EPOCH_KEY, 0) or 0)
    except (TypeError, ValueError):
        return 0


def _persist_state(state: RouteState, session: Any) -> None:
    session[_SPORT_KEY] = state.sport_id
    session[_MARKET_KEY] = state.market_id
    session[_SOURCE_KEY] = state.source
    session[_EPOCH_KEY] = state.epoch
    session[_MEMORY_KEY] = dict(state.last_market_by_sport)


def _resolve_initial_state(session: Mapping[str, Any], query: Mapping[str, Any]) -> RouteState:
    normalized = normalize_legacy_query(query, session)
    state = resolve_route(
        canonical_sport=normalized.sport_id,
        canonical_market=normalized.market_id,
        last_market_by_sport=_memory_from_session(session),
        epoch=_epoch_from_session(session),
    )

    # Browser Back/Forward or a shared canonical URL can change route identity
    # without a new pills click. Advance the UI generation whenever the valid
    # canonical route differs from the route we last persisted, so stale native
    # widget state cannot overwrite the URL on the next render.
    persisted_sport = str(session.get(_SPORT_KEY) or "").strip().lower()
    persisted_market = str(session.get(_MARKET_KEY) or "").strip().lower()
    has_canonical_route = bool(normalized.sport_id and normalized.market_id)
    if (
        has_canonical_route
        and persisted_sport
        and persisted_market
        and (persisted_sport, persisted_market) != (state.sport_id, state.market_id)
    ):
        return RouteState(
            state.sport_id,
            state.market_id,
            state.source,
            state.epoch + 1,
            state.last_market_by_sport,
        )
    return state


def _apply_intent(state: RouteState, intent: RouteIntent | None) -> RouteState:
    if intent is None or intent.source != "tap":
        return state

    next_state = state
    if intent.sport_id and intent.sport_id != state.sport_id:
        next_state = apply_sport_intent(next_state, intent.sport_id)
        if intent.market_id:
            next_state = apply_market_intent(next_state, intent.market_id)
        return next_state

    if intent.market_id:
        return apply_market_intent(next_state, intent.market_id)
    return next_state


def _no_route_hygiene(*args: Any, **kwargs: Any) -> bool:
    """Universal Nav already normalized global route state above the parent."""
    return False


def _identity_selectbox_factory(delegate):
    """Prevent the immediate parent from installing a second global nav owner."""
    return delegate


def render_app() -> Any:
    # 1–2: normalize cold-start inputs and resolve the one canonical authority.
    state = _resolve_initial_state(st.session_state, st.query_params)

    # 3–4: render once and apply explicit user intent at highest precedence.
    intent = nav_ui.render_universal_nav(state)
    state = _apply_intent(state, intent)
    _persist_state(state, st.session_state)

    # 5: canonical URL patch is planned/applied once; idempotent patches no-op.
    patch = query_patch_for_state(state, st.query_params)
    apply_query_patch(st.query_params, patch)

    # 6: feed the existing frozen/current renderer ancestry its compatibility
    # inputs without erasing other sports' remembered market keys.
    apply_legacy_route_state(state, st.session_state)

    # 7–9: suppress only obsolete global navigation/hero presentation, delegate,
    # and always restore parent/Streamlit callable ownership even if rendering raises.
    original_selectbox = st.selectbox
    original_markdown = st.markdown
    original_hygiene = prior.apply_route_hygiene
    original_parent_bridge_factory = prior._make_selectbox_bridge

    st.selectbox = make_legacy_selectbox_bridge(original_selectbox, state)
    st.markdown = make_legacy_markdown_bridge(original_markdown)
    prior.apply_route_hygiene = _no_route_hygiene
    prior._make_selectbox_bridge = _identity_selectbox_factory
    try:
        return prior.render_app()
    finally:
        prior._make_selectbox_bridge = original_parent_bridge_factory
        prior.apply_route_hygiene = original_hygiene
        st.markdown = original_markdown
        st.selectbox = original_selectbox


__all__ = [
    "FROZEN_PARENT",
    "MODEL_VERSION",
    "UNIVERSAL_NAV_ENABLED",
    "record_bootstrap_import_ms",
    "render_app",
]
