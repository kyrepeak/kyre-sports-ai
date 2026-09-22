"""NFL Rushing Yards V10 — speed-only request-scope reuse layer.

V10 is additive over the certified final Page Build V9. It changes no page
content, projection math, market semantics, freshness rules, identity rules, or
betting behavior. During one Streamlit render only, it memoizes repeated calls
that historical presentation layers intentionally make against the same exact
event/player inputs.

Frozen owners remain V9/V8/... and the certified projection/market clients.
Sportsbook projection influence remains exactly 0.0%.
"""
from __future__ import annotations

from time import perf_counter
from typing import Any, Callable

import streamlit as st

import nfl_rushing_yards_hub_v1 as context_page
import nfl_rushing_yards_hub_v2 as projection_page
import nfl_rushing_yards_hub_v3 as market_page
import nfl_rushing_yards_hub_v9 as prior

MODEL_VERSION = "NFL RUSHING YARDS V10 • PERFORMANCE FAST REUSE V1"
FROZEN_PRIOR = "nfl_rushing_yards_hub_v9"
PERFORMANCE_ONLY = True
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0


def _safe(value: Any, default: str = "") -> str:
    text = str(value if value is not None else "").strip()
    return text or default


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


def _context_key(event_id: Any, *args: Any, **kwargs: Any) -> tuple[str]:
    return (_safe(event_id),)


def _projection_key(context: Any, *args: Any, **kwargs: Any) -> tuple[str, str, int]:
    if not isinstance(context, dict):
        return ("", "", id(context))
    return (
        _safe(context.get("official_event_id")),
        _safe(context.get("captured_at_utc")),
        len(context.get("teams") or []),
    )


def _market_key(event_id: Any, *args: Any, **kwargs: Any) -> tuple[str]:
    return (_safe(event_id),)


def _athlete_market_key(
    event_market: Any,
    official_athlete_id: Any,
    official_team_id: Any = "",
    *args: Any,
    **kwargs: Any,
) -> tuple[str, str, str, str]:
    market = event_market if isinstance(event_market, dict) else {}
    return (
        _safe(market.get("official_event_id")),
        _safe(market.get("captured_at_utc")),
        _safe(official_athlete_id),
        _safe(official_team_id),
    )


def _store_speed_stats(stats: dict[str, Any], total_ms: float) -> None:
    try:
        st.session_state["nfl_rushing_yards_speed_v1_last"] = {
            "version": MODEL_VERSION,
            "total_wrapper_ms": max(0.0, float(total_ms)),
            "context": dict(stats.get("context") or {}),
            "projection": dict(stats.get("projection") or {}),
            "market": dict(stats.get("market") or {}),
            "athlete_market": dict(stats.get("athlete_market") or {}),
            "performance_only": True,
            "sportsbook_projection_influence": 0.0,
            "projection_math_changed": False,
            "market_semantics_changed": False,
        }
    except Exception:
        pass


def render_nfl_rushing_yards_hub() -> None:
    """Render frozen V9 while reusing identical per-render work."""
    stats: dict[str, Any] = {}
    started = perf_counter()

    original_context = context_page._load_rushing_context
    original_projection = projection_page.projection.build_event_projections
    original_market = market_page._load_rushing_market
    original_athlete_market = market_page.market_api.market_for_athlete

    context_page._load_rushing_context = _timed_request_memo(
        original_context, _context_key, stats, "context"
    )
    projection_page.projection.build_event_projections = _timed_request_memo(
        original_projection, _projection_key, stats, "projection"
    )
    market_page._load_rushing_market = _timed_request_memo(
        original_market, _market_key, stats, "market"
    )
    market_page.market_api.market_for_athlete = _timed_request_memo(
        original_athlete_market, _athlete_market_key, stats, "athlete_market"
    )

    try:
        return prior.render_nfl_rushing_yards_hub()
    finally:
        context_page._load_rushing_context = original_context
        projection_page.projection.build_event_projections = original_projection
        market_page._load_rushing_market = original_market
        market_page.market_api.market_for_athlete = original_athlete_market
        _store_speed_stats(stats, (perf_counter() - started) * 1000.0)


def render_nfl_hub(market: str = "Rushing Yards") -> None:
    if str(market or "Rushing Yards") != "Rushing Yards":
        raise ValueError("NFL Rushing Yards V10 only renders the Rushing Yards market.")
    return render_nfl_rushing_yards_hub()


__all__ = [
    "FROZEN_PRIOR",
    "MODEL_VERSION",
    "PERFORMANCE_ONLY",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "_athlete_market_key",
    "_context_key",
    "_market_key",
    "_projection_key",
    "_timed_request_memo",
    "render_nfl_hub",
    "render_nfl_rushing_yards_hub",
]
