"""Pure canonical route-generation state for Universal Runtime V5."""
from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from universal_sports_nav_controller_v1 import RouteIntent, RouteState, resolve_route
from universal_sports_nav_registry_v1 import get_market

_PAGE_KEYS = ("date", "game_id", "player_id")


def _strings(values: Mapping[str, object] | None) -> dict[str, str]:
    result: dict[str, str] = {}
    for key, value in dict(values or {}).items():
        text = str(value or "").strip()
        if text:
            result[str(key)] = text
    return result


def _page_params(sport_id: str, market_id: str, values: Mapping[str, object] | None) -> dict[str, str]:
    market = get_market(sport_id, market_id)
    if market is None:
        return {}
    raw = _strings(values)
    return {key: raw[key] for key in market.page_params if key in raw}


@dataclass(frozen=True)
class RuntimeRoute:
    sport_id: str
    market_id: str
    params: Mapping[str, str] = field(default_factory=dict)
    generation: int = 0
    source: str = "default"


@dataclass(frozen=True)
class RuntimeState:
    active: RuntimeRoute
    last_route_by_sport: Mapping[str, RuntimeRoute] = field(default_factory=dict)
    generation: int = 0


def _freeze_route(route: RuntimeRoute) -> RuntimeRoute:
    return RuntimeRoute(
        sport_id=str(route.sport_id),
        market_id=str(route.market_id),
        params=MappingProxyType(dict(route.params)),
        generation=int(route.generation),
        source=str(route.source),
    )


def _freeze_state(active: RuntimeRoute, memory: Mapping[str, RuntimeRoute], generation: int) -> RuntimeState:
    frozen_active = _freeze_route(active)
    frozen_memory = {str(key): _freeze_route(value) for key, value in dict(memory).items()}
    frozen_memory[frozen_active.sport_id] = frozen_active
    return RuntimeState(frozen_active, MappingProxyType(frozen_memory), int(generation))


def bootstrap_runtime(route_state: RouteState, params: Mapping[str, str] | None = None) -> RuntimeState:
    generation = int(route_state.epoch)
    active = RuntimeRoute(
        sport_id=route_state.sport_id,
        market_id=route_state.market_id,
        params=_page_params(route_state.sport_id, route_state.market_id, params),
        generation=generation,
        source=route_state.source,
    )
    memory: dict[str, RuntimeRoute] = {}
    for sport_id, market_id in dict(route_state.last_market_by_sport).items():
        memory[str(sport_id)] = RuntimeRoute(str(sport_id), str(market_id), {}, generation, "memory")
    return _freeze_state(active, memory, generation)


def commit_intent(
    state: RuntimeState,
    intent: RouteIntent,
    params: Mapping[str, str] | None = None,
) -> RuntimeState:
    memory = dict(state.last_route_by_sport)
    memory[state.active.sport_id] = state.active
    last_market_by_sport = {sport_id: route.market_id for sport_id, route in memory.items()}
    if intent.source == "canonical_url" and (intent.sport_id or intent.market_id):
        resolved = resolve_route(
            canonical_sport=intent.sport_id or state.active.sport_id,
            canonical_market=intent.market_id or state.active.market_id,
            last_market_by_sport=last_market_by_sport,
            epoch=state.generation,
        )
    else:
        resolved = resolve_route(
            intent=intent,
            canonical_sport=state.active.sport_id,
            canonical_market=state.active.market_id,
            last_market_by_sport=last_market_by_sport,
            epoch=state.generation,
        )
    remembered = memory.get(resolved.sport_id)
    if params is None and remembered is not None and remembered.market_id == resolved.market_id:
        next_params = dict(remembered.params)
    elif params is None and resolved.sport_id == state.active.sport_id and resolved.market_id == state.active.market_id:
        next_params = dict(state.active.params)
    else:
        next_params = _page_params(resolved.sport_id, resolved.market_id, params)
    filtered_params = _page_params(resolved.sport_id, resolved.market_id, next_params)
    route_changed = (
        resolved.sport_id != state.active.sport_id
        or resolved.market_id != state.active.market_id
        or filtered_params != dict(state.active.params)
    )
    explicit_tap = intent.source == "tap" and bool(intent.sport_id or intent.market_id)
    generation = state.generation + (1 if explicit_tap or route_changed else 0)
    active = RuntimeRoute(
        resolved.sport_id,
        resolved.market_id,
        filtered_params,
        generation,
        intent.source if intent.source in {"tap", "canonical_url"} else resolved.source,
    )
    memory[active.sport_id] = active
    return _freeze_state(active, memory, generation)


def is_current_generation(state: RuntimeState, generation: int) -> bool:
    return int(generation) == int(state.generation) == int(state.active.generation)


def canonical_query_patch(
    previous: RuntimeRoute,
    current: RuntimeRoute,
    existing_query: Mapping[str, object],
) -> dict[str, str | None]:
    del previous
    patch: dict[str, str | None] = {"sport": current.sport_id, "market": current.market_id}
    market = get_market(current.sport_id, current.market_id)
    allowed = set(market.page_params if market is not None else ())
    for key in _PAGE_KEYS:
        value = str(current.params.get(key) or "").strip() if key in allowed else ""
        if value:
            patch[key] = value
        elif key in existing_query:
            patch[key] = None
    return patch


__all__ = [
    "RuntimeRoute",
    "RuntimeState",
    "bootstrap_runtime",
    "canonical_query_patch",
    "commit_intent",
    "is_current_generation",
]
