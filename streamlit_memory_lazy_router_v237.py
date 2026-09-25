"""Streamlit lazy router V237 — Passing Yards visible leak cleanup.

Additive over frozen V236. Receptions and every non-Passing-Yards route still
delegate to V236 unchanged. Only NFL -> Passing Yards swaps V235's Passing Hub
from frozen V84 to presentation-only V85.
"""
from __future__ import annotations

import importlib
import streamlit as st

import streamlit_memory_lazy_router_v187 as identity_router
import streamlit_memory_lazy_router_v235 as passing_router
import streamlit_memory_lazy_router_v236 as prior

MODEL_VERSION = "KYRE STREAMLIT ROUTER V237 • PASSING YARDS V85 CLEANUP"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v236"
FROZEN_PASSING_ROUTER = "streamlit_memory_lazy_router_v235"
PASSING_MARKET = "Passing Yards"
PASSING_HUB = "nfl_passing_yards_hub_v85"
FALLBACK_HUB = "nfl_passing_yards_hub_v84"
PRESENTATION_ONLY = True
MAY_MODIFY_PROJECTION = False
MAY_MODIFY_CONTEXT_MATH = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_MARKET_MATH = False
MAY_MODIFY_WIDGET_KEYS = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
_IMPORT_CACHE: dict[str, bool] = {}
SPORT_KEY = "ks_sport_touch"
NFL_MARKET_KEY = "ks_nfl_market_touch"


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def _passing_requested() -> bool:
    # Read the live Streamlit widget state first. The historical delegated
    # _active_route() chain can miss the same-run NFL -> Passing Yards handoff
    # and fall all the way back to V187's legacy player-prop identity handler.
    sport_state = str(st.session_state.get(SPORT_KEY) or "").strip()
    market_state = str(st.session_state.get(NFL_MARKET_KEY) or "").strip()
    if sport_state == "NFL" and market_state == PASSING_MARKET:
        return True

    if passing_router._cold_passing_yards_query_requested():
        return True
    sport, market = passing_router._active_route()
    return sport == "NFL" and market == PASSING_MARKET


def _cleanup_hub_importable(importer=importlib.import_module) -> bool:
    if importer is importlib.import_module and PASSING_HUB in _IMPORT_CACHE:
        return _IMPORT_CACHE[PASSING_HUB]
    try:
        importer(PASSING_HUB)
        ok = True
    except Exception:
        ok = False
    if importer is importlib.import_module:
        _IMPORT_CACHE[PASSING_HUB] = ok
    return ok


def _install_passing_owners() -> None:
    """Install the certified Passing Yards owner without render-wide locking.

    Both assignments are idempotent and affect only the Passing Yards key.
    Keeping the owner stable avoids cross-session global mutation/restore races
    and, critically, avoids holding a process-wide lock for an entire Streamlit
    render. Non-Passing-Yards routes continue to delegate through V236.
    """
    passing_router.PASSING_HUB = PASSING_HUB
    identity_router.PROP_HUBS[PASSING_MARKET] = PASSING_HUB


def render_app() -> None:
    # Install the Passing Yards owner before route detection. This is an
    # idempotent string-map update only; it does not import V85 or affect any
    # non-Passing-Yards market. If hosted Streamlit delays widget/session-state
    # propagation, lower routers still cannot fall back to the legacy V42 owner.
    _install_passing_owners()

    if not _passing_requested():
        return prior.render_app()
    if not _cleanup_hub_importable():
        return prior.render_app()

    # Passing Yards is already fully owned by the V85 hub chain. Once that
    # route is positively identified, jump directly into V187's certified
    # root-shell dispatcher instead of re-entering V236 -> V235 -> ... -> V187.
    # The historical re-entry can stall hosted sessions before V85 emits its
    # first marker. Non-Passing-Yards routes still delegate through V236 above.
    return identity_router._render_direct_prop()


__all__ = [
    "FALLBACK_HUB",
    "FROZEN_PASSING_ROUTER",
    "FROZEN_ROUTER",
    "MAY_MODIFY_CONTEXT_MATH",
    "MAY_MODIFY_MARKET_MATH",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_PROJECTION",
    "MAY_MODIFY_WIDGET_KEYS",
    "MODEL_VERSION",
    "PASSING_HUB",
    "PASSING_MARKET",
    "PRESENTATION_ONLY",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "SPORT_KEY",
    "NFL_MARKET_KEY",
    "_cleanup_hub_importable",
    "_install_passing_owners",
    "_passing_requested",
    "record_bootstrap_import_ms",
    "render_app",
]
