"""Monster Performance Profiler V1.

Dependency-light performance diagnosis shared by Streamlit and FastAPI.
This module is measurement-only: it never changes sports data, schedules,
markets, projections, rankings, or selection logic.
"""
from __future__ import annotations

import os
import re
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Iterator

PERFORMANCE_PROFILER_VERSION = "MONSTER_PERFORMANCE_PROFILER_V1"
PROJECTION_WEIGHT = 0.0
MAY_MODIFY_PROJECTION = False

_LABEL_RE = re.compile(r"[^A-Za-z0-9._:-]+")


def _env_float(name: str, default: float) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default
    return max(0.0, value)


def slow_request_threshold_ms() -> float:
    return _env_float("KYRE_PERF_SLOW_REQUEST_MS", 1500.0)


def critical_request_threshold_ms() -> float:
    return _env_float("KYRE_PERF_CRITICAL_REQUEST_MS", 3000.0)


def slow_span_threshold_ms() -> float:
    return _env_float("KYRE_PERF_SLOW_SPAN_MS", 250.0)


def _clean_label(value: Any, *, fallback: str = "unknown") -> str:
    text = str(value or "").strip()[:160]
    return text or fallback


def header_token(value: Any, *, limit: int = 96) -> str:
    """Return a response-header-safe diagnostic token."""
    cleaned = _LABEL_RE.sub("_", _clean_label(value)).strip("_")
    return (cleaned or "unknown")[:limit]


def classify_stage(label: str) -> str:
    """Map a timing label to a stable bottleneck family."""
    lowered = _clean_label(label).lower()
    if lowered.startswith(("import.", "bootstrap.", "cold_start.")) or "import" in lowered:
        return "import"
    if lowered.startswith(("cache.", "snapshot.")) or "cache" in lowered:
        return "cache"
    if lowered.startswith(("market.", "odds.", "sportsbook.")) or any(
        token in lowered for token in ("market", "odds", "sportsbook")
    ):
        return "market"
    if lowered.startswith(("api.", "http.", "network.")) or any(
        token in lowered for token in ("request", "endpoint", "http")
    ):
        return "api"
    if lowered.startswith(("analysis.", "model.", "projection.", "simulation.")) or any(
        token in lowered for token in ("analysis", "projection", "simulation", "prewarm")
    ):
        return "analysis"
    if lowered.startswith(("render.", "page.", "ui.")) or any(
        token in lowered for token in ("render", "widget", "streamlit")
    ):
        return "render"
    return "code"


@dataclass
class SpanSample:
    name: str
    duration_ms: float
    category: str = ""
    calls: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "stage": self.name,
            "category": self.category or classify_stage(self.name),
            "calls": max(1, int(self.calls)),
            "total_ms": round(max(0.0, float(self.duration_ms)), 2),
        }


@dataclass
class PerformanceTrace:
    surface: str
    path: str = "unknown"
    started: float = field(default_factory=perf_counter)
    spans: list[SpanSample] = field(default_factory=list)

    def add(
        self,
        name: str,
        duration_ms: float,
        *,
        category: str | None = None,
        calls: int = 1,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.spans.append(
            SpanSample(
                name=_clean_label(name),
                duration_ms=max(0.0, float(duration_ms)),
                category=_clean_label(category, fallback="") if category else "",
                calls=max(1, int(calls)),
                metadata=dict(metadata or {}),
            )
        )

    def elapsed_ms(self) -> float:
        return max(0.0, (perf_counter() - self.started) * 1000.0)


_ACTIVE_TRACE: ContextVar[PerformanceTrace | None] = ContextVar(
    "monster_performance_trace_v1",
    default=None,
)


def start_trace(surface: str, *, path: str = "unknown"):
    trace = PerformanceTrace(surface=_clean_label(surface), path=_clean_label(path))
    return trace, _ACTIVE_TRACE.set(trace)


def current_trace() -> PerformanceTrace | None:
    return _ACTIVE_TRACE.get()


def reset_trace(token: Any) -> None:
    _ACTIVE_TRACE.reset(token)


@contextmanager
def span(name: str, *, category: str | None = None) -> Iterator[None]:
    """Measure a named block when a Monster trace is active."""
    trace = current_trace()
    started = perf_counter()
    try:
        yield
    finally:
        if trace is not None:
            trace.add(name, (perf_counter() - started) * 1000.0, category=category)


def add_stage_rows(trace: PerformanceTrace, rows: Any) -> None:
    """Import stage rows from an existing measurement-only profiler."""
    if not isinstance(rows, (list, tuple)):
        return
    for row in rows:
        if not isinstance(row, dict):
            continue
        try:
            duration_ms = float(row.get("total_ms", 0.0) or 0.0)
            calls = int(row.get("calls", 1) or 1)
        except (TypeError, ValueError):
            continue
        trace.add(
            str(row.get("stage") or row.get("name") or "unknown"),
            duration_ms,
            category=str(row.get("category") or "") or None,
            calls=calls,
        )


def speed_grade(total_ms: float) -> str:
    value = max(0.0, float(total_ms))
    if value >= critical_request_threshold_ms():
        return "CRITICAL"
    if value >= slow_request_threshold_ms():
        return "SLOW"
    if value >= 750.0:
        return "WATCH"
    return "FAST"


def _guidance(category: str, bottleneck: str) -> str:
    hints = {
        "import": "Inspect eager imports and cold-start routing; lazy-load modules not needed for this route.",
        "cache": "Inspect cache misses, cache keys, TTLs, and whether stable data can be reused safely.",
        "market": "Inspect sportsbook/market fetch latency, retries, snapshot reuse, and upstream freshness checks.",
        "api": "Inspect this route's upstream requests and database/network calls before changing model logic.",
        "analysis": "Inspect the named analysis/prewarm stage for repeated work, serialization, or parallelization opportunities.",
        "render": "Inspect Streamlit/UI rendering and repeated widget/dataframe work after data is already available.",
        "code": "Instrument one level deeper inside this stage; the current trace identifies the hotspot but not its inner call.",
    }
    return hints.get(category, hints["code"]) + f" Hotspot: {bottleneck}."


def diagnose(
    *,
    total_ms: float,
    spans: list[SpanSample] | None = None,
    surface: str = "unknown",
    path: str = "unknown",
) -> dict[str, Any]:
    """Turn timing samples into a compact root-cause-oriented diagnosis."""
    total = max(0.0, float(total_ms))
    normalized = [sample.as_dict() for sample in (spans or [])]
    normalized.sort(key=lambda row: (-float(row["total_ms"]), str(row["stage"])))

    candidates = [
        row
        for row in normalized
        if row["stage"] not in {"page.total_server_render", "api.request.total", "app.total"}
    ]
    if not candidates:
        candidates = normalized

    top = candidates[0] if candidates else {
        "stage": "unattributed",
        "category": "code",
        "calls": 1,
        "total_ms": total,
    }
    bottleneck_ms = max(0.0, float(top["total_ms"]))
    share = 0.0 if total <= 0.0 else min(100.0, (bottleneck_ms / total) * 100.0)
    slow_spans = [row for row in normalized if float(row["total_ms"]) >= slow_span_threshold_ms()]
    grade = speed_grade(total)

    return {
        "version": PERFORMANCE_PROFILER_VERSION,
        "surface": _clean_label(surface),
        "path": _clean_label(path),
        "grade": grade,
        "total_ms": round(total, 2),
        "bottleneck": str(top["stage"]),
        "bottleneck_category": str(top["category"]),
        "bottleneck_ms": round(bottleneck_ms, 2),
        "bottleneck_share_pct": round(share, 1),
        "slow_span_count": len(slow_spans),
        "top_spans": normalized[:8],
        "guidance": _guidance(str(top["category"]), str(top["stage"])),
        "projection_weight": PROJECTION_WEIGHT,
        "may_modify_projection": MAY_MODIFY_PROJECTION,
    }


def diagnose_trace(trace: PerformanceTrace, *, total_ms: float | None = None) -> dict[str, Any]:
    return diagnose(
        total_ms=trace.elapsed_ms() if total_ms is None else total_ms,
        spans=trace.spans,
        surface=trace.surface,
        path=trace.path,
    )


def compact_summary(diagnosis: dict[str, Any]) -> str:
    return (
        "⚡ MONSTER PERF V1 • "
        f"{diagnosis.get('grade', 'UNKNOWN')} • "
        f"total {float(diagnosis.get('total_ms', 0.0)):.1f} ms • "
        f"bottleneck {diagnosis.get('bottleneck', 'unknown')} "
        f"({float(diagnosis.get('bottleneck_ms', 0.0)):.1f} ms, "
        f"{float(diagnosis.get('bottleneck_share_pct', 0.0)):.1f}%)"
    )


__all__ = [
    "MAY_MODIFY_PROJECTION",
    "PERFORMANCE_PROFILER_VERSION",
    "PROJECTION_WEIGHT",
    "PerformanceTrace",
    "SpanSample",
    "add_stage_rows",
    "classify_stage",
    "compact_summary",
    "critical_request_threshold_ms",
    "current_trace",
    "diagnose",
    "diagnose_trace",
    "header_token",
    "reset_trace",
    "slow_request_threshold_ms",
    "slow_span_threshold_ms",
    "span",
    "speed_grade",
    "start_trace",
]
