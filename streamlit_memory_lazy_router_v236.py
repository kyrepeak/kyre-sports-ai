"""Streamlit lazy router V236 — NFL Receptions safe route restore.

Additive over frozen V235. The historical V187 router intentionally intercepts
NFL Receptions with a fail-closed warning and no page owner. That was correct
while identity work was uncertified, but it now prevents the user-facing
Receptions route from reaching even the existing safe NFL foundation surface.

V236 changes only NFL -> Receptions routing:
- consumes the already-certified V185 category handoff,
- temporarily disables V187's obsolete Receptions interception,
- delegates through the existing router chain so V191 theme ownership and
  root/nfl_hub_v18 rendering remain intact,
- keeps betting model/projection/probability/market math OFF for Receptions.

Every non-Receptions route delegates unchanged to frozen V235.
"""
from __future__ import annotations

import streamlit_memory_lazy_router_v187 as legacy_receptions
import streamlit_memory_lazy_router_v185 as handoff
import streamlit_memory_lazy_router_v235 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V236 • NFL RECEPTIONS SAFE ROUTE RESTORE"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v235"
NFL_SPORT_LABEL = "NFL"
RECEPTIONS_MARKET = "Receptions"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MARKET_MATH = False
PRESENTATION_ROUTING_ONLY = True
RUNTIME_MARKER = "NFL_RECEPTIONS_V236_SAFE_ROUTE_ACTIVE"


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def _query_value(key: str) -> str:
    return handoff._query_value(key)


def _cold_receptions_query_requested() -> bool:
    sport = _query_value(handoff.SPORT_JUMP_QUERY_KEY)
    market = _query_value(handoff.MARKET_JUMP_QUERY_KEY)
    return (
        str(sport or "").strip().upper() == NFL_SPORT_LABEL
        and str(market or "").strip() == RECEPTIONS_MARKET
    )


def _active_route() -> tuple[str, str]:
    return prior._active_route()


def _render_receptions_through_safe_foundation() -> None:
    """Bypass only V187's obsolete reserved warning, then restore it."""
    original = legacy_receptions.RECEPTIONS_MARKET
    legacy_receptions.RECEPTIONS_MARKET = "__V236_RECEPTIONS_BYPASS__"
    try:
        return prior.render_app()
    finally:
        legacy_receptions.RECEPTIONS_MARKET = original


def render_app() -> None:
    if _cold_receptions_query_requested():
        handoff._consume_any_nfl_category_without_rerun()

    sport, market = _active_route()
    if sport != NFL_SPORT_LABEL or market != RECEPTIONS_MARKET:
        return prior.render_app()

    return _render_receptions_through_safe_foundation()


__all__ = [
    "FROZEN_ROUTER",
    "MAY_MODIFY_MARKET_MATH",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "NFL_SPORT_LABEL",
    "PRESENTATION_ROUTING_ONLY",
    "RECEPTIONS_MARKET",
    "RUNTIME_MARKER",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_active_route",
    "_cold_receptions_query_requested",
    "_render_receptions_through_safe_foundation",
    "record_bootstrap_import_ms",
    "render_app",
]
