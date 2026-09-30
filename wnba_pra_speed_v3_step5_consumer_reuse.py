"""WNBA PRA Speed V3 Step 5 — cross-player consumer snapshot reuse."""
from __future__ import annotations

from html import escape
from time import perf_counter
from typing import Any, Mapping

import streamlit as st

import wnba_pra_navigation_v2_step1 as navigation
import wnba_pra_performance_v2_step5 as performance
import wnba_pra_player_intelligence_v2_step4 as player_intelligence
from wnba_api_client_v1 import KyreWNBAAPIClient, SUPPORTED_SEASON

MODEL_VERSION = "WNBA PRA SPEED V3 • STEP 5 CROSS-PLAYER CONSUMER REUSE"
EXPECTED_HISTORY_DATA_TYPE = "wnba_pra_speed_v3_step5_fast_history"
EXPECTED_HISTORY_SCHEMA_VERSION = "wnba_pra_speed_v3_step5_fast_history_v1"
API_TIMEOUT_SECONDS = 5.0
API_ATTEMPTS = 1
SESSION_PERF = "ks_wnba_pra_speed_v3_step5_perf"

REUSE_CONTRACT = {
    "project": "WNBA PRA Speed V3",
    "step": "5/9",
    "scope": "reuse_shared_consumer_snapshot_across_players",
    "warm_same_session_target_seconds_max": 0.75,
    "cached_cold_player_target_seconds_max": 1.5,
    "true_cold_pra_target_seconds_max": 2.5,
    "consumer_reads_on_cross_player_open_max": 0,
    "history_reads_on_cross_player_open_max": 1,
    "frozen_speed_v3_steps_1_4_modified": False,
    "new_history_cache_added": False,
    "projection_math_changed": False,
    "market_math_changed": False,
    "sportsbook_projection_influence": 0.0,
}


def _record(**values: Any) -> None:
    current = st.session_state.get(SESSION_PERF)
    current = dict(current) if isinstance(current, Mapping) else {}
    current.update(values)
    st.session_state[SESSION_PERF] = current
    performance._record(**values)


def _read_fast_history(player_id: int) -> dict[str, Any]:
    pid = int(player_id)
    client = KyreWNBAAPIClient(
        timeout_seconds=API_TIMEOUT_SECONDS,
        attempts=API_ATTEMPTS,
    )
    body = client.get_json(
        f"/api/v1/wnba/players/{pid}/pra-history-fast",
        params={"season": SUPPORTED_SEASON},
    )
    if body.get("data_type") != EXPECTED_HISTORY_DATA_TYPE:
        raise ValueError("Step-5 fast history data_type is invalid.")
    if body.get("schema_version") != EXPECTED_HISTORY_SCHEMA_VERSION:
        raise ValueError("Step-5 fast history schema_version is invalid.")
    if int(body.get("player_id") or 0) != pid:
        raise ValueError("Step-5 fast history player_id drifted.")
    if int(body.get("season") or 0) != int(SUPPORTED_SEASON):
        raise ValueError("Step-5 fast history season drifted.")
    history = body.get("history")
    if not isinstance(history, Mapping):
        raise ValueError("Step-5 fast history payload is missing history.")
    return dict(history)


def load_player_intelligence_cross_player_reuse(
    game_id: str,
    player_id: int,
) -> dict[str, Any]:
    """Preserve the global consumer snapshot while loading only new-player history."""
    pid = int(player_id)
    started = perf_counter()

    consumer = performance._cached_consumer()
    history = performance._cached_history(pid)
    consumer_hit = consumer is not None
    history_hit = history is not None
    consumer_error = ""
    history_error = ""
    cold_pair_used = False
    fast_history_used = False
    consumer_reads = 0
    history_reads = 0

    if consumer is None and history is None:
        cold_pair_used = True
        payload = performance._FROZEN_PLAYER_LOADER(str(game_id), pid)
        maybe_consumer = payload.get("consumer") if isinstance(payload, Mapping) else None
        maybe_history = payload.get("history") if isinstance(payload, Mapping) else None
        consumer_error = (
            str(payload.get("consumer_error") or "")
            if isinstance(payload, Mapping)
            else "InvalidPayload"
        )
        history_error = (
            str(payload.get("history_error") or "")
            if isinstance(payload, Mapping)
            else "InvalidPayload"
        )
        if isinstance(maybe_consumer, Mapping):
            consumer = dict(maybe_consumer)
            performance._cache_consumer(consumer)
        if isinstance(maybe_history, Mapping):
            history = dict(maybe_history)
            performance._cache_history(pid, history)
    else:
        if consumer is None:
            consumer_reads += 1
            try:
                consumer = player_intelligence._read_consumer()
                performance._cache_consumer(consumer)
            except Exception as exc:
                consumer_error = type(exc).__name__
                consumer = None

        if history is None:
            history_reads += 1
            fast_history_used = True
            try:
                history = _read_fast_history(pid)
                performance._cache_history(pid, history)
            except Exception as exc:
                history_error = type(exc).__name__
                history = None

    elapsed_ms = (perf_counter() - started) * 1000.0
    _record(
        player_id=pid,
        player_loader="speed_v3_step5_cross_player_consumer_reuse",
        consumer_session_hit=consumer_hit,
        history_session_hit=history_hit,
        consumer_network_reads_this_call=consumer_reads,
        history_network_reads_this_call=history_reads,
        direct_network_reads_this_call=consumer_reads + history_reads,
        cold_pair_loader_used=cold_pair_used,
        fast_history_used=fast_history_used,
        duplicate_consumer_read_suppressed=bool(consumer_hit and not history_hit),
        cross_player_load_ms=round(elapsed_ms, 3),
        consumer_present=isinstance(consumer, Mapping),
        history_present=isinstance(history, Mapping),
        consumer_error=consumer_error,
        history_error=history_error,
    )

    return {
        "game_id": str(game_id),
        "player_id": pid,
        "consumer": consumer,
        "history": history,
        "consumer_error": consumer_error,
        "history_error": history_error,
        "network_reads": (
            0
            if consumer_hit and history_hit
            else (consumer_reads + history_reads if not cold_pair_used else 1)
        ),
        "projection_runs": 0,
        "sportsbook_calls": 0,
        "qualification_runs": 0,
        "ranking_runs": 0,
        "monte_carlo_runs": 0,
        "reuse": {
            "consumer_session_hit": consumer_hit,
            "history_session_hit": history_hit,
            "cold_pair_loader_used": cold_pair_used,
            "fast_history_used": fast_history_used,
            "consumer_network_reads": consumer_reads,
            "history_network_reads": history_reads,
        },
    }


def _render_marker(state: navigation.NavigationState) -> None:
    perf = st.session_state.get(SESSION_PERF)
    perf = dict(perf) if isinstance(perf, Mapping) else {}
    st.markdown(
        '<span data-wnba-pra-speed-v3-step5="cross-player-consumer-reuse" '
        f'data-page="{escape(state.page, quote=True)}" '
        f'data-player-id="{int(perf.get("player_id") or 0)}" '
        f'data-consumer-session-hit="{str(bool(perf.get("consumer_session_hit"))).lower()}" '
        f'data-history-session-hit="{str(bool(perf.get("history_session_hit"))).lower()}" '
        f'data-consumer-network-reads="{int(perf.get("consumer_network_reads_this_call") or 0)}" '
        f'data-history-network-reads="{int(perf.get("history_network_reads_this_call") or 0)}" '
        f'data-direct-network-reads="{int(perf.get("direct_network_reads_this_call") or 0)}" '
        f'data-cold-pair-loader-used="{str(bool(perf.get("cold_pair_loader_used"))).lower()}" '
        f'data-fast-history-used="{str(bool(perf.get("fast_history_used"))).lower()}" '
        f'data-duplicate-consumer-read-suppressed="{str(bool(perf.get("duplicate_consumer_read_suppressed"))).lower()}" '
        f'data-consumer-present="{str(bool(perf.get("consumer_present"))).lower()}" '
        f'data-history-present="{str(bool(perf.get("history_present"))).lower()}" '
        f'data-cross-player-load-ms="{float(perf.get("cross_player_load_ms") or 0.0):.3f}" '
        'style="display:none" aria-hidden="true"></span>',
        unsafe_allow_html=True,
    )


def render_step5_route(frozen_renderer) -> Any:
    result = frozen_renderer()
    _render_marker(navigation.current_state())
    return result


__all__ = [
    "MODEL_VERSION",
    "REUSE_CONTRACT",
    "SESSION_PERF",
    "load_player_intelligence_cross_player_reuse",
    "render_step5_route",
]
