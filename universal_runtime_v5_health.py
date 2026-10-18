"""Lightweight bounded health telemetry for Universal Runtime V5."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, MutableSequence, Sequence

MAX_RUNTIME_EVENTS = 256
ROUTE_COMMIT_BUDGET_MS = 150.0
SHELL_VISIBLE_BUDGET_MS = 500.0
CACHED_VISIBLE_BUDGET_MS = 750.0


@dataclass(frozen=True)
class RuntimeEvent:
    name: str
    generation: int
    monotonic_ms: float
    values: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class RuntimeHealth:
    active_owner_count: int
    active_scope_count: int
    stale_commit_attempts: int
    wrapper_depth: int
    route_commit_ms: float | None
    shell_visible_ms: float | None
    cached_visible_ms: float | None
    live_refresh_ms: float | None


def record_event(events: MutableSequence[RuntimeEvent], event: RuntimeEvent) -> None:
    events.append(event)
    overflow = len(events) - MAX_RUNTIME_EVENTS
    if overflow > 0:
        del events[:overflow]


def _latest_duration(events: Sequence[RuntimeEvent], name: str) -> float | None:
    for event in reversed(tuple(events)):
        if event.name != name:
            continue
        raw = event.values.get("duration_ms")
        try:
            return float(raw) if raw is not None else None
        except (TypeError, ValueError):
            return None
    return None


def summarize_health(
    events: Sequence[RuntimeEvent],
    *,
    active_owner_count: int,
    active_scope_count: int,
    wrapper_depth: int,
) -> RuntimeHealth:
    return RuntimeHealth(
        active_owner_count=int(active_owner_count),
        active_scope_count=int(active_scope_count),
        stale_commit_attempts=sum(1 for event in events if event.name == "stale_commit_attempt"),
        wrapper_depth=int(wrapper_depth),
        route_commit_ms=_latest_duration(events, "route_commit"),
        shell_visible_ms=_latest_duration(events, "shell_visible"),
        cached_visible_ms=_latest_duration(events, "cached_visible"),
        live_refresh_ms=_latest_duration(events, "live_refresh"),
    )


def assert_runtime_health(health: RuntimeHealth) -> None:
    if health.active_owner_count != 1:
        raise RuntimeError("API2_V5_DUPLICATE_ROUTE_OWNER")
    if health.active_scope_count != 1:
        raise RuntimeError("API2_V5_DUPLICATE_ACTIVE_SCOPE")
    if health.wrapper_depth != 1:
        raise RuntimeError("API2_V5_WRAPPER_DEPTH_REGRESSION")
    if health.route_commit_ms is not None and health.route_commit_ms > ROUTE_COMMIT_BUDGET_MS:
        raise RuntimeError("API2_V5_ROUTE_COMMIT_BUDGET_EXCEEDED")
    if health.shell_visible_ms is not None and health.shell_visible_ms > SHELL_VISIBLE_BUDGET_MS:
        raise RuntimeError("API2_V5_SHELL_BUDGET_EXCEEDED")
    if health.cached_visible_ms is not None and health.cached_visible_ms > CACHED_VISIBLE_BUDGET_MS:
        raise RuntimeError("API2_V5_CACHE_BUDGET_EXCEEDED")


def latency_trend_ms(samples: Sequence[float]) -> float:
    values = [float(value) for value in samples]
    n = len(values)
    if n < 2:
        return 0.0
    mean_x = (n - 1) / 2.0
    mean_y = sum(values) / n
    numerator = sum((index - mean_x) * (value - mean_y) for index, value in enumerate(values))
    denominator = sum((index - mean_x) ** 2 for index in range(n))
    return numerator / denominator if denominator else 0.0


__all__ = [
    "CACHED_VISIBLE_BUDGET_MS",
    "MAX_RUNTIME_EVENTS",
    "ROUTE_COMMIT_BUDGET_MS",
    "RuntimeEvent",
    "RuntimeHealth",
    "SHELL_VISIBLE_BUDGET_MS",
    "assert_runtime_health",
    "latency_trend_ms",
    "record_event",
    "summarize_health",
]
