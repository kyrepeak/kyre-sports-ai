"""API 2 production-entrypoint cold-start guard.

Seeds the existing canonical Universal Navigation state before the preserved
entrypoint invokes Universal Navigation V3. This module does not own routing;
it only prevents an empty Streamlit session from reaching V3 without a valid
canonical sport/market pair.
"""
from __future__ import annotations

from typing import Any, Mapping, MutableMapping

import streamlit_memory_lazy_router_universal_nav_v1 as canonical_v1
from universal_sports_nav_compat_v1 import apply_legacy_route_state
from universal_sports_nav_registry_v1 import get_market, get_sport

MODEL_VERSION = "API2 ENTRYPOINT COLD START V1"


def _canonical_route_is_valid(session: Mapping[str, Any]) -> bool:
    sport_id = str(session.get("ks_universal_sport") or "").strip().lower()
    market_id = str(session.get("ks_universal_market") or "").strip().lower()
    sport = get_sport(sport_id)
    return sport is not None and get_market(sport_id, market_id) is not None


def seed_canonical_route_if_missing(
    session: MutableMapping[str, Any],
    query: Mapping[str, Any],
) -> dict[str, str]:
    """Seed canonical + legacy route state only when canonical state is absent/invalid."""
    if _canonical_route_is_valid(session):
        return {
            "sport_id": str(session["ks_universal_sport"]).strip().lower(),
            "market_id": str(session["ks_universal_market"]).strip().lower(),
        }

    state = canonical_v1._resolve_initial_state(session, query)
    canonical_v1._persist_state(state, session)
    apply_legacy_route_state(state, session)
    return {"sport_id": state.sport_id, "market_id": state.market_id}


__all__ = [
    "MODEL_VERSION",
    "_canonical_route_is_valid",
    "seed_canonical_route_if_missing",
]
