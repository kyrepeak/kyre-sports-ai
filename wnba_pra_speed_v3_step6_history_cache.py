"""WNBA PRA Speed V3 Step 6 — Streamlit cached-history reader."""
from __future__ import annotations

from html import escape
from time import perf_counter
from typing import Any, Mapping

import streamlit as st

import wnba_pra_navigation_v2_step1 as navigation
from wnba_api_client_v1 import KyreWNBAAPIClient, SUPPORTED_SEASON

MODEL_VERSION = "WNBA PRA SPEED V3 • STEP 6 SMART HISTORY CACHE"
EXPECTED_DATA_TYPE = "wnba_pra_speed_v3_step6_history_cache"
EXPECTED_SCHEMA_VERSION = "wnba_pra_speed_v3_step6_history_cache_v1"

API_TIMEOUT_SECONDS = 5.0
API_ATTEMPTS = 1
SESSION_PERF = "ks_wnba_pra_speed_v3_step6_perf"

HISTORY_CACHE_CONTRACT = {
    "project": "WNBA PRA Speed V3",
    "step": "6/9",
    "scope": "smarter_longer_player_history_cache",
    "active_season_ttl_seconds": 600,
    "historical_season_ttl_seconds": 21600,
    "cache_key": ["player_id", "season"],
    "cache_max_entries": 512,
    "warm_same_session_target_seconds_max": 0.75,
    "cached_cold_player_target_seconds_max": 1.5,
    "true_cold_pra_target_seconds_max": 2.5,
    "frozen_speed_v3_steps_1_5_modified": False,
    "projection_math_changed": False,
    "market_math_changed": False,
    "sportsbook_projection_influence": 0.0,
}


def _record(**values: Any) -> None:
    current = st.session_state.get(SESSION_PERF)
    current = dict(current) if isinstance(current, Mapping) else {}
    current.update(values)
    st.session_state[SESSION_PERF] = current


def read_cached_history(player_id: int) -> dict[str, Any]:
    """Read only the selected player's history through the Step-6 cache."""
    pid = int(player_id)
    started = perf_counter()
    client = KyreWNBAAPIClient(
        timeout_seconds=API_TIMEOUT_SECONDS,
        attempts=API_ATTEMPTS,
    )
    body = client.get_json(
        f"/api/v1/wnba/players/{pid}/pra-history-cached",
        params={"season": SUPPORTED_SEASON},
    )
    elapsed_ms = (perf_counter() - started) * 1000.0

    if body.get("data_type") != EXPECTED_DATA_TYPE:
        raise ValueError("Step-6 cached history data_type is invalid.")
    if body.get("schema_version") != EXPECTED_SCHEMA_VERSION:
        raise ValueError("Step-6 cached history schema_version is invalid.")
    if int(body.get("player_id") or 0) != pid:
        raise ValueError("Step-6 cached history player_id drifted.")
    if int(body.get("season") or 0) != int(SUPPORTED_SEASON):
        raise ValueError("Step-6 cached history season drifted.")

    history = body.get("history")
    if not isinstance(history, Mapping):
        raise ValueError("Step-6 cached history payload is missing history.")

    cache = body.get("cache")
    cache = dict(cache) if isinstance(cache, Mapping) else {}
    hit = bool(cache.get("hit"))
    ttl_seconds = int(cache.get("ttl_seconds") or 0)
    age_ms = float(cache.get("age_ms") or 0.0)
    generation_ms = float(cache.get("generation_ms") or 0.0)

    _record(
        player_id=pid,
        history_cache_route_used=True,
        server_history_cache_hit=hit,
        server_history_cache_ttl_seconds=ttl_seconds,
        server_history_cache_age_ms=round(age_ms, 3),
        server_history_generation_ms=round(generation_ms, 3),
        cached_history_read_ms=round(elapsed_ms, 3),
        history_present=True,
    )
    return dict(history)


def _render_marker(state: navigation.NavigationState) -> None:
    perf = st.session_state.get(SESSION_PERF)
    perf = dict(perf) if isinstance(perf, Mapping) else {}
    st.markdown(
        '<span data-wnba-pra-speed-v3-step6="history-cache" '
        f'data-page="{escape(state.page, quote=True)}" '
        f'data-player-id="{int(perf.get("player_id") or 0)}" '
        f'data-history-cache-route-used="{str(bool(perf.get("history_cache_route_used"))).lower()}" '
        f'data-server-history-cache-hit="{str(bool(perf.get("server_history_cache_hit"))).lower()}" '
        f'data-server-history-cache-ttl-seconds="{int(perf.get("server_history_cache_ttl_seconds") or 0)}" '
        f'data-server-history-cache-age-ms="{float(perf.get("server_history_cache_age_ms") or 0.0):.3f}" '
        f'data-server-history-generation-ms="{float(perf.get("server_history_generation_ms") or 0.0):.3f}" '
        f'data-cached-history-read-ms="{float(perf.get("cached_history_read_ms") or 0.0):.3f}" '
        f'data-history-present="{str(bool(perf.get("history_present"))).lower()}" '
        'style="display:none" aria-hidden="true"></span>',
        unsafe_allow_html=True,
    )


def render_step6_route(frozen_renderer) -> Any:
    result = frozen_renderer()
    _render_marker(navigation.current_state())
    return result


__all__ = [
    "EXPECTED_DATA_TYPE",
    "EXPECTED_SCHEMA_VERSION",
    "HISTORY_CACHE_CONTRACT",
    "MODEL_VERSION",
    "SESSION_PERF",
    "read_cached_history",
    "render_step6_route",
]
