"""CFB Over/Under Clean Page V34 — parallel analysis prewarm.

Additive performance wrapper over certified Clean Page V33. V34 keeps the V33
cache-stable runtime and V32 profiler, but overlaps independent selected-game
analysis-source cache warmups with the live sportsbook request.

The certified page still performs the same schedule load, same official ESPN
identity recovery, same market attachment, same explicit analysis line, same
frozen V14 analysis, same readable Steps 1-12, and same full-slate behavior.
Only independent provider waits are overlapped.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextvars import ContextVar
from time import perf_counter
from typing import Any, Mapping

import streamlit as st

import cfb_over_under_analysis_prewarm_v1 as prewarm
import cfb_over_under_clean_page_v19 as clone_tools
import cfb_over_under_clean_page_v33 as frozen_page
import cfb_over_under_performance_profiler_v1 as profiler

MODEL_VERSION = "CFB O/U CLEAN PAGE V34 • PARALLEL ANALYSIS PREWARM ACTIVE"
MARKET = "Over/Under"
FROZEN_PAGE = "cfb_over_under_clean_page_v33"
ACTIVE_MARKET_ADAPTER = frozen_page.ACTIVE_MARKET_ADAPTER
ACTIVE_MARKET_INTELLIGENCE = frozen_page.ACTIVE_MARKET_INTELLIGENCE
ACTIVE_SCHEDULE = frozen_page.ACTIVE_SCHEDULE
FROZEN_RUNTIME_SLATE = frozen_page.FROZEN_RUNTIME_SLATE
ACTIVE_RUNTIME_SLATE = frozen_page.ACTIVE_RUNTIME_SLATE
ACTIVE_PERFORMANCE_PROFILER = frozen_page.ACTIVE_PERFORMANCE_PROFILER
ACTIVE_ANALYSIS_PREWARM = "cfb_over_under_analysis_prewarm_v1"

_V34_MARKER = (
    "⚡ CFB O/U • CLEAN PAGE V34 ACTIVE • PARALLEL ANALYSIS PREWARM ACTIVE • "
    "CACHE-STABLE ANALYSIS ACTIVE • PERFORMANCE PROFILER ACTIVE • "
    "CFB O/U • CLEAN PAGE V33 ACTIVE • V32/V31 BASE CONTRACT PRESERVED • "
    "CFB O/U • CLEAN PAGE V30 ACTIVE • FUTURE SLATE COVERAGE ACTIVE • "
    "OFFICIAL ESPN IDENTITY RECOVERY • NO FUZZY MATCHING • "
    "NO FUZZY GAME MATCHING • NO SYNTHETIC IDS • FRESHNESS FIREWALL ACTIVE • "
    "DISPLAY ONLY • 0.0% PROJECTION INFLUENCE • "
    "0.0% SPORTSBOOK PROJECTION INFLUENCE • FROZEN PROJECTION MATH PRESERVED • "
    "FROZEN V14 PROJECTION MATH PRESERVED • READABLE STEPS 4-12 ACTIVE"
)

_BASE_GLOBALS = frozen_page._RENDER_V33.__globals__
_BASE_SCHEDULE = _BASE_GLOBALS["schedule_v6"]
_BASE_MARKET = _BASE_GLOBALS["market_adapter"]
_BASE_PAGE = _BASE_GLOBALS["frozen_page"]
_BASE_ST = _BASE_GLOBALS["st"]
_BASE_LINE_BOARD = _BASE_GLOBALS["_line_board"]

_SCHEDULE_CONTEXT: ContextVar[dict[str, Any]] = ContextVar(
    "cfb_ou_v34_schedule_context",
    default={},
)


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _selected_game_from_context(day: str) -> dict[str, Any]:
    context = dict(_SCHEDULE_CONTEXT.get() or {})
    games = list(context.get("games") or [])
    if not games or _clean(context.get("day")) != _clean(day)[:10]:
        return {}
    key = f"cfb_ou_v18_matchup_{_clean(day)[:10]}"
    try:
        index = int(st.session_state.get(key, 0))
    except Exception:
        index = 0
    if index < 0 or index >= len(games):
        index = 0
    game = games[index]
    return dict(game) if isinstance(game, Mapping) else {}


class _SchedulePrewarmProxy:
    def __getattr__(self, name: str) -> Any:
        return getattr(_BASE_SCHEDULE, name)

    def load_with_diagnostics(self, *args: Any, **kwargs: Any):
        games, diag = _BASE_SCHEDULE.load_with_diagnostics(*args, **kwargs)
        day = ""
        if args:
            day = _clean(args[0])[:10]
        if not day:
            day = _clean(kwargs.get("target_date"))[:10]
        _SCHEDULE_CONTEXT.set({
            "day": day,
            "games": [dict(game) for game in games],
        })
        return games, diag


class _MarketPrewarmProxy:
    """Overlap source prewarm with the unchanged live sportsbook request."""

    def __getattr__(self, name: str) -> Any:
        return getattr(_BASE_MARKET, name)

    def load_odds_for_date(self, *args: Any, **kwargs: Any):
        day = _clean(args[0] if args else kwargs.get("target_date"))[:10]
        selected_game = _selected_game_from_context(day)
        trace = profiler.current_trace()

        if not selected_game:
            return _BASE_MARKET.load_odds_for_date(*args, **kwargs)

        prewarm_started = perf_counter()
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                prewarm.warm_selected_game,
                selected_game,
                day,
            )
            market_result = _BASE_MARKET.load_odds_for_date(*args, **kwargs)
            wait_started = perf_counter()
            try:
                prewarm_diag = future.result()
            except Exception as exc:
                prewarm_diag = {
                    "version": prewarm.MODEL_VERSION,
                    "status": "UNAVAILABLE",
                    "elapsed_ms": round((perf_counter() - prewarm_started) * 1000.0, 1),
                    "error": f"{type(exc).__name__}: {exc}"[:400],
                }
            wait_seconds = perf_counter() - wait_started

        total_seconds = perf_counter() - prewarm_started
        if trace is not None:
            trace.add("analysis.prewarm.parallel", total_seconds)
            trace.add("analysis.prewarm.wait_after_market", wait_seconds)

        try:
            st.session_state["cfb_ou_prewarm_v1_last"] = prewarm_diag
        except Exception:
            pass
        return market_result


class _StreamlitV34Proxy:
    def __getattr__(self, name: str) -> Any:
        return getattr(_BASE_ST, name)

    def caption(self, body: Any, *args: Any, **kwargs: Any) -> Any:
        text = str(body or "")
        if (
            "CFB O/U • CLEAN PAGE V18 ACTIVE" in text
            or "CFB O/U • CLEAN PAGE V19 ACTIVE" in text
            or "CFB O/U • CLEAN PAGE V20 ACTIVE" in text
            or "CFB O/U • CLEAN PAGE V30 ACTIVE" in text
            or "CFB O/U • CLEAN PAGE V31 ACTIVE" in text
            or "CFB O/U • CLEAN PAGE V32 ACTIVE" in text
            or "CFB O/U • CLEAN PAGE V33 ACTIVE" in text
            or "READABLE STEP 12 FINAL CERTIFICATION ACTIVE" in text
        ):
            return st.caption(_V34_MARKER, *args, **kwargs)
        return _BASE_ST.caption(body, *args, **kwargs)


_SCHEDULE_PROXY = _SchedulePrewarmProxy()
_MARKET_PROXY = _MarketPrewarmProxy()
_ST_PROXY = _StreamlitV34Proxy()

_RENDER_V34 = clone_tools._clone_function(
    frozen_page._RENDER_V33,
    {
        "schedule_v6": _SCHEDULE_PROXY,
        "market_adapter": _MARKET_PROXY,
        "st": _ST_PROXY,
    },
)


def render_over_under_hub(section_header=None, status_info=None, team_logo=None, h=None) -> None:
    trace = profiler.PerfTrace()
    token = profiler.set_active_trace(trace)
    slot = st.empty()
    started = perf_counter()
    try:
        result = _RENDER_V34(section_header, status_info, team_logo, h)
    finally:
        trace.add("page.total_server_render", perf_counter() - started)
        profiler.reset_active_trace(token)
        try:
            st.session_state["cfb_ou_perf_v1_last"] = {
                "version": profiler.MODEL_VERSION,
                "active_page": MODEL_VERSION,
                "active_runtime_slate": ACTIVE_RUNTIME_SLATE,
                "active_prewarm": ACTIVE_ANALYSIS_PREWARM,
                "total_ms": trace.total_ms(),
                "stages": trace.aggregate(),
                "projection_weight": 0.0,
                "may_modify_projection": False,
            }
        except Exception:
            pass
        slot.caption(trace.compact_caption(limit=8))
    return result


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if market != MARKET:
        raise ValueError(f"Clean O/U Page V34 received unsupported market: {market}")
    return render_over_under_hub(section_header, status_info, team_logo, h)


__all__ = [
    "ACTIVE_ANALYSIS_PREWARM",
    "ACTIVE_MARKET_ADAPTER",
    "ACTIVE_MARKET_INTELLIGENCE",
    "ACTIVE_PERFORMANCE_PROFILER",
    "ACTIVE_RUNTIME_SLATE",
    "ACTIVE_SCHEDULE",
    "FROZEN_PAGE",
    "FROZEN_RUNTIME_SLATE",
    "MARKET",
    "MODEL_VERSION",
    "_selected_game_from_context",
    "render_cfb_hub",
    "render_over_under_hub",
]
