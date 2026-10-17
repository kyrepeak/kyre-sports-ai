"""Legacy-session compatibility adapter for Universal Sports Navigation V1."""
from __future__ import annotations

from typing import Any, Callable, MutableMapping

from universal_sports_nav_controller_v1 import RouteState
from universal_sports_nav_registry_v1 import get_market, get_sport


LEGACY_TOP_LEVEL_LABELS = frozenset({
    "🏟️ Sport",
    "🎯 NFL Market",
    "🎯 CFB Market",
    "🎯 NBA Market",
    "🎯 MLB Market",
    "🎯 WNBA Market",
})

_MARKET_LABEL_TO_SPORT = {
    "🎯 NFL Market": "nfl",
    "🎯 CFB Market": "cfb",
    "🎯 NBA Market": "nba",
    "🎯 MLB Market": "mlb",
    "🎯 WNBA Market": "wnba",
}


def _set_if_changed(session: MutableMapping[str, Any], key: str, value: Any, changed: list[str]) -> None:
    if session.get(key) != value:
        session[key] = value
        changed.append(key)


def apply_legacy_route_state(
    state: RouteState,
    session_state: MutableMapping[str, Any],
) -> tuple[str, ...]:
    """Translate one validated canonical route into legacy router inputs."""
    sport = get_sport(state.sport_id)
    market = get_market(state.sport_id, state.market_id)
    if sport is None or market is None:
        raise ValueError("canonical route is not registered live")

    changed: list[str] = []
    _set_if_changed(session_state, "ks_sport_touch", sport.legacy_sport, changed)
    _set_if_changed(session_state, market.legacy_market_key, market.legacy_market, changed)
    for key, value in market.legacy_flags:
        _set_if_changed(session_state, key, value, changed)
    return tuple(changed)


def make_legacy_selectbox_bridge(
    delegate: Callable[..., Any],
    state: RouteState,
) -> Callable[..., Any]:
    """Suppress only legacy global nav selectboxes; delegate page controls exactly."""
    sport = get_sport(state.sport_id)
    market = get_market(state.sport_id, state.market_id)
    if sport is None or market is None:
        raise ValueError("canonical route is not registered live")

    def _bridge(label: str, options, *args, **kwargs):
        text = str(label or "")
        if text not in LEGACY_TOP_LEVEL_LABELS:
            return delegate(label, options, *args, **kwargs)
        if text == "🏟️ Sport":
            return sport.legacy_sport
        target_sport = _MARKET_LABEL_TO_SPORT.get(text)
        if target_sport == state.sport_id:
            return market.legacy_market
        # CFB and NBA still traverse the legacy root's NFL fallback dispatch
        # seam. Feed that seam the canonical market instead of the first NFL
        # option so downstream sport-specific renderer bridges receive the
        # destination route rather than a stale/default NFL market.
        if text == "🎯 NFL Market" and state.sport_id in {"cfb", "nba"}:
            return market.legacy_market
        values = list(options or ())
        return values[0] if values else None

    return _bridge


def make_legacy_markdown_bridge(delegate: Callable[..., Any]) -> Callable[..., Any]:
    """Hide only the obsolete root KYRE SPORTS AI hero during safe cutover."""
    def _bridge(body: Any, *args, **kwargs):
        text = str(body or "")
        has_shell = 'class="ks-shell"' in text or "class='ks-shell'" in text
        if has_shell and "KYRE SPORTS AI" in text:
            return None
        return delegate(body, *args, **kwargs)

    return _bridge


__all__ = [
    "LEGACY_TOP_LEVEL_LABELS",
    "apply_legacy_route_state",
    "make_legacy_markdown_bridge",
    "make_legacy_selectbox_bridge",
]
