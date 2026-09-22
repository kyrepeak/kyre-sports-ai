"""CFB Over/Under Clean Page V36 — exact ESPN team-ID logos.

Additive presentation-only wrapper over certified Clean Page V35. V36 swaps
only Step 1's logo resolver from the network-heavy multi-source V2 path to the
exact ESPN team-ID-only V3 resolver. Everything else remains V35 unchanged,
including market freshness, parallel prewarm, cache-stable analysis, future
slate coverage, performance profiling, and frozen V14 projection math.
"""
from __future__ import annotations

from time import perf_counter
from typing import Any

import streamlit as st

import cfb_over_under_clean_page_v19 as clone_tools
import cfb_over_under_clean_page_v35 as frozen_page
import cfb_over_under_logo_resolver_v3 as logo_v3
import cfb_over_under_performance_profiler_v1 as profiler

MODEL_VERSION = "CFB O/U CLEAN PAGE V36 • EXACT ESPN TEAM-ID LOGOS"
MARKET = "Over/Under"
FROZEN_PAGE = "cfb_over_under_clean_page_v35"
ACTIVE_LOGO_RESOLVER = "cfb_over_under_logo_resolver_v3"
ACTIVE_MARKET_ADAPTER = frozen_page.ACTIVE_MARKET_ADAPTER
ACTIVE_MARKET_INTELLIGENCE = frozen_page.ACTIVE_MARKET_INTELLIGENCE
ACTIVE_SCHEDULE = frozen_page.ACTIVE_SCHEDULE
FROZEN_RUNTIME_SLATE = frozen_page.FROZEN_RUNTIME_SLATE
ACTIVE_RUNTIME_SLATE = frozen_page.ACTIVE_RUNTIME_SLATE
ACTIVE_PERFORMANCE_PROFILER = frozen_page.ACTIVE_PERFORMANCE_PROFILER
ACTIVE_ANALYSIS_PREWARM = frozen_page.ACTIVE_ANALYSIS_PREWARM

_V36_MARKER = (
    "🟢 CFB O/U • CLEAN PAGE V36 ACTIVE • EXACT ESPN TEAM-ID LOGOS ACTIVE • "
    "NO NAME-BASED LOGO MATCHING • NO WIKIPEDIA/WIKIMEDIA LOGO GUESSING • "
    "NO LOGO NETWORK SCRAPING • V35 PERFORMANCE CONTRACT PRESERVED • "
    "FRESHNESS-SAFE MARKET SNAPSHOT REUSE ACTIVE • PARALLEL ANALYSIS PREWARM ACTIVE • "
    "CACHE-STABLE ANALYSIS ACTIVE • PERFORMANCE PROFILER ACTIVE • FUTURE SLATE COVERAGE ACTIVE • "
    "OFFICIAL ESPN IDENTITY RECOVERY • NO FUZZY GAME MATCHING • NO SYNTHETIC IDS • "
    "DISPLAY ONLY • 0.0% SPORTSBOOK PROJECTION INFLUENCE • "
    "FROZEN V14 PROJECTION MATH PRESERVED • READABLE STEPS 4-12 ACTIVE"
)

_BASE_RENDER_GLOBALS = frozen_page._RENDER_V35.__globals__
_BASE_STEP_PAGE = _BASE_RENDER_GLOBALS["frozen_page"]
_BASE_ST = _BASE_RENDER_GLOBALS["st"]

_STEP1_V36 = clone_tools._clone_function(
    _BASE_STEP_PAGE._step1,
    {"logo_resolver": logo_v3},
)


class _StepPageV36Proxy:
    def __getattr__(self, name: str) -> Any:
        if name == "_step1":
            return _STEP1_V36
        return getattr(_BASE_STEP_PAGE, name)


class _StreamlitV36Proxy:
    def __getattr__(self, name: str) -> Any:
        return getattr(_BASE_ST, name)

    def caption(self, body: Any, *args: Any, **kwargs: Any) -> Any:
        text = str(body or "")
        if "CFB O/U • CLEAN PAGE V35 ACTIVE" in text:
            return st.caption(_V36_MARKER, *args, **kwargs)
        return _BASE_ST.caption(body, *args, **kwargs)


_STEP_PAGE_PROXY = _StepPageV36Proxy()
_ST_PROXY = _StreamlitV36Proxy()

_RENDER_V36 = clone_tools._clone_function(
    frozen_page._RENDER_V35,
    {
        "frozen_page": _STEP_PAGE_PROXY,
        "st": _ST_PROXY,
    },
)


def render_over_under_hub(section_header=None, status_info=None, team_logo=None, h=None) -> None:
    trace = profiler.PerfTrace()
    token = profiler.set_active_trace(trace)
    slot = st.empty()
    started = perf_counter()
    try:
        result = _RENDER_V36(section_header, status_info, team_logo, h)
    finally:
        trace.add("page.total_server_render", perf_counter() - started)
        profiler.reset_active_trace(token)
        try:
            st.session_state["cfb_ou_perf_v1_last"] = {
                "version": profiler.MODEL_VERSION,
                "active_page": MODEL_VERSION,
                "active_runtime_slate": ACTIVE_RUNTIME_SLATE,
                "active_market_adapter": ACTIVE_MARKET_ADAPTER,
                "active_prewarm": ACTIVE_ANALYSIS_PREWARM,
                "active_logo_resolver": ACTIVE_LOGO_RESOLVER,
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
        raise ValueError(f"Clean O/U Page V36 received unsupported market: {market}")
    return render_over_under_hub(section_header, status_info, team_logo, h)


__all__ = [
    "ACTIVE_ANALYSIS_PREWARM",
    "ACTIVE_LOGO_RESOLVER",
    "ACTIVE_MARKET_ADAPTER",
    "ACTIVE_MARKET_INTELLIGENCE",
    "ACTIVE_PERFORMANCE_PROFILER",
    "ACTIVE_RUNTIME_SLATE",
    "ACTIVE_SCHEDULE",
    "FROZEN_PAGE",
    "FROZEN_RUNTIME_SLATE",
    "MARKET",
    "MODEL_VERSION",
    "_STEP1_V36",
    "_V36_MARKER",
    "render_cfb_hub",
    "render_over_under_hub",
]
