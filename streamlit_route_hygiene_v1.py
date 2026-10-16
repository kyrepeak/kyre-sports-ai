"""Sitewide Streamlit route hygiene for stale deep-link query state.

Cold-start deep links remain authoritative when no in-session sport selection
exists. Once a user has an explicit current sport/market widget value, stale
route query params may not overwrite that newer selection on the next rerun.
"""
from __future__ import annotations

from typing import Any, Mapping, MutableMapping


SPORT_MARKET_KEYS = {
    "MLB": ("ks_mlb_market_touch", "ks_mlb_market"),
    "WNBA": ("ks_wnba_market_touch", "ks_wnba_market"),
    "NFL": ("ks_nfl_market_touch", "ks_nfl_market"),
    "College Football": ("ks_cfb_market_touch", "ks_cfb_market"),
    "NBA": ("ks_nba_market_touch", "ks_nba_market"),
}


def _scalar(value: Any) -> str:
    if isinstance(value, (list, tuple)):
        value = value[-1] if value else ""
    return str(value or "").strip()


def _route_query_keys(query_params: Mapping[str, Any]) -> tuple[str, ...]:
    keys = []
    for raw in query_params.keys():
        key = str(raw)
        if key == "ks_sport" or (key.startswith("ks_") and key.endswith("_market")):
            keys.append(key)
    return tuple(sorted(set(keys)))


def stale_route_query_keys(
    session_state: Mapping[str, Any],
    query_params: Mapping[str, Any],
) -> tuple[str, ...]:
    """Return stale route keys that would override a newer in-app selection."""
    session_sport = _scalar(session_state.get("ks_sport_touch"))
    if not session_sport:
        # Fresh session: preserve deep-link query authority.
        return ()

    query_sport = _scalar(query_params.get("ks_sport"))
    if not query_sport:
        return ()

    if query_sport != session_sport:
        return _route_query_keys(query_params)

    market_keys = SPORT_MARKET_KEYS.get(session_sport)
    if not market_keys:
        return ()

    session_key, query_key = market_keys
    session_market = _scalar(session_state.get(session_key))
    query_market = _scalar(query_params.get(query_key))
    if session_market and query_market and session_market != query_market:
        return tuple(sorted({"ks_sport", query_key}))
    return ()


def apply_route_hygiene(
    session_state: Mapping[str, Any],
    query_params: MutableMapping[str, Any],
) -> tuple[str, ...]:
    """Clear only stale route keys; return the keys successfully cleared."""
    stale = stale_route_query_keys(session_state, query_params)
    cleared: list[str] = []
    for key in stale:
        try:
            if key in query_params:
                del query_params[key]
                cleared.append(key)
        except Exception:
            # Query mutation can be unavailable in some embedded/test contexts.
            continue
    return tuple(cleared)


__all__ = ["SPORT_MARKET_KEYS", "apply_route_hygiene", "stale_route_query_keys"]
