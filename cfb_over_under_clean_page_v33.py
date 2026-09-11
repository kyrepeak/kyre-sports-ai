"""CFB Over/Under Clean Page V33 — cache-stable analysis activation.

Additive performance wrapper over certified Clean Page V32. V33 preserves the
V32 profiler and every visual/model contract while replacing only the runtime
slate object with V16, which removes certified display-only ``market_*`` fields
from the expensive frozen analysis cache input and restores them after analysis.

Frozen V14 projection math, official ESPN identity recovery, Schedule V7,
Market Adapter V2 semantics, qualification thresholds and 0.0% sportsbook
projection influence remain unchanged.
"""
from __future__ import annotations

from time import perf_counter
from typing import Any

import streamlit as st

import cfb_over_under_clean_page_v19 as clone_tools
import cfb_over_under_clean_page_v32 as frozen_page
import cfb_over_under_performance_profiler_v1 as profiler
import cfb_over_under_slate_v16_cache_stable as runtime_v16

MODEL_VERSION = "CFB O/U CLEAN PAGE V33 • CACHE-STABLE ANALYSIS ACTIVE"
MARKET = "Over/Under"
FROZEN_PAGE = "cfb_over_under_clean_page_v32"
ACTIVE_MARKET_ADAPTER = frozen_page.ACTIVE_MARKET_ADAPTER
ACTIVE_MARKET_INTELLIGENCE = frozen_page.ACTIVE_MARKET_INTELLIGENCE
ACTIVE_SCHEDULE = frozen_page.ACTIVE_SCHEDULE
FROZEN_RUNTIME_SLATE = frozen_page.ACTIVE_RUNTIME_SLATE
ACTIVE_RUNTIME_SLATE = "cfb_over_under_slate_v16_cache_stable"
ACTIVE_PERFORMANCE_PROFILER = frozen_page.ACTIVE_PERFORMANCE_PROFILER

_V33_MARKER = (
    "⚡ CFB O/U • CLEAN PAGE V33 ACTIVE • CACHE-STABLE ANALYSIS ACTIVE • "
    "PERFORMANCE PROFILER ACTIVE • V32/V31 BASE CONTRACT PRESERVED • "
    "FUTURE SLATE COVERAGE ACTIVE • OFFICIAL ESPN IDENTITY RECOVERY • "
    "NO FUZZY MATCHING • NO FUZZY GAME MATCHING • NO SYNTHETIC IDS • "
    "FRESHNESS FIREWALL ACTIVE • DISPLAY ONLY • "
    "0.0% PROJECTION INFLUENCE • 0.0% SPORTSBOOK PROJECTION INFLUENCE • "
    "FROZEN PROJECTION MATH PRESERVED • FROZEN V14 PROJECTION MATH PRESERVED • "
    "READABLE STEPS 4-12 ACTIVE"
)

_BASE_GLOBALS = frozen_page._RENDER_V32.__globals__
_BASE_PAGE = _BASE_GLOBALS["frozen_page"]
_BASE_ST = _BASE_GLOBALS["st"]


class _CacheStablePageProxy:
    """Preserve V32 presentation/final model; replace only runtime analysis."""

    def __init__(self) -> None:
        self._runtime = frozen_page._RuntimeTimingProxy(runtime_v16)

    def __getattr__(self, name: str) -> Any:
        if name == "runtime_slate":
            return self._runtime
        return getattr(_BASE_PAGE, name)


class _StreamlitV33Proxy:
    """Keep V32 profiler enqueue timing while advancing only the page marker."""

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
            or "READABLE STEP 12 FINAL CERTIFICATION ACTIVE" in text
        ):
            return st.caption(_V33_MARKER, *args, **kwargs)
        return _BASE_ST.caption(body, *args, **kwargs)


_PAGE_PROXY = _CacheStablePageProxy()
_ST_PROXY = _StreamlitV33Proxy()

_RENDER_V33 = clone_tools._clone_function(
    frozen_page._RENDER_V32,
    {
        "frozen_page": _PAGE_PROXY,
        "st": _ST_PROXY,
    },
)


def render_over_under_hub(section_header=None, status_info=None, team_logo=None, h=None) -> None:
    trace = profiler.PerfTrace()
    token = profiler.set_active_trace(trace)
    slot = st.empty()
    started = perf_counter()
    try:
        result = _RENDER_V33(section_header, status_info, team_logo, h)
    finally:
        trace.add("page.total_server_render", perf_counter() - started)
        profiler.reset_active_trace(token)
        try:
            st.session_state["cfb_ou_perf_v1_last"] = {
                "version": profiler.MODEL_VERSION,
                "active_page": MODEL_VERSION,
                "active_runtime_slate": ACTIVE_RUNTIME_SLATE,
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
        raise ValueError(f"Clean O/U Page V33 received unsupported market: {market}")
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
