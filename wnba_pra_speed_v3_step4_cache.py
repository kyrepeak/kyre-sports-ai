"""WNBA PRA Speed V3 Step 4 — cached finished-bundle Streamlit loader."""
from __future__ import annotations

from html import escape
from time import perf_counter
from typing import Any, Mapping

import streamlit as st

import wnba_pra_navigation_v2_step1 as navigation
from wnba_api_client_v1 import KyreWNBAAPIClient, SUPPORTED_SEASON
from wnba_streamlit_consumer_v2 import normalize_consumer_payload


MODEL_VERSION = "WNBA PRA SPEED V3 • STEP 4 SERVER BUNDLE CACHE"
EXPECTED_DATA_TYPE = "wnba_pra_speed_v3_step4_cached_detail_bundle"
EXPECTED_SCHEMA_VERSION = "wnba_pra_speed_v3_step4_cached_detail_bundle_v1"
API_TIMEOUT_SECONDS = 5.0
API_ATTEMPTS = 1
SESSION_PERF = "ks_wnba_pra_speed_v3_step4_perf"

CACHE_CONTRACT = {
    "project": "WNBA PRA Speed V3",
    "step": "4/9",
    "scope": "server_side_finished_bundle_cache",
    "warm_same_session_target_seconds_max": 0.75,
    "cached_cold_player_target_seconds_max": 1.5,
    "true_cold_pra_target_seconds_max": 2.5,
    "streamlit_hosted_reads_per_cold_open": 1,
    "frozen_speed_v3_steps_1_3_modified": False,
    "projection_math_changed": False,
    "market_math_changed": False,
    "sportsbook_projection_influence": 0.0,
}


def _record(**values: Any) -> None:
    current = st.session_state.get(SESSION_PERF)
    current = dict(current) if isinstance(current, Mapping) else {}
    current.update(values)
    st.session_state[SESSION_PERF] = current


def _read_cached_bundle(player_id: int) -> dict[str, Any]:
    pid = int(player_id)
    client = KyreWNBAAPIClient(
        timeout_seconds=API_TIMEOUT_SECONDS,
        attempts=API_ATTEMPTS,
    )
    body = client.get_json(
        f"/api/v1/wnba/players/{pid}/pra-detail-cached",
        params={"season": SUPPORTED_SEASON},
    )
    if body.get("data_type") != EXPECTED_DATA_TYPE:
        raise ValueError("Step-4 cached PRA detail data_type is invalid.")
    if body.get("schema_version") != EXPECTED_SCHEMA_VERSION:
        raise ValueError("Step-4 cached PRA detail schema_version is invalid.")
    if int(body.get("player_id") or 0) != pid:
        raise ValueError("Step-4 cached PRA detail player_id drifted.")
    if int(body.get("season") or 0) != int(SUPPORTED_SEASON):
        raise ValueError("Step-4 cached PRA detail season drifted.")
    return body


def load_cached_bundle_pair(game_id: str, player_id: int) -> dict[str, Any]:
    """Return the frozen Step-3 pair through the Step-4 cached endpoint."""
    pid = int(player_id)
    started = perf_counter()
    consumer: dict[str, Any] | None = None
    history: dict[str, Any] | None = None
    consumer_error = ""
    history_error = ""
    bundle_error = ""
    cache_hit = False
    generation_ms = 0.0

    try:
        outer = _read_cached_bundle(pid)
    except Exception as exc:
        outer = {}
        bundle_error = type(exc).__name__
        consumer_error = bundle_error
        history_error = bundle_error

    cache_meta = outer.get("cache") if isinstance(outer, Mapping) else None
    if isinstance(cache_meta, Mapping):
        cache_hit = bool(cache_meta.get("hit"))
        try:
            generation_ms = float(cache_meta.get("generation_ms") or 0.0)
        except (TypeError, ValueError):
            generation_ms = 0.0

    body = outer.get("bundle") if isinstance(outer, Mapping) else None
    body = body if isinstance(body, Mapping) else {}

    raw_consumer = body.get("consumer")
    raw_history = body.get("history")
    if isinstance(body, Mapping):
        consumer_error = str(body.get("consumer_error") or consumer_error)
        history_error = str(body.get("history_error") or history_error)

    if not consumer_error and isinstance(raw_consumer, Mapping):
        try:
            consumer = normalize_consumer_payload(dict(raw_consumer))
        except Exception as exc:
            consumer_error = type(exc).__name__

    if not history_error and isinstance(raw_history, Mapping):
        history = dict(raw_history)

    elapsed_ms = (perf_counter() - started) * 1000.0
    _record(
        cached_bundle_used=True,
        server_cache_hit=cache_hit,
        cached_bundle_read_ms=round(elapsed_ms, 3),
        server_generation_ms=round(generation_ms, 3),
        streamlit_network_reads=1,
        consumer_present=isinstance(consumer, Mapping),
        history_present=isinstance(history, Mapping),
        consumer_error=consumer_error,
        history_error=history_error,
        bundle_error=bundle_error,
        player_id=pid,
    )

    return {
        "game_id": str(game_id),
        "player_id": pid,
        "consumer": consumer,
        "history": history,
        "consumer_error": consumer_error,
        "history_error": history_error,
        "network_reads": 1,
        "projection_runs": 0,
        "sportsbook_calls": 0,
        "qualification_runs": 0,
        "ranking_runs": 0,
        "monte_carlo_runs": 0,
        "step4_server_cache_hit": cache_hit,
    }


def _render_marker(state: navigation.NavigationState) -> None:
    perf = st.session_state.get(SESSION_PERF)
    perf = dict(perf) if isinstance(perf, Mapping) else {}
    st.markdown(
        '<span data-wnba-pra-speed-v3-step4="server-bundle-cache" '
        f'data-page="{escape(state.page, quote=True)}" '
        f'data-cache-used="{str(bool(perf.get("cached_bundle_used"))).lower()}" '
        f'data-server-cache-hit="{str(bool(perf.get("server_cache_hit"))).lower()}" '
        f'data-streamlit-network-reads="{int(perf.get("streamlit_network_reads") or 0)}" '
        f'data-cached-bundle-read-ms="{float(perf.get("cached_bundle_read_ms") or 0.0):.3f}" '
        f'data-server-generation-ms="{float(perf.get("server_generation_ms") or 0.0):.3f}" '
        f'data-consumer-present="{str(bool(perf.get("consumer_present"))).lower()}" '
        f'data-history-present="{str(bool(perf.get("history_present"))).lower()}" '
        f'data-consumer-error="{escape(str(perf.get("consumer_error") or ""), quote=True)}" '
        f'data-history-error="{escape(str(perf.get("history_error") or ""), quote=True)}" '
        'style="display:none" aria-hidden="true"></span>',
        unsafe_allow_html=True,
    )


def render_step4_route(frozen_renderer) -> Any:
    result = frozen_renderer()
    _render_marker(navigation.current_state())
    return result


__all__ = [
    "CACHE_CONTRACT",
    "EXPECTED_DATA_TYPE",
    "EXPECTED_SCHEMA_VERSION",
    "MODEL_VERSION",
    "SESSION_PERF",
    "load_cached_bundle_pair",
    "render_step4_route",
]
