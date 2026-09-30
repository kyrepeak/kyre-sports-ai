"""WNBA PRA Speed V3 — Step 1 measurement-only profiler.

This layer instruments the frozen Navigation V2 Step-7 PRA route without
changing basketball outputs, request count, navigation behavior, or model math.
"""
from __future__ import annotations

from html import escape
from time import perf_counter
from typing import Any, Callable

import streamlit as st

import wnba_pra_navigation_v2_step1 as navigation
import wnba_pra_performance_v2_step5 as performance
import wnba_pra_player_intelligence_v2_step4 as player_intelligence


MODEL_VERSION = "WNBA PRA SPEED V3 • STEP 1 PROFILER"
SESSION_PROFILE = "ks_wnba_pra_speed_v3_step1_profile"

PROFILER_CONTRACT = {
    "project": "WNBA PRA Speed V3",
    "step": "1/9",
    "scope": "measurement_only",
    "frozen_navigation_steps_1_through_7_modified": False,
    "network_reads_added": 0,
    "reruns_added": 0,
    "model_runs_added": 0,
    "sportsbook_calls_added": 0,
    "monte_carlo_runs_added": 0,
    "projection_math_changed": False,
    "market_math_changed": False,
    "sportsbook_projection_influence": 0.0,
}


def _timed(name: str, fn: Callable[..., Any], timings: dict[str, float], calls: dict[str, int]):
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        started = perf_counter()
        try:
            return fn(*args, **kwargs)
        finally:
            timings[name] = timings.get(name, 0.0) + ((perf_counter() - started) * 1000.0)
            calls[name] = calls.get(name, 0) + 1
    return wrapped


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _render_deployment_marker(state: navigation.NavigationState) -> None:
    st.markdown(
        '<span data-wnba-pra-speed-v3-step1-deployed="true" '
        f'data-wnba-nav-page="{escape(str(state.page), quote=True)}" '
        'style="display:none" aria-hidden="true"></span>',
        unsafe_allow_html=True,
    )


def _render_marker(profile: dict[str, Any]) -> None:
    attrs = {
        "data-wnba-pra-speed-v3-step1": "profiler",
        "data-total-render-ms": f'{_number(profile.get("total_render_ms")):.3f}',
        "data-player-loader-ms": f'{_number(profile.get("player_loader_ms")):.3f}',
        "data-consumer-read-ms": f'{_number(profile.get("consumer_read_ms")):.3f}',
        "data-history-read-ms": f'{_number(profile.get("history_read_ms")):.3f}',
        "data-decision-card-ms": f'{_number(profile.get("decision_card_ms")):.3f}',
        "data-history-summary-ms": f'{_number(profile.get("history_summary_ms")):.3f}',
        "data-post-loader-render-ms": f'{_number(profile.get("post_loader_render_ms")):.3f}',
        "data-network-reads": str(int(_number(profile.get("network_reads")))),
        "data-consumer-session-hit": str(bool(profile.get("consumer_session_hit"))).lower(),
        "data-history-session-hit": str(bool(profile.get("history_session_hit"))).lower(),
        "data-cold-pair-loader": str(bool(profile.get("cold_pair_loader_used"))).lower(),
    }
    rendered = " ".join(f'{key}="{escape(value, quote=True)}"' for key, value in attrs.items())
    st.markdown(
        f'<span {rendered} style="display:none" aria-hidden="true"></span>',
        unsafe_allow_html=True,
    )


def render_profiled_step1_route(frozen_renderer: Callable[[], Any]) -> Any:
    """Profile only the Player Intelligence route while preserving frozen output."""
    state = navigation.current_state()
    _render_deployment_marker(state)
    if state.page != navigation.PAGE_PLAYER:
        return frozen_renderer()

    timings: dict[str, float] = {
        "player_loader_ms": 0.0,
        "consumer_read_ms": 0.0,
        "history_read_ms": 0.0,
        "decision_card_ms": 0.0,
        "history_summary_ms": 0.0,
    }
    calls: dict[str, int] = {}

    original_loader = performance.load_player_intelligence_same_session
    original_consumer = player_intelligence._read_consumer
    original_history = player_intelligence._read_history
    original_card = player_intelligence._exact_pra_card
    original_summary = player_intelligence._history_summary

    performance.load_player_intelligence_same_session = _timed(
        "player_loader_ms", original_loader, timings, calls
    )
    player_intelligence._read_consumer = _timed(
        "consumer_read_ms", original_consumer, timings, calls
    )
    player_intelligence._read_history = _timed(
        "history_read_ms", original_history, timings, calls
    )
    player_intelligence._exact_pra_card = _timed(
        "decision_card_ms", original_card, timings, calls
    )
    player_intelligence._history_summary = _timed(
        "history_summary_ms", original_summary, timings, calls
    )

    started = perf_counter()
    try:
        result = frozen_renderer()
    finally:
        total_render_ms = (perf_counter() - started) * 1000.0
        performance.load_player_intelligence_same_session = original_loader
        player_intelligence._read_consumer = original_consumer
        player_intelligence._read_history = original_history
        player_intelligence._exact_pra_card = original_card
        player_intelligence._history_summary = original_summary

    perf = st.session_state.get(performance.SESSION_PERF)
    perf = dict(perf) if isinstance(perf, dict) else {}
    step4_perf = st.session_state.get(player_intelligence.PERF_KEY)
    step4_perf = dict(step4_perf) if isinstance(step4_perf, dict) else {}

    direct_reads = int(_number(perf.get("direct_network_reads_this_call")))
    cold_pair = bool(perf.get("cold_pair_loader_used"))
    network_reads = 2 if cold_pair else direct_reads
    loader_ms = timings.get("player_loader_ms", 0.0)

    profile = {
        "model_version": MODEL_VERSION,
        "page": navigation.PAGE_PLAYER,
        "game_id": str(state.game_id or ""),
        "player_id": str(state.player_id or ""),
        "total_render_ms": round(total_render_ms, 3),
        "player_loader_ms": round(loader_ms, 3),
        "consumer_read_ms": round(timings.get("consumer_read_ms", 0.0), 3),
        "history_read_ms": round(timings.get("history_read_ms", 0.0), 3),
        "decision_card_ms": round(timings.get("decision_card_ms", 0.0), 3),
        "history_summary_ms": round(timings.get("history_summary_ms", 0.0), 3),
        "post_loader_render_ms": round(max(0.0, total_render_ms - loader_ms), 3),
        "consumer_read_calls": int(calls.get("consumer_read_ms", 0)),
        "history_read_calls": int(calls.get("history_read_ms", 0)),
        "decision_card_calls": int(calls.get("decision_card_ms", 0)),
        "history_summary_calls": int(calls.get("history_summary_ms", 0)),
        "network_reads": network_reads,
        "consumer_session_hit": bool(perf.get("consumer_session_hit")),
        "history_session_hit": bool(perf.get("history_session_hit")),
        "cold_pair_loader_used": cold_pair,
        "direct_network_reads_this_call": direct_reads,
        "frozen_step4_load_call_ms": round(_number(step4_perf.get("load_call_ms")), 3),
        "projection_runs_added": 0,
        "sportsbook_calls_added": 0,
        "monte_carlo_runs_added": 0,
    }
    st.session_state[SESSION_PROFILE] = profile
    _render_marker(profile)
    return result


__all__ = [
    "MODEL_VERSION",
    "PROFILER_CONTRACT",
    "SESSION_PROFILE",
    "render_profiled_step1_route",
]
