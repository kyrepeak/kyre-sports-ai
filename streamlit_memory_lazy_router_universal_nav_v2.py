"""Tap-first Universal Sports Navigation V2 activation overlay.

This additive layer fixes first-tap cross-sport switching without reopening the
frozen V1 router. A widget callback records the newest explicit tap before the
next rerun. V2 consumes that intent, clears stale route-local URL and outgoing
sport-local session context on a sport handoff, updates the canonical route,
then delegates through V1 with only its renderer temporarily upgraded to the
callback-driven V2 UI.
"""
from __future__ import annotations

from typing import Any, Mapping, MutableMapping

import streamlit as st

import streamlit_memory_lazy_router_universal_nav_v1 as prior
import streamlit_memory_lazy_router_v1 as legacy_root
import universal_sports_nav_ui_v2 as nav_ui
import universal_tap_only_selector_v2 as tap_selector
from universal_sports_nav_controller_v1 import RouteIntent, RouteState, resolve_route
from universal_sports_nav_registry_v1 import get_market, get_sport
from universal_sports_nav_url_v1 import apply_query_patch, query_patch_for_state


MODEL_VERSION = "API2 UNIVERSAL SPORTS NAVIGATION V2 • TAP-FIRST HANDOFF"
FROZEN_PARENT = "streamlit_memory_lazy_router_universal_nav_v1"
UNIVERSAL_NAV_ENABLED = True
PENDING_INTENT_KEY = nav_ui.PENDING_INTENT_KEY
RECEIVING_V17_MODULE = "nfl_receiving_yards_hub_v17"
RECEIVING_V18_MODULE = "nfl_receiving_yards_hub_v18"
RECEIVING_V19_MODULE = "nfl_receiving_yards_hub_v19"
RECEIVING_V20_MODULE = "nfl_receiving_yards_hub_v20"
RECEIVING_V21_MODULE = "nfl_receiving_yards_hub_v21"

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


def _clear_cross_route_session_context(session: MutableMapping[str, Any], outgoing_sport_id: str) -> None:
    """Retire outgoing sport-local widget/page state before the new sport renders."""
    sport = str(outgoing_sport_id or "").strip().lower()
    if not sport:
        return
    prefixes = (f"{sport}_", f"ks_{sport}_")
    for raw_key in list(session.keys()):
        key = str(raw_key).strip().lower()
        if key.startswith("ks_universal_"):
            continue
        if key.startswith(prefixes):
            try:
                del session[raw_key]
            except Exception:
                continue


def _prepare_pending_handoff(
    intent: RouteIntent,
    session: MutableMapping[str, Any],
    query: MutableMapping[str, Any],
) -> RouteState:
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
        _clear_cross_route_session_context(session, current.sport_id)
    prior._persist_state(state, session)
    prior.apply_legacy_route_state(state, session)
    apply_query_patch(query, query_patch_for_state(state, query))
    return state


def _render_handoff_mask(state: RouteState) -> None:
    """Cover stale DOM while the committed destination starts on a clean rerun."""
    sport = get_sport(state.sport_id)
    market = get_market(state.sport_id, state.market_id)
    sport_label = sport.label if sport is not None else str(state.sport_id).upper()
    market_label = (
        market.label
        if market is not None
        else str(state.market_id).replace("-", " ").title()
    )
    st.markdown(
        f"""
<div class="ks-route-transition-v2">
  <div class="ks-route-transition-v2__card">
    <div class="ks-route-transition-v2__brand">KYRE SPORTS</div>
    <div class="ks-route-transition-v2__title">Loading {sport_label} · {market_label}</div>
    <div class="ks-route-transition-v2__sub">Switching pages...</div>
  </div>
</div>
<style>
.ks-route-transition-v2{{position:fixed;inset:0;z-index:2147483646;background:#080d16;display:flex;align-items:center;justify-content:center;padding:24px}}
.ks-route-transition-v2__card{{width:min(520px,92vw);border:1px solid rgba(56,189,248,.28);border-radius:22px;padding:26px;background:#0f1726;text-align:center}}
.ks-route-transition-v2__brand{{font-size:.72rem;font-weight:900;letter-spacing:.14em;color:#38bdf8}}
.ks-route-transition-v2__title{{margin-top:8px;font-size:1.25rem;font-weight:900;color:#f8fafc}}
.ks-route-transition-v2__sub{{margin-top:7px;font-size:.82rem;color:#94a3b8}}
</style>
""",
        unsafe_allow_html=True,
    )


def _render_app_impl() -> Any:
    pending = _consume_pending_intent(st.session_state)
    if pending is not None:
        state = _prepare_pending_handoff(pending, st.session_state, st.query_params)
        _render_handoff_mask(state)
        rerun = getattr(st, "rerun", None)
        if callable(rerun):
            rerun()
            return None

    original_renderer = prior.nav_ui.render_universal_nav
    original_import = legacy_root._import
    original_markdown = st.markdown
    receiving_route = (
        str(st.session_state.get("ks_universal_sport") or "").strip().lower() == "nfl"
        and str(st.session_state.get("ks_universal_market") or "").strip().lower() == "receiving-yards"
    )

    def receiving_import(module_name: str):
        if receiving_route and str(module_name) == RECEIVING_V17_MODULE:
            module_name = RECEIVING_V19_MODULE
        if receiving_route and str(module_name) == RECEIVING_V19_MODULE:
            module_name = RECEIVING_V20_MODULE
        if receiving_route and str(module_name) == RECEIVING_V20_MODULE:
            module_name = RECEIVING_V21_MODULE
        return original_import(module_name)

    def clean_router_debug(body: Any, *args: Any, **kwargs: Any):
        if receiving_route and isinstance(body, str) and "KYRE STREAMLIT MEMORY LAZY ROUTER V1" in body:
            return None
        return original_markdown(body, *args, **kwargs)

    prior.nav_ui.render_universal_nav = nav_ui.render_universal_nav
    legacy_root._import = receiving_import
    st.markdown = clean_router_debug
    try:
        return prior.render_app()
    finally:
        st.markdown = original_markdown
        legacy_root._import = original_import
        prior.nav_ui.render_universal_nav = original_renderer


def render_app() -> Any:
    with tap_selector.install_universal_tap_only_selectboxes():
        return _render_app_impl()


__all__ = [
    "FROZEN_PARENT",
    "MODEL_VERSION",
    "PENDING_INTENT_KEY",
    "UNIVERSAL_NAV_ENABLED",
    "record_bootstrap_import_ms",
    "render_app",
]
