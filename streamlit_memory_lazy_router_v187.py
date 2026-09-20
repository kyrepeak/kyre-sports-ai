"""KYRE Streamlit Router V187 — NFL Step 7 app identity fail-closed route.

Additive over frozen V186. It advances only player-prop render owners:
- Passing Yards -> V42
- Rushing Yards -> V16
- Receiving Yards -> V17
- Receptions -> explicit fail-closed reserved surface (no player renderer)

All other markets delegate to V186 unchanged.
"""
from __future__ import annotations

import streamlit as st

import streamlit_memory_lazy_router_v1 as root
import streamlit_memory_lazy_router_v185 as handoff
import streamlit_memory_lazy_router_v186 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V187 • NFL STEP 7 APP IDENTITY FAIL-CLOSED"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v186"
NFL_SPORT_LABEL = "NFL"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False

PROP_HUBS = {
    "Passing Yards": "nfl_passing_yards_hub_v42",
    "Rushing Yards": "nfl_rushing_yards_hub_v16",
    "Receiving Yards": "nfl_receiving_yards_hub_v17",
}
RECEPTIONS_MARKET = "Receptions"


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def _active_market() -> str:
    if str(st.session_state.get(handoff.SPORT_KEY) or "") != NFL_SPORT_LABEL:
        return ""
    return str(st.session_state.get(handoff.NFL_MARKET_KEY) or "").strip()


def _render_nfl_v187(market: str) -> None:
    normalized = str(market or "Slate").strip()
    if normalized == RECEPTIONS_MARKET:
        st.warning(
            "Receptions is fail-closed at the Step 7 app identity gate. "
            "No player identity is rendered until an independent exact-ID Receptions "
            "surface is certified against the shared current receiver pool."
        )
        return
    module_name = PROP_HUBS.get(normalized)
    if not module_name:
        raise RuntimeError("Router V187 direct handler is player-prop identity only.")
    module = root._import(module_name)
    return module.render_nfl_hub(normalized)


def _render_direct_prop() -> None:
    original_render_nfl = root._render_nfl
    original_prefixes = root._ROUTE_MODULE_PREFIXES
    root._render_nfl = _render_nfl_v187
    if "nfl_" not in root._ROUTE_MODULE_PREFIXES:
        root._ROUTE_MODULE_PREFIXES = root._ROUTE_MODULE_PREFIXES + ("nfl_",)
    try:
        return root.render_app()
    finally:
        root._render_nfl = original_render_nfl
        root._ROUTE_MODULE_PREFIXES = original_prefixes


def render_app() -> None:
    # Preserve V185's certified same-run NFL dropdown handoff before routing.
    handoff._consume_any_nfl_category_without_rerun()
    market = _active_market()
    if market in PROP_HUBS or market == RECEPTIONS_MARKET:
        return _render_direct_prop()
    return prior.render_app()


__all__ = [
    "FROZEN_ROUTER",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "NFL_SPORT_LABEL",
    "PROP_HUBS",
    "RECEPTIONS_MARKET",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_active_market",
    "_render_direct_prop",
    "_render_nfl_v187",
    "record_bootstrap_import_ms",
    "render_app",
]
