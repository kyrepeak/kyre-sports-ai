"""CFB Over/Under Clean Page V32 — performance profiler activation.

Additive measurement-only wrapper over certified Clean Page V31. V32 records
server-side elapsed time around the existing schedule, market, selected-game
analysis, presentation, and full-slate UI paths. It changes no data source
semantics, identity policy, projection formula, threshold, ranking, or selection.
"""
from __future__ import annotations

from time import perf_counter
from typing import Any

import streamlit as st

import cfb_over_under_clean_page_v19 as clone_tools
import cfb_over_under_clean_page_v31 as frozen_page
import cfb_over_under_performance_profiler_v1 as profiler

MODEL_VERSION = "CFB O/U CLEAN PAGE V32 • PERFORMANCE PROFILER ACTIVE"
MARKET = "Over/Under"
FROZEN_PAGE = "cfb_over_under_clean_page_v31"
ACTIVE_MARKET_ADAPTER = frozen_page.ACTIVE_MARKET_ADAPTER
ACTIVE_MARKET_INTELLIGENCE = frozen_page.ACTIVE_MARKET_INTELLIGENCE
ACTIVE_SCHEDULE = frozen_page.ACTIVE_SCHEDULE
FROZEN_RUNTIME_SLATE = frozen_page.FROZEN_RUNTIME_SLATE
ACTIVE_RUNTIME_SLATE = frozen_page.ACTIVE_RUNTIME_SLATE
ACTIVE_PERFORMANCE_PROFILER = "cfb_over_under_performance_profiler_v1"

_V32_MARKER = (
    "⚡ CFB O/U • CLEAN PAGE V32 ACTIVE • PERFORMANCE PROFILER ACTIVE • "
    "MEASUREMENT ONLY • V31 BASE CONTRACT PRESERVED: "
    "CFB O/U • CLEAN PAGE V31 ACTIVE • DOWNSTREAM IDENTITY BRIDGE ACTIVE • "
    "CFB O/U • CLEAN PAGE V30 ACTIVE • FUTURE SLATE COVERAGE ACTIVE • "
    "OFFICIAL ESPN IDENTITY RECOVERY • NO FUZZY MATCHING • "
    "NO FUZZY GAME MATCHING • NO SYNTHETIC IDS • FRESHNESS FIREWALL ACTIVE • "
    "DISPLAY ONLY • 0.0% PROJECTION INFLUENCE • "
    "0.0% SPORTSBOOK PROJECTION INFLUENCE • FROZEN PROJECTION MATH PRESERVED • "
    "FROZEN V14 PROJECTION MATH PRESERVED • READABLE STEPS 4-12 ACTIVE"
)

_BASE_GLOBALS = frozen_page._RENDER_V31.__globals__
_BASE_SCHEDULE = _BASE_GLOBALS["schedule_v6"]
_BASE_MARKET = _BASE_GLOBALS["market_adapter"]
_BASE_PAGE = _BASE_GLOBALS["frozen_page"]
_BASE_ST = _BASE_GLOBALS["st"]
_BASE_LINE_BOARD = _BASE_GLOBALS["_line_board"]


class _ScheduleTimingProxy:
    def __getattr__(self, name: str) -> Any:
        return getattr(_BASE_SCHEDULE, name)

    def load_with_diagnostics(self, *args: Any, **kwargs: Any):
        return profiler.timed_call(
            "schedule.load_with_diagnostics",
            _BASE_SCHEDULE.load_with_diagnostics,
            *args,
            **kwargs,
        )


class _MarketTimingProxy:
    def __getattr__(self, name: str) -> Any:
        return getattr(_BASE_MARKET, name)

    def load_odds_for_date(self, *args: Any, **kwargs: Any):
        return profiler.timed_call(
            "market.load_odds_for_date",
            _BASE_MARKET.load_odds_for_date,
            *args,
            **kwargs,
        )

    def attach_market_lines(self, *args: Any, **kwargs: Any):
        return profiler.timed_call(
            "market.attach_market_lines",
            _BASE_MARKET.attach_market_lines,
            *args,
            **kwargs,
        )


class _RuntimeTimingProxy:
    def __init__(self, base: Any) -> None:
        self._base = base

    def __getattr__(self, name: str) -> Any:
        return getattr(self._base, name)

    def analyze_game(self, *args: Any, **kwargs: Any):
        return profiler.timed_call(
            "analysis.selected_game",
            self._base.analyze_game,
            *args,
            **kwargs,
        )

    def scan_slate(self, *args: Any, **kwargs: Any):
        return profiler.timed_call(
            "analysis.full_slate_scan",
            self._base.scan_slate,
            *args,
            **kwargs,
        )


class _FinalModelTimingProxy:
    def __init__(self, base: Any) -> None:
        self._base = base

    def __getattr__(self, name: str) -> Any:
        return getattr(self._base, name)

    def rank_slate(self, *args: Any, **kwargs: Any):
        return profiler.timed_call(
            "analysis.rank_slate",
            self._base.rank_slate,
            *args,
            **kwargs,
        )


class _FrozenPageTimingProxy:
    _PRESENTATION = {
        "_step1": "presentation.step1",
        "_step2": "presentation.step2",
        "_step3_readable": "presentation.step3",
        "_cert_step": "presentation.step12",
        "_final": "presentation.final",
    }

    def __init__(self, base: Any) -> None:
        self._base = base
        self._runtime = _RuntimeTimingProxy(base.runtime_slate)
        self._final_model = _FinalModelTimingProxy(base.final_model)

    def __getattr__(self, name: str) -> Any:
        if name == "runtime_slate":
            return self._runtime
        if name == "final_model":
            return self._final_model
        attr = getattr(self._base, name)
        if name == "_model_step" and callable(attr):
            def timed_model_step(*args: Any, **kwargs: Any):
                step = args[0] if args else kwargs.get("step", "?")
                return profiler.timed_call(
                    f"presentation.step{step}",
                    attr,
                    *args,
                    **kwargs,
                )
            return timed_model_step
        label = self._PRESENTATION.get(name)
        if label and callable(attr):
            def timed_present(*args: Any, **kwargs: Any):
                return profiler.timed_call(label, attr, *args, **kwargs)
            return timed_present
        return attr


class _StreamlitTimingProxy:
    """Preserve V31 Streamlit behavior while timing expensive enqueue calls."""

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
            or "READABLE STEP 12 FINAL CERTIFICATION ACTIVE" in text
        ):
            return st.caption(_V32_MARKER, *args, **kwargs)
        return _BASE_ST.caption(body, *args, **kwargs)

    def markdown(self, *args: Any, **kwargs: Any) -> Any:
        return profiler.timed_call(
            "ui.markdown_enqueue",
            _BASE_ST.markdown,
            *args,
            **kwargs,
        )

    def data_editor(self, *args: Any, **kwargs: Any) -> Any:
        return profiler.timed_call(
            "ui.full_slate_data_editor",
            _BASE_ST.data_editor,
            *args,
            **kwargs,
        )


_SCHEDULE_PROXY = _ScheduleTimingProxy()
_MARKET_PROXY = _MarketTimingProxy()
_PAGE_PROXY = _FrozenPageTimingProxy(_BASE_PAGE)
_ST_PROXY = _StreamlitTimingProxy()


def _timed_line_board(*args: Any, **kwargs: Any):
    return profiler.timed_call(
        "ui.full_slate_line_board",
        _BASE_LINE_BOARD,
        *args,
        **kwargs,
    )


_RENDER_V32 = clone_tools._clone_function(
    frozen_page._RENDER_V31,
    {
        "schedule_v6": _SCHEDULE_PROXY,
        "market_adapter": _MARKET_PROXY,
        "frozen_page": _PAGE_PROXY,
        "_line_board": _timed_line_board,
        "st": _ST_PROXY,
    },
)


def render_over_under_hub(section_header=None, status_info=None, team_logo=None, h=None) -> None:
    trace = profiler.PerfTrace()
    token = profiler.set_active_trace(trace)
    slot = st.empty()
    started = perf_counter()
    try:
        result = _RENDER_V32(section_header, status_info, team_logo, h)
    finally:
        trace.add("page.total_server_render", perf_counter() - started)
        profiler.reset_active_trace(token)
        try:
            st.session_state["cfb_ou_perf_v1_last"] = {
                "version": profiler.MODEL_VERSION,
                "total_ms": trace.total_ms(),
                "stages": trace.aggregate(),
                "projection_weight": 0.0,
                "may_modify_projection": False,
            }
        except Exception:
            pass
        slot.caption(trace.compact_caption(limit=6))
    return result


def render_cfb_hub(market: str, section_header=None, status_info=None, team_logo=None, h=None) -> None:
    if market != MARKET:
        raise ValueError(f"Clean O/U Page V32 received unsupported market: {market}")
    return render_over_under_hub(section_header, status_info, team_logo, h)


__all__ = [
    "ACTIVE_MARKET_ADAPTER",
    "ACTIVE_MARKET_INTELLIGENCE",
    "ACTIVE_PERFORMANCE_PROFILER",
    "ACTIVE_RUNTIME_SLATE",
    "ACTIVE_SCHEDULE",
    "FROZEN_PAGE",
    "FROZEN_RUNTIME_SLATE",
    "MARKET",
    "MODEL_VERSION",
    "render_cfb_hub",
    "render_over_under_hub",
]
