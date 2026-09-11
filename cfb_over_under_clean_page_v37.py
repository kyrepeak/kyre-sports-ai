"""CFB Over/Under Clean Page V37 — exact ESPN logos wired to real Step 1.

Additive presentation-only hotfix over certified Clean Page V36. The V36
resolver itself was correct, but its injection point landed on V32's timed
presentation closure instead of the original Step-1 renderer. That closure had
already captured the old V17 Step-1 function, so replacing a global on the
closure could not replace the logo resolver used inside the captured function.

V37 fixes only that wiring: it clones the real V17 ``_step1`` function with the
exact ESPN team-ID-only V3 resolver, then re-applies the existing Step-1 profiler
timer around that exact renderer. All V35/V36 market, prewarm, runtime, identity,
full-slate, and frozen V14 projection contracts remain unchanged.
"""
from __future__ import annotations

from time import perf_counter
from typing import Any

import streamlit as st

import cfb_over_under_clean_page_v17 as step1_owner
import cfb_over_under_clean_page_v19 as clone_tools
import cfb_over_under_clean_page_v36 as frozen_page
import cfb_over_under_logo_resolver_v3 as logo_v3
import cfb_over_under_performance_profiler_v1 as profiler

MODEL_VERSION = "CFB O/U CLEAN PAGE V37 • EXACT ESPN TEAM-ID LOGOS WIRED"
MARKET = "Over/Under"
FROZEN_PAGE = "cfb_over_under_clean_page_v36"
ACTIVE_LOGO_RESOLVER = "cfb_over_under_logo_resolver_v3"
ACTIVE_MARKET_ADAPTER = frozen_page.ACTIVE_MARKET_ADAPTER
ACTIVE_MARKET_INTELLIGENCE = frozen_page.ACTIVE_MARKET_INTELLIGENCE
ACTIVE_SCHEDULE = frozen_page.ACTIVE_SCHEDULE
FROZEN_RUNTIME_SLATE = frozen_page.FROZEN_RUNTIME_SLATE
ACTIVE_RUNTIME_SLATE = frozen_page.ACTIVE_RUNTIME_SLATE
ACTIVE_PERFORMANCE_PROFILER = frozen_page.ACTIVE_PERFORMANCE_PROFILER
ACTIVE_ANALYSIS_PREWARM = frozen_page.ACTIVE_ANALYSIS_PREWARM

_V37_MARKER = (
    "🟢 CFB O/U • CLEAN PAGE V37 ACTIVE • EXACT ESPN TEAM-ID LOGOS WIRED TO STEP 1 • "
    "V36 EXACT-ID RESOLVER PRESERVED • NO NAME-BASED LOGO MATCHING • "
    "NO WIKIPEDIA/WIKIMEDIA LOGO GUESSING • NO LOGO NETWORK SCRAPING • "
    "V35 PERFORMANCE CONTRACT PRESERVED • FRESHNESS-SAFE MARKET SNAPSHOT REUSE ACTIVE • "
    "PARALLEL ANALYSIS PREWARM ACTIVE • CACHE-STABLE ANALYSIS ACTIVE • "
    "PERFORMANCE PROFILER ACTIVE • FUTURE SLATE COVERAGE ACTIVE • "
    "OFFICIAL ESPN IDENTITY RECOVERY • NO FUZZY GAME MATCHING • NO SYNTHETIC IDS • "
    "DISPLAY ONLY • 0.0% SPORTSBOOK PROJECTION INFLUENCE • "
    "FROZEN V14 PROJECTION MATH PRESERVED • READABLE STEPS 4-12 ACTIVE"
)

# Clone the REAL Step-1 renderer, not V32's timing closure. This is the key
# correction over V36.
_STEP1_EXACT = clone_tools._clone_function(
    step1_owner._step1,
    {"logo_resolver": logo_v3},
)


def _step1_v37(*args: Any, **kwargs: Any):
    """Render exact-ID Step 1 while retaining the existing profiler span."""
    return profiler.timed_call(
        "presentation.step1",
        _STEP1_EXACT,
        *args,
        **kwargs,
    )


_BASE_RENDER_GLOBALS = frozen_page._RENDER_V36.__globals__
_BASE_PAGE = _BASE_RENDER_GLOBALS["frozen_page"]
_BASE_ST = _BASE_RENDER_GLOBALS["st"]


class _StepPageV37Proxy:
    def __getattr__(self, name: str) -> Any:
        if name == "_step1":
            return _step1_v37
        return getattr(_BASE_PAGE, name)


class _StreamlitV37Proxy:
    """Advance the visible marker regardless of which frozen marker enters first."""

    _MARKER_TOKENS = (
        "CFB O/U • CLEAN PAGE V18 ACTIVE",
        "CFB O/U • CLEAN PAGE V19 ACTIVE",
        "CFB O/U • CLEAN PAGE V20 ACTIVE",
        "CFB O/U • CLEAN PAGE V30 ACTIVE",
        "CFB O/U • CLEAN PAGE V31 ACTIVE",
        "CFB O/U • CLEAN PAGE V32 ACTIVE",
        "CFB O/U • CLEAN PAGE V33 ACTIVE",
        "CFB O/U • CLEAN PAGE V34 ACTIVE",
        "CFB O/U • CLEAN PAGE V35 ACTIVE",
        "CFB O/U • CLEAN PAGE V36 ACTIVE",
        "READABLE STEP 12 FINAL CERTIFICATION ACTIVE",
    )

    def __getattr__(self, name: str) -> Any:
        return getattr(_BASE_ST, name)

    def caption(self, body: Any, *args: Any, **kwargs: Any) -> Any:
        text = str(body or "")
        if any(token in text for token in self._MARKER_TOKENS):
            return st.caption(_V37_MARKER, *args, **kwargs)
        return _BASE_ST.caption(body, *args, **kwargs)


_STEP_PAGE_PROXY = _StepPageV37Proxy()
_ST_PROXY = _StreamlitV37Proxy()

_RENDER_V37 = clone_tools._clone_function(
    frozen_page._RENDER_V36,
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
        result = _RENDER_V37(section_header, status_info, team_logo, h)
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
                "step1_logo_wiring": "real_v17_step1_exact_espn_team_id_v3",
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
        raise ValueError(f"Clean O/U Page V37 received unsupported market: {market}")
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
    "_STEP1_EXACT",
    "_V37_MARKER",
    "_step1_v37",
    "render_cfb_hub",
    "render_over_under_hub",
]
