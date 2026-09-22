"""CFB Over/Under performance profiler V1.

Measurement-only utilities for the College Football Over/Under page. This module
records server-side elapsed time for named stages and does not alter schedule
identity, sportsbook semantics, projection inputs, projection formulas, ranking,
or selection behavior.
"""
from __future__ import annotations

from collections import defaultdict
from contextvars import ContextVar
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Callable

MODEL_VERSION = "CFB O/U PERFORMANCE PROFILER V1 • MEASUREMENT ONLY"
PROJECTION_WEIGHT = 0.0
MAY_MODIFY_PROJECTION = False


@dataclass
class PerfTrace:
    """One Streamlit render's server-side timing events."""

    events: list[tuple[str, float]] = field(default_factory=list)

    def add(self, label: str, seconds: float) -> None:
        value = max(0.0, float(seconds))
        self.events.append((str(label), value))

    def call(self, label: str, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        started = perf_counter()
        try:
            return fn(*args, **kwargs)
        finally:
            self.add(label, perf_counter() - started)

    def aggregate(self) -> list[dict[str, Any]]:
        grouped: dict[str, list[float]] = defaultdict(list)
        for label, seconds in self.events:
            if label == "page.total_server_render":
                continue
            grouped[label].append(seconds)
        rows = [
            {
                "stage": label,
                "calls": len(values),
                "total_ms": round(sum(values) * 1000.0, 1),
                "max_ms": round(max(values) * 1000.0, 1),
            }
            for label, values in grouped.items()
        ]
        rows.sort(key=lambda row: (-float(row["total_ms"]), str(row["stage"])))
        return rows

    def total_ms(self) -> float:
        totals = [
            seconds
            for label, seconds in self.events
            if label == "page.total_server_render"
        ]
        return round((totals[-1] if totals else 0.0) * 1000.0, 1)

    def compact_caption(self, limit: int = 4) -> str:
        rows = self.aggregate()[: max(1, int(limit))]
        slow = " • ".join(
            f"{row['stage']} {row['total_ms']:.1f} ms"
            for row in rows
        ) or "no stage samples"
        return (
            "⚡ CFB O/U PERF V1 • measurement only • "
            f"server render {self.total_ms():.1f} ms • slowest: {slow} • "
            "projection math unchanged"
        )


_ACTIVE_TRACE: ContextVar[PerfTrace | None] = ContextVar(
    "cfb_ou_performance_trace",
    default=None,
)


def set_active_trace(trace: PerfTrace | None):
    return _ACTIVE_TRACE.set(trace)


def reset_active_trace(token: Any) -> None:
    _ACTIVE_TRACE.reset(token)


def current_trace() -> PerfTrace | None:
    return _ACTIVE_TRACE.get()


def timed_call(label: str, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    trace = current_trace()
    if trace is None:
        return fn(*args, **kwargs)
    return trace.call(label, fn, *args, **kwargs)


__all__ = [
    "MAY_MODIFY_PROJECTION",
    "MODEL_VERSION",
    "PROJECTION_WEIGHT",
    "PerfTrace",
    "current_trace",
    "reset_active_trace",
    "set_active_trace",
    "timed_call",
]
