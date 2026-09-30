"""WNBA PRA Speed V3 — Step 3 single-request cold-pair loader."""
from __future__ import annotations

from html import escape
from time import perf_counter
from typing import Any, Callable, Mapping

import streamlit as st

import wnba_pra_navigation_v2_step1 as navigation
from wnba_api_client_v1 import KyreWNBAAPIClient, SUPPORTED_SEASON
from wnba_streamlit_consumer_v2 import normalize_consumer_payload


MODEL_VERSION = "WNBA PRA SPEED V3 • STEP 3 SINGLE-REQUEST DETAIL BUNDLE"
EXPECTED_DATA_TYPE = "wnba_pra_speed_v3_step3_detail_bundle"
EXPECTED_SCHEMA_VERSION = "wnba_pra_speed_v3_step3_detail_bundle_v1"
API_TIMEOUT_SECONDS = 5.0
API_ATTEMPTS = 1
SESSION_PERF = "ks_wnba_pra_speed_v3_step3_perf"

BUNDLE_CONTRACT = {
    "project": "WNBA PRA Speed V3",
    "step": "3/9",
    "scope": "single_request_cold_pair_only",
    "cold_pair_streamlit_api_reads": 1,
    "consumer_normalization_changed": False,
    "history_payload_changed": False,
    "session_cache_behavior_changed": False,
    "projection_runs_added": 0,
    "sportsbook_calls_added": 0,
    "qualification_runs_added": 0,
    "ranking_runs_added": 0,
    "monte_carlo_runs_added": 0,
    "projection_math_changed": False,
    "market_math_changed": False,
    "sportsbook_projection_influence": 0.0,
    "frozen_navigation_steps_1_through_7_modified": False,
    "frozen_speed_v3_steps_1_2_modified": False,
}


def _record(**values: Any) -> None:
    current = st.session_state.get(SESSION_PERF)
    current = dict(current) if isinstance(current, Mapping) else {}
    current.update(values)
    st.session_state[SESSION_PERF] = current


def _read_bundle(player_id: int) -> dict[str, Any]:
    pid = int(player_id)
    client = KyreWNBAAPIClient(
        timeout_seconds=API_TIMEOUT_SECONDS,
        attempts=API_ATTEMPTS,
    )
    body = client.get_json(
        f"/api/v1/wnba/players/{pid}/pra-detail",
        params={"season": SUPPORTED_SEASON},
    )
    if body.get("data_type") != EXPECTED_DATA_TYPE:
        raise ValueError("Step-3 PRA detail bundle data_type is invalid.")
    if body.get("schema_version") != EXPECTED_SCHEMA_VERSION:
        raise ValueError("Step-3 PRA detail bundle schema_version is invalid.")
    if int(body.get("player_id") or 0) != pid:
        raise ValueError("Step-3 PRA detail bundle player_id drifted.")
    if int(body.get("season") or 0) != int(SUPPORTED_SEASON):
        raise ValueError("Step-3 PRA detail bundle season drifted.")
    return body


def load_bundle_pair(game_id: str, player_id: int) -> dict[str, Any]:
    """Return the same Step-4 pair through one hosted read."""
    pid = int(player_id)
    started = perf_counter()
    consumer: dict[str, Any] | None = None
    history: dict[str, Any] | None = None
    consumer_error = ""
    history_error = ""
    bundle_error = ""

    try:
        body = _read_bundle(pid)
    except Exception as exc:
        body = {}
        bundle_error = type(exc).__name__
        consumer_error = bundle_error
        history_error = bundle_error

    raw_consumer = body.get("consumer") if isinstance(body, Mapping) else None
    raw_history = body.get("history") if isinstance(body, Mapping) else None
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
        bundle_used=True,
        bundle_read_ms=round(elapsed_ms, 3),
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
    }


def _render_marker(state: navigation.NavigationState) -> None:
    perf = st.session_state.get(SESSION_PERF)
    perf = dict(perf) if isinstance(perf, Mapping) else {}
    st.markdown(
        '<span data-wnba-pra-speed-v3-step3="detail-bundle" '
        f'data-wnba-pra-speed-v3-step3-page="{escape(state.page, quote=True)}" '
        f'data-bundle-used="{str(bool(perf.get("bundle_used"))).lower()}" '
        f'data-streamlit-network-reads="{int(perf.get("streamlit_network_reads") or 0)}" '
        f'data-bundle-read-ms="{float(perf.get("bundle_read_ms") or 0.0):.3f}" '
        f'data-consumer-present="{str(bool(perf.get("consumer_present"))).lower()}" '
        f'data-history-present="{str(bool(perf.get("history_present"))).lower()}" '
        f'data-consumer-error="{escape(str(perf.get("consumer_error") or ""), quote=True)}" '
        f'data-history-error="{escape(str(perf.get("history_error") or ""), quote=True)}" '
        'style="display:none" aria-hidden="true"></span>',
        unsafe_allow_html=True,
    )


def render_step3_route(frozen_renderer: Callable[[], Any]) -> Any:
    result = frozen_renderer()
    _render_marker(navigation.current_state())
    return result


__all__ = [
    "BUNDLE_CONTRACT",
    "EXPECTED_DATA_TYPE",
    "EXPECTED_SCHEMA_VERSION",
    "MODEL_VERSION",
    "SESSION_PERF",
    "load_bundle_pair",
    "render_step3_route",
]
