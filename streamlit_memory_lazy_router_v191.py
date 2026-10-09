"""KYRE Streamlit Router V191 — remaining-pages universal compatibility.

Additive over frozen V190. Already-certified presentations remain untouched:
NFL Passing Yards, NFL Moneyline, and CFB Game Total. Every other active route
renders inside one scoped Streamlit container with the universal compatibility
skin. Route/data/model owners remain V190 and its frozen delegates.

CFB Game Total Step-4 public convergence is installed additively before V190
renders. The repair wraps only V160's exact Game Total surface and changes no
frozen source file, model, projection, probability, market, or other sport.

Step-5 live certification additionally guards the two CFB compatibility
installers once per Python process. Streamlit reruns therefore reuse the same
wrapper chain instead of nesting another Step-3/Step-4 presentation wrapper.
"""
from __future__ import annotations

from threading import RLock

import streamlit as st

import streamlit_memory_lazy_router_v190 as prior
from cfb_game_total_page1_v2_step4_public_repair_v1 import install_public_repair
from kyre_remaining_pages_theme_v1 import (
    REMAINING_PAGES_CONTAINER_KEY,
    build_remaining_pages_theme_css,
    should_theme_route,
)

MODEL_VERSION = "KYRE STREAMLIT ROUTER V191 • REMAINING PAGES UNIVERSAL THEME • STEP5 IDEMPOTENCE"
FROZEN_ROUTER = "streamlit_memory_lazy_router_v190"
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
MAY_MODIFY_PROJECTION = False
PRESENTATION_ONLY = True

_INSTALL_LOCK = RLock()
_PUBLIC_REPAIR_INSTALLED = False
_CFB_GAME_TOTAL_COMPAT_INSTALLED = False


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def _active_route() -> tuple[str, str]:
    sport = str(st.session_state.get("ks_sport_touch") or "").strip().upper()
    if sport == "COLLEGE FOOTBALL":
        sport = "CFB"
    if sport == "NFL":
        market = str(st.session_state.get("ks_nfl_market_touch") or "").strip()
    elif sport == "CFB":
        market = str(st.session_state.get("ks_cfb_market_touch") or "").strip()
    elif sport == "MLB":
        market = str(st.session_state.get("ks_mlb_market_touch") or "").strip()
    elif sport == "WNBA":
        market = str(st.session_state.get("ks_wnba_market_touch") or "").strip()
    else:
        market = ""
    return sport, market


def _ensure_public_repair_once() -> bool:
    global _PUBLIC_REPAIR_INSTALLED
    with _INSTALL_LOCK:
        if _PUBLIC_REPAIR_INSTALLED:
            return True
        installed = bool(install_public_repair())
        if installed:
            _PUBLIC_REPAIR_INSTALLED = True
        return installed


def _should_theme_route_once(sport: str, market: str) -> bool:
    """Preserve theme routing while installing CFB Game Total compatibility once."""
    global _CFB_GAME_TOTAL_COMPAT_INSTALLED
    normalized_sport = str(sport or "").strip().upper()
    normalized_market = str(market or "").strip()
    if (normalized_sport, normalized_market) != ("CFB", "Game Total"):
        return should_theme_route(sport, market)

    with _INSTALL_LOCK:
        if _CFB_GAME_TOTAL_COMPAT_INSTALLED:
            return False
        # The frozen theme gate owns the exact CFB compatibility installer and
        # intentionally returns False because CFB Game Total is excluded from
        # universal restyling. Call it once, then preserve that False result.
        should_theme_route("CFB", "Game Total")
        _CFB_GAME_TOTAL_COMPAT_INSTALLED = True
        return False


def render_app() -> None:
    _ensure_public_repair_once()
    sport, market = _active_route()
    if not _should_theme_route_once(sport, market):
        return prior.render_app()

    st.markdown(build_remaining_pages_theme_css(), unsafe_allow_html=True)
    themed = st.container(key=REMAINING_PAGES_CONTAINER_KEY)
    with themed:
        return prior.render_app()


__all__ = [
    "FROZEN_ROUTER",
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "PRESENTATION_ONLY",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_active_route",
    "_ensure_public_repair_once",
    "_should_theme_route_once",
    "record_bootstrap_import_ms",
    "render_app",
]
