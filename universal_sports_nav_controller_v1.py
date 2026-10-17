"""Pure route authority for Universal Sports Navigation V1."""
from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from universal_sports_nav_registry_v1 import DEFAULT_SPORT_ID, get_market, get_sport


@dataclass(frozen=True)
class RouteState:
    sport_id: str
    market_id: str
    source: str
    epoch: int
    last_market_by_sport: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class RouteIntent:
    sport_id: str | None = None
    market_id: str | None = None
    source: str = "none"


_VALID_SOURCES = {"tap", "canonical_url", "memory", "default", "legacy"}


def _memory(values: Mapping[str, str] | None) -> dict[str, str]:
    return {str(k): str(v) for k, v in dict(values or {}).items()}


def _state(sport_id: str, market_id: str, source: str, epoch: int, memory: Mapping[str, str]) -> RouteState:
    mem = _memory(memory)
    mem[sport_id] = market_id
    return RouteState(sport_id, market_id, source, int(epoch), MappingProxyType(mem))


def _market_for_sport(sport_id: str, requested: str | None, memory: Mapping[str, str]) -> tuple[str, str]:
    sport = get_sport(sport_id)
    if sport is None:
        sport = get_sport(DEFAULT_SPORT_ID)
        sport_id = sport.id
    requested_id = str(requested or "").strip().lower()
    if requested_id and get_market(sport_id, requested_id) is not None:
        return requested_id, "requested"
    remembered = str(memory.get(sport_id) or "").strip().lower()
    if remembered and get_market(sport_id, remembered) is not None:
        return remembered, "memory"
    return sport.default_market_id, "default"


def remembered_market(state: RouteState, sport_id: str) -> str | None:
    sport_id = str(sport_id or "").strip().lower()
    market_id = str(state.last_market_by_sport.get(sport_id) or "").strip().lower()
    return market_id if get_market(sport_id, market_id) is not None else None


def resolve_route(
    *,
    intent: RouteIntent | None = None,
    canonical_sport: str | None = None,
    canonical_market: str | None = None,
    legacy_sport: str | None = None,
    legacy_market: str | None = None,
    last_market_by_sport: Mapping[str, str] | None = None,
    epoch: int = 0,
) -> RouteState:
    """Resolve one canonical route with explicit deterministic precedence."""
    memory = _memory(last_market_by_sport)
    intent = intent or RouteIntent()

    if intent.source == "tap" and (intent.sport_id or intent.market_id):
        base_sport = str(intent.sport_id or canonical_sport or DEFAULT_SPORT_ID).strip().lower()
        if get_sport(base_sport) is None:
            base_sport = DEFAULT_SPORT_ID
        market_id, _ = _market_for_sport(base_sport, intent.market_id, memory)
        return _state(base_sport, market_id, "tap", int(epoch) + 1, memory)

    canonical_id = str(canonical_sport or "").strip().lower()
    if get_sport(canonical_id) is not None:
        market_id, chosen = _market_for_sport(canonical_id, canonical_market, memory)
        source = "canonical_url" if chosen == "requested" else chosen
        return _state(canonical_id, market_id, source, int(epoch), memory)

    default_sport = get_sport(DEFAULT_SPORT_ID)
    remembered = str(memory.get(DEFAULT_SPORT_ID) or "").strip().lower()
    if remembered and get_market(DEFAULT_SPORT_ID, remembered) is not None:
        return _state(DEFAULT_SPORT_ID, remembered, "memory", int(epoch), memory)

    # Legacy is deliberately lower authority than the registry default. It is
    # primarily normalized by the URL codec before reaching this function.
    if default_sport is None:
        legacy_id = str(legacy_sport or "").strip().lower()
        if get_sport(legacy_id) is not None and get_market(legacy_id, str(legacy_market or "").lower()) is not None:
            return _state(legacy_id, str(legacy_market).lower(), "legacy", int(epoch), memory)
        raise RuntimeError("universal sports registry has no default sport")

    return _state(DEFAULT_SPORT_ID, default_sport.default_market_id, "default", int(epoch), memory)


def apply_sport_intent(state: RouteState, sport_id: str) -> RouteState:
    sport_id = str(sport_id or "").strip().lower()
    if get_sport(sport_id) is None:
        sport_id = DEFAULT_SPORT_ID
    market_id, _ = _market_for_sport(sport_id, None, state.last_market_by_sport)
    changed = (sport_id, market_id) != (state.sport_id, state.market_id)
    return _state(sport_id, market_id, "tap", state.epoch + (1 if changed else 0), state.last_market_by_sport)


def apply_market_intent(state: RouteState, market_id: str) -> RouteState:
    market_id = str(market_id or "").strip().lower()
    if get_market(state.sport_id, market_id) is None:
        market_id, _ = _market_for_sport(state.sport_id, None, state.last_market_by_sport)
    changed = market_id != state.market_id
    return _state(state.sport_id, market_id, "tap", state.epoch + (1 if changed else 0), state.last_market_by_sport)


__all__ = [
    "RouteIntent", "RouteState", "apply_market_intent", "apply_sport_intent",
    "remembered_market", "resolve_route",
]
