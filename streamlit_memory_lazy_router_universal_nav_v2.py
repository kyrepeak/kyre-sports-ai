"""Tap-first Universal Sports Navigation V2 activation overlay.

This additive layer fixes first-tap cross-sport switching without reopening the
frozen V1 router. A widget callback records the newest explicit tap before the
next rerun. V2 consumes that intent, clears stale route-local URL context on a
sport handoff, updates the canonical route, then delegates through V1 with only
its renderer temporarily upgraded to the callback-driven V2 UI.
"""
from __future__ import annotations

from typing import Any, Mapping, MutableMapping

import streamlit as st

import streamlit_memory_lazy_router_universal_nav_v1 as prior
import universal_sports_nav_ui_v2 as nav_ui
from universal_sports_nav_controller_v1 import RouteIntent, resolve_route
from universal_sports_nav_url_v1 import apply_query_patch, query_patch_for_state


MODEL_VERSION = "API2 UNIVERSAL SPORTS NAVIGATION V2 • TAP-FIRST HANDOFF"
FROZEN_PARENT = "streamlit_memory_lazy_router_universal_nav_v1"
UNIVERSAL_NAV_ENABLED = True
PENDING_INTENT_KEY = nav_ui.PENDING_INTENT_KEY

_ROUTE_LOCAL_QUERY_KEYS = frozenset({"date", "game_id", "player_id"})


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def _consume_pending_intent(session: MutableMapping[str, Any]) -> RouteIntent | None:
    raw = session.pop(PENDING_INTENT_KEY, None)
    if not isinstance(raw, Mapping) or str(raw.get("source") or "") != "tap":
        return None
    sport_id = str(raw.get("sport_id") or "").strip().lower() or None
    market_id = str(raw.get("market_id") or "").strip().lower() or None
    if not sport_id and not market_id:
        return None
    return RouteIntent(sport_id=sport_id, market_id=market_id, source="tap")


def _clear_cross_route_query_context(query: MutableMapping[str, Any]) -> None:
    """Remove page-local/legacy route state before a cross-sport handoff."""
    for raw_key in list(query.keys()):
        key = str(raw_key)
        if key in _ROUTE_LOCAL_QUERY_KEYS or key.startswith("ks_"):
            try:
                del query[raw_key]
            except Exception:
                continue


def _prepare_pending_handoff(intent: RouteIntent, session: MutableMapping[str, Any], query: MutableMapping[str, Any]) -> None:
    current = prior._resolve_initial_state(session, query)
    state = resolve_route(
        intent=intent,
        canonical_sport=current.sport_id,
        canonical_market=current.market_id,
        last_market_by_sport=current.last_market_by_sport,
        epoch=current.epoch,
    )
    if state.sport_id != current.sport_id:
        _clear_cross_route_query_context(query)
    prior._persist_state(state, session)
    prior.apply_legacy_route_state(state, session)
    apply_query_patch(query, query_patch_for_state(state, query))


def render_app() -> Any:
    pending = _consume_pending_intent(st.session_state)
    if pending is not None:
        _prepare_pending_handoff(pending, st.session_state, st.query_params)

    original_renderer = prior.nav_ui.render_universal_nav
    prior.nav_ui.render_universal_nav = nav_ui.render_universal_nav
    try:
        return prior.render_app()
    finally:
        prior.nav_ui.render_universal_nav = original_renderer


__all__ = [
    "FROZEN_PARENT",
    "MODEL_VERSION",
    "PENDING_INTENT_KEY",
    "UNIVERSAL_NAV_ENABLED",
    "record_bootstrap_import_ms",
    "render_app",
]
