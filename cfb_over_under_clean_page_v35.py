"""CFB Over/Under Clean Page V35 — freshness-safe market snapshot reuse.

Additive performance wrapper over certified Clean Page V34. V35 preserves the
parallel selected-game analysis prewarm, cache-stable V16 analysis path, V32
profiler, official identity recovery and every frozen model contract. The only
behavioral change is routing the live sportsbook load through Market Adapter V3,
which reuses successful snapshots for up to 240 seconds while re-running the
300-second freshness firewall on every public access.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from time import perf_counter
from typing import Any

import streamlit as st

import cfb_over_under_analysis_prewarm_v1 as prewarm
import cfb_over_under_clean_page_v19 as clone_tools
import cfb_over_under_clean_page_v34 as frozen_page
import cfb_over_under_market_adapter_v3 as market_v3
import cfb_over_under_performance_profiler_v1 as profiler

MODEL_VERSION = "CFB O/U CLEAN PAGE V35 • FRESHNESS-SAFE MARKET SNAPSHOT REUSE"
MARKET = "Over/Under"
FROZEN_PAGE = "cfb_over_under_clean_page_v34"
ACTIVE_MARKET_ADAPTER = "cfb_over_under_market_adapter_v3"
ACTIVE_MARKET_INTELLIGENCE = frozen_page.ACTIVE_MARKET_INTELLIGENCE
ACTIVE_SCHEDULE = frozen_page.ACTIVE_SCHEDULE
FROZEN_RUNTIME_SLATE = frozen_page.FROZEN_RUNTIME_SLATE
ACTIVE_RUNTIME_SLATE = frozen_page.ACTIVE_RUNTIME_SLATE
ACTIVE_PERFORMANCE_PROFILER = frozen_page.ACTIVE_PERFORMANCE_PROFILER
ACTIVE_ANALYSIS_PREWARM = frozen_page.ACTIVE_ANALYSIS_PREWARM

_V35_MARKER = (
    "⚡ CFB O/U • CLEAN PAGE V35 ACTIVE • FRESHNESS-SAFE MARKET SNAPSHOT REUSE ACTIVE • "
    "FRESHNESS REVALIDATED EVERY ACCESS • 240S SUCCESS SNAPSHOT CACHE • "
    "PARALLEL ANALYSIS PREWARM ACTIVE • CACHE-STABLE ANALYSIS ACTIVE • "
    "PERFORMANCE PROFILER ACTIVE • V34/V33/V32/V31 BASE CONTRACT PRESERVED • "
    "CFB O/U • CLEAN PAGE V30 ACTIVE • FUTURE SLATE COVERAGE ACTIVE • "
    "OFFICIAL ESPN IDENTITY RECOVERY • NO FUZZY MATCHING • "
    "NO FUZZY GAME MATCHING • NO SYNTHETIC IDS • FRESHNESS FIREWALL ACTIVE • "
    "DISPLAY ONLY • 0.0% PROJECTION INFLUENCE • "
    "0.0% SPORTSBOOK PROJECTION INFLUENCE • FROZEN PROJECTION MATH PRESERVED • "
    "FROZEN V14 PROJECTION MATH PRESERVED • READABLE STEPS 4-12 ACTIVE"
)

_BASE_GLOBALS = frozen_page._RENDER_V34.__globals__
_BASE_ST = _BASE_GLOBALS["st"]


class _MarketV35Proxy:
    """Keep V34 parallel prewarm while swapping only the market adapter to V3."""

    def __getattr__(self, name: str) -> Any:
        return getattr(market_v3, name)

    def load_odds_for_date(self, *args: Any, **kwargs: Any):
        day = str(args[0] if args else kwargs.get("target_date") or "").strip()[:10]
        selected_game = frozen_page._selected_game_from_context(day)
        trace = profiler.current_trace()

        def load_market():
            return profiler.timed_call(
                "market.load_odds_for_date",
                market_v3.load_odds_for_date,
                *args,
                **kwargs,
            )

        if not selected_game:
            return load_market()

        prewarm_started = perf_counter()
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                prewarm.warm_selected_game,
                selected_game,
                day,
            )
            market_result = load_market()
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

    def attach_market_lines(self, *args: Any, **kwargs: Any):
        return profiler.timed_call(
            "market.attach_market_lines",
            market_v3.attach_market_lines,
            *args,
            **kwargs,
        )


class _StreamlitV35Proxy:
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
            or "CFB O/U • CLEAN PAGE V34 ACTIVE" in text
            or "READABLE STEP 12 FINAL CERTIFICATION ACTIVE" in text
        ):
            return st.caption(_V35_MARKER, *args, **kwargs)
        return _BASE_ST.caption(body, *args, **kwargs)


_MARKET_PROXY = _MarketV35Proxy()
_ST_PROXY = _StreamlitV35Proxy()

_RENDER_V35 = clone_tools._clone_function(
    frozen_page._RENDER_V34,
    {
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
        result = _RENDER_V35(section_header, status_info, team_logo, h)
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
        raise ValueError(f"Clean O/U Page V35 received unsupported market: {market}")
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
    "render_cfb_hub",
    "render_over_under_hub",
]
