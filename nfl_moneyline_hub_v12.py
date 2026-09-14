"""NFL Moneyline V12 — performance-only fast execution over frozen V11.

V12 preserves the exact certified V11 -> V10 -> V9 -> V8 analytical/runtime
chain. It makes the already-hidden legacy V8 execution cheaper in two ways:

1. identical request-scope deterministic calls are memoized only for the life of
   the current Streamlit render; and
2. presentation-only Streamlit deltas emitted by the hidden legacy surface are
   sunk after V11 has created its hidden container. Historical wrapper hooks
   still execute, so Step injection and session-state ownership remain frozen.

No model formula, 5M Monte Carlo count, market freshness rule, identity rule,
edge/EV formula, grade, stake behavior, or visible V9 card output is changed.
"""
from __future__ import annotations

from contextlib import contextmanager
from time import perf_counter
from typing import Any, Callable, Iterator

import streamlit as st

import nfl_hub_v1 as foundation
import nfl_moneyline_hub_v43 as calibration_page
import nfl_moneyline_hub_v11 as v11

MODEL_VERSION = "NFL MONEYLINE V12 • PERFORMANCE FAST EXECUTION V1 • V11 FROZEN"
FROZEN_PRIOR = "nfl_moneyline_hub_v11"
FROZEN_ENGINE = "nfl_moneyline_hub_v8"
PERFORMANCE_ONLY = True
SPORTSBOOK_MODEL_INFLUENCE = 0.0
STAKE_SIZING_ENABLED = False
MONTE_CARLO_SIMULATIONS = 5_000_000


class _Sink:
    """Minimal DeltaGenerator-like sink for output that is already invisible."""

    def __init__(self, stats: dict[str, Any], name: str = "sink") -> None:
        self._stats = stats
        self._name = name

    def _hit(self, name: str | None = None) -> None:
        key = name or self._name
        suppressed = self._stats.setdefault("suppressed", {})
        suppressed[key] = int(suppressed.get(key) or 0) + 1

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def __getattr__(self, name: str):
        def _method(*args: Any, **kwargs: Any):
            self._hit(name)
            if name in {"container", "empty", "expander", "status"}:
                return self
            if name == "progress":
                return self
            return None
        return _method

    def container(self, *args: Any, **kwargs: Any):
        self._hit("container")
        return self

    def empty(self, *args: Any, **kwargs: Any):
        self._hit("empty")
        return self

    def update(self, *args: Any, **kwargs: Any):
        self._hit("update")
        return None


_SIMPLE_OUTPUTS = (
    "markdown",
    "caption",
    "dataframe",
    "table",
    "write",
    "text",
    "code",
    "json",
    "image",
    "metric",
    "info",
    "warning",
    "success",
    "error",
    "header",
    "subheader",
    "divider",
    "toast",
)
_CONTEXT_OUTPUTS = ("spinner", "expander", "container", "empty", "status", "progress")


def _simple_sink(stats: dict[str, Any], name: str) -> Callable[..., None]:
    def _wrapped(*args: Any, **kwargs: Any) -> None:
        suppressed = stats.setdefault("suppressed", {})
        suppressed[name] = int(suppressed.get(name) or 0) + 1
        return None
    return _wrapped


def _context_sink(stats: dict[str, Any], name: str) -> Callable[..., _Sink]:
    def _wrapped(*args: Any, **kwargs: Any) -> _Sink:
        suppressed = stats.setdefault("suppressed", {})
        suppressed[name] = int(suppressed.get(name) or 0) + 1
        return _Sink(stats, name)
    return _wrapped


def _columns_sink(stats: dict[str, Any], spec: Any = 1, *args: Any, **kwargs: Any):
    suppressed = stats.setdefault("suppressed", {})
    suppressed["columns"] = int(suppressed.get("columns") or 0) + 1
    if isinstance(spec, int):
        count = max(0, spec)
    else:
        try:
            count = len(spec)
        except Exception:
            count = 1
    return tuple(_Sink(stats, "column") for _ in range(count))


@contextmanager
def _sink_hidden_presentation(stats: dict[str, Any]) -> Iterator[None]:
    """Sink only presentation calls while preserving widgets/state/cache logic."""
    originals: dict[str, Any] = {}
    names = (*_SIMPLE_OUTPUTS, *_CONTEXT_OUTPUTS, "columns")
    try:
        for name in names:
            if not hasattr(st, name):
                continue
            originals[name] = getattr(st, name)
            if name == "columns":
                setattr(st, name, lambda spec=1, *a, **k: _columns_sink(stats, spec, *a, **k))
            elif name in _CONTEXT_OUTPUTS:
                setattr(st, name, _context_sink(stats, name))
            else:
                setattr(st, name, _simple_sink(stats, name))
        yield
    finally:
        for name, original in originals.items():
            setattr(st, name, original)


def _timed_request_memo(
    original: Callable[..., Any],
    key_fn: Callable[..., Any],
    stats: dict[str, Any],
    name: str,
) -> Callable[..., Any]:
    cache: dict[Any, Any] = {}

    def wrapped(*args: Any, **kwargs: Any) -> Any:
        bucket = stats.setdefault(name, {"calls": 0, "misses": 0, "hits": 0, "work_ms": 0.0})
        bucket["calls"] += 1
        key = key_fn(*args, **kwargs)
        if key in cache:
            bucket["hits"] += 1
            return cache[key]
        bucket["misses"] += 1
        started = perf_counter()
        value = original(*args, **kwargs)
        bucket["work_ms"] += (perf_counter() - started) * 1000.0
        cache[key] = value
        return value

    return wrapped


def _schedule_key(day_str: Any, *args: Any, **kwargs: Any) -> tuple[str]:
    return (str(day_str or "").strip(),)


def _calibration_key(*args: Any, **kwargs: Any) -> tuple[str]:
    return ("frozen-calibration",)


def _store_speed_stats(stats: dict[str, Any], total_ms: float) -> None:
    try:
        st.session_state["nfl_moneyline_speed_v12_last"] = {
            "version": MODEL_VERSION,
            "total_wrapper_ms": max(0.0, float(total_ms)),
            "schedule": dict(stats.get("schedule") or {}),
            "calibration": dict(stats.get("calibration") or {}),
            "suppressed": dict(stats.get("suppressed") or {}),
            "suppressed_total": sum(int(v or 0) for v in (stats.get("suppressed") or {}).values()),
            "performance_only": True,
            "sportsbook_model_influence": 0.0,
            "stake_sizing_enabled": False,
            "monte_carlo_simulations": MONTE_CARLO_SIMULATIONS,
            "model_math_changed": False,
            "market_semantics_changed": False,
            "freshness_rules_changed": False,
            "identity_rules_changed": False,
        }
    except Exception:
        pass


def _fast_hidden_run_frozen_engine(stats: dict[str, Any]) -> None:
    """Execute exact frozen V8 while suppressing its already-hidden UI deltas."""
    # Keep the certified V11 hiding guarantee: CSS exists before the keyed
    # legacy container enters the DOM.
    st.markdown(v11._HIDDEN_LEGACY_CSS, unsafe_allow_html=True)
    hidden = st.container(key=v11.LEGACY_CONTAINER_KEY)
    with hidden:
        legacy = st.empty()
        with legacy.container():
            with _sink_hidden_presentation(stats):
                v11.frozen_v9.frozen.render_nfl_moneyline_hub()
        legacy.empty()


def render_nfl_hub(market: str = "Moneyline"):
    if str(market or "Moneyline") != "Moneyline":
        raise RuntimeError("Moneyline V12 direct handler is Moneyline only.")

    stats: dict[str, Any] = {}
    started = perf_counter()

    original_schedule = foundation.load_nfl_slate
    original_calibration = calibration_page._fit_calibration_model
    original_hidden_runner = v11._hidden_run_frozen_engine

    foundation.load_nfl_slate = _timed_request_memo(
        original_schedule, _schedule_key, stats, "schedule"
    )
    calibration_page._fit_calibration_model = _timed_request_memo(
        original_calibration, _calibration_key, stats, "calibration"
    )
    v11._hidden_run_frozen_engine = lambda: _fast_hidden_run_frozen_engine(stats)

    try:
        return v11.render_nfl_hub(market)
    finally:
        v11._hidden_run_frozen_engine = original_hidden_runner
        calibration_page._fit_calibration_model = original_calibration
        foundation.load_nfl_slate = original_schedule
        _store_speed_stats(stats, (perf_counter() - started) * 1000.0)


__all__ = [
    "FROZEN_ENGINE",
    "FROZEN_PRIOR",
    "MODEL_VERSION",
    "MONTE_CARLO_SIMULATIONS",
    "PERFORMANCE_ONLY",
    "SPORTSBOOK_MODEL_INFLUENCE",
    "STAKE_SIZING_ENABLED",
    "_Sink",
    "_calibration_key",
    "_fast_hidden_run_frozen_engine",
    "_schedule_key",
    "_sink_hidden_presentation",
    "_timed_request_memo",
    "render_nfl_hub",
]
