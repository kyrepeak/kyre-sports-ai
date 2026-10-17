"""Universal Sports Navigation V3 — canonical legacy-owner enforcement.

V2 owns tap-first hard handoffs. V3 adds a steady-state ownership guard so the
legacy renderer ancestry can never see a different sport than the canonical
Universal Navigation route selected by the user.
"""
from __future__ import annotations

from typing import Any, Mapping, MutableMapping

import streamlit as st

import streamlit_memory_lazy_router_universal_nav_v1 as canonical_v1
import streamlit_memory_lazy_router_universal_nav_v2 as prior
from universal_sports_nav_compat_v1 import apply_legacy_route_state
from universal_sports_nav_controller_v1 import RouteState
from universal_sports_nav_registry_v1 import SPORTS, get_market, get_sport

MODEL_VERSION = "API2 UNIVERSAL SPORTS NAVIGATION V3.1 • CANONICAL RENDER OWNER + COLD START"
FROZEN_PARENT = "streamlit_memory_lazy_router_universal_nav_v2"
PENDING_INTENT_KEY = prior.PENDING_INTENT_KEY
UNIVERSAL_NAV_ENABLED = True

_CANONICAL_KEYS = frozenset({
    "ks_universal_sport",
    "ks_universal_market",
    "ks_universal_nav_source",
    "ks_universal_epoch",
    "ks_universal_last_market_by_sport",
})


def record_bootstrap_import_ms(value: float) -> None:
    return prior.record_bootstrap_import_ms(value)


def _should_sync_steady_state(session: Mapping[str, Any]) -> bool:
    raw = session.get(PENDING_INTENT_KEY)
    if isinstance(raw, Mapping) and str(raw.get("source") or "").strip().lower() == "tap":
        return False
    return True


def _active_route(session: Mapping[str, Any]) -> tuple[str, str]:
    sport_id = str(session.get("ks_universal_sport") or "").strip().lower()
    market_id = str(session.get("ks_universal_market") or "").strip().lower()
    sport = get_sport(sport_id)
    market = get_market(sport_id, market_id) if sport is not None else None
    if sport is None or market is None:
        raise ValueError("canonical universal route is not registered live")
    return sport_id, market_id


def _seed_canonical_route_if_missing(
    session: MutableMapping[str, Any],
    query: Mapping[str, Any],
) -> tuple[str, str]:
    """Seed a valid cold-start/deep-link route before V3 enforces ownership."""
    try:
        return _active_route(session)
    except ValueError:
        state = canonical_v1._resolve_initial_state(session, query)
        canonical_v1._persist_state(state, session)
        apply_legacy_route_state(state, session)
        return state.sport_id, state.market_id


def _all_legacy_route_keys() -> dict[str, set[str]]:
    by_sport: dict[str, set[str]] = {}
    for sport in SPORTS:
        keys: set[str] = set()
        for market in sport.markets:
            keys.add(str(market.legacy_market_key))
            for key, _value in market.legacy_flags:
                keys.add(str(key))
        by_sport[sport.id] = keys
    return by_sport


def _enforce_canonical_legacy_owner(session: MutableMapping[str, Any]) -> dict[str, str]:
    sport_id, market_id = _active_route(session)
    sport = get_sport(sport_id)
    market = get_market(sport_id, market_id)
    assert sport is not None and market is not None

    # Remove route selectors/flags owned by every non-active sport so stale
    # legacy widget/session state cannot outvote canonical Universal Navigation.
    by_sport = _all_legacy_route_keys()
    for other_id, keys in by_sport.items():
        if other_id == sport_id:
            continue
        for key in keys:
            if key in _CANONICAL_KEYS:
                continue
            session.pop(key, None)

    # MLB's live-odds flag is a historical global side route and is not stored
    # in every registry market, so retire it explicitly off MLB.
    if sport_id != "mlb":
        session.pop("ks_mlb_live_odds_route", None)

    state = RouteState(
        sport_id=sport_id,
        market_id=market_id,
        source=str(session.get("ks_universal_nav_source") or "canonical"),
        epoch=int(session.get("ks_universal_epoch", 0) or 0),
        last_market_by_sport=dict(session.get("ks_universal_last_market_by_sport") or {}),
    )
    apply_legacy_route_state(state, session)
    return {"sport_id": sport_id, "market_id": market_id}


def render_app() -> Any:
    # Never sync the old canonical route over a fresh tap waiting for V2 to
    # consume it. V2 performs the hard handoff/rerun; V3 enforces ownership on
    # the following clean steady-state run.
    if _should_sync_steady_state(st.session_state):
        _seed_canonical_route_if_missing(st.session_state, st.query_params)
        _enforce_canonical_legacy_owner(st.session_state)
    return prior.render_app()


__all__ = [
    "FROZEN_PARENT",
    "MODEL_VERSION",
    "PENDING_INTENT_KEY",
    "UNIVERSAL_NAV_ENABLED",
    "_enforce_canonical_legacy_owner",
    "_seed_canonical_route_if_missing",
    "_should_sync_steady_state",
    "record_bootstrap_import_ms",
    "render_app",
]
