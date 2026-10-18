"""Single-render-scope lifecycle and generation gate for Runtime V5."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable, TypeVar

from universal_runtime_v5_state import RuntimeRoute, RuntimeState, is_current_generation

T = TypeVar("T")
_VALID_STATUS = {"ACTIVE", "RETIRING", "DORMANT"}


@dataclass(frozen=True)
class RenderScope:
    scope_id: str
    generation: int
    sport_id: str
    market_id: str
    status: str


def new_scope(route: RuntimeRoute) -> RenderScope:
    return RenderScope(
        scope_id=f"v5:{int(route.generation)}:{route.sport_id}:{route.market_id}",
        generation=int(route.generation),
        sport_id=route.sport_id,
        market_id=route.market_id,
        status="ACTIVE",
    )


def retire_scope(scope: RenderScope) -> RenderScope:
    if scope.status not in _VALID_STATUS:
        raise RuntimeError("API2_V5_INVALID_SCOPE_STATUS")
    return RenderScope(
        scope.scope_id,
        scope.generation,
        scope.sport_id,
        scope.market_id,
        "DORMANT",
    )


def can_commit(scope: RenderScope, runtime: RuntimeState) -> bool:
    return (
        scope.status == "ACTIVE"
        and is_current_generation(runtime, scope.generation)
        and scope.sport_id == runtime.active.sport_id
        and scope.market_id == runtime.active.market_id
    )


def commit_if_current(
    scope: RenderScope,
    runtime: RuntimeState,
    commit: Callable[[], T],
) -> T | None:
    if not can_commit(scope, runtime):
        return None
    return commit()


def assert_single_active_scope(scopes: Iterable[RenderScope]) -> RenderScope:
    active = [scope for scope in scopes if scope.status == "ACTIVE"]
    if len(active) > 1:
        raise RuntimeError("API2_V5_DUPLICATE_ACTIVE_SCOPE")
    if not active:
        raise RuntimeError("API2_V5_NO_ACTIVE_SCOPE")
    return active[0]


__all__ = [
    "RenderScope",
    "assert_single_active_scope",
    "can_commit",
    "commit_if_current",
    "new_scope",
    "retire_scope",
]
