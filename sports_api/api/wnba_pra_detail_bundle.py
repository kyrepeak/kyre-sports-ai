"""WNBA PRA Speed V3 Step 3 — single-request Player PRA detail bundle.

The endpoint is read-only. It returns the exact Step-18A consumer snapshot and
a verified player game-log dataset as two isolated components inside one hosted
API response. The Step-3 history transport uses the repository-established ESPN
athlete-gamelog family because both direct WNBA Stats hosts are not latency-safe
on the live Render service. No projection, market, ranking, qualification, simulation,
sportsbook, or wager work is performed here.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

from fastapi import APIRouter, Query

from sports_api.wnba_pra_speed_v3_step3_espn_history import (
    get_step3_espn_player_game_log_dataset,
)
from sports_api.wnba_step18a_streamlit_consumer import build_step18a_consumer_latest


DATA_TYPE = "wnba_pra_speed_v3_step3_detail_bundle"
SCHEMA_VERSION = "wnba_pra_speed_v3_step3_detail_bundle_v1"
DEFAULT_SEASON = 2026

router = APIRouter(prefix="/api/v1/wnba", tags=["wnba-pra-speed-v3"])


def _result(future) -> tuple[dict[str, Any] | None, str]:
    try:
        value = future.result()
    except Exception as exc:
        return None, type(exc).__name__
    return (dict(value), "") if isinstance(value, dict) else (None, "InvalidPayload")


def build_pra_detail_bundle(player_id: int, season: int = DEFAULT_SEASON) -> dict[str, Any]:
    pid = int(player_id)
    year = int(season)
    if pid <= 0:
        raise ValueError("player_id must be positive.")
    if year < 1997 or year > 2100:
        raise ValueError("season is outside the supported WNBA range.")

    with ThreadPoolExecutor(max_workers=2) as pool:
        consumer_future = pool.submit(build_step18a_consumer_latest)
        history_future = pool.submit(
            get_step3_espn_player_game_log_dataset,
            pid,
            year,
        )
        consumer, consumer_error = _result(consumer_future)
        history, history_error = _result(history_future)

    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "player_id": pid,
        "season": year,
        "consumer": consumer,
        "history": history,
        "consumer_error": consumer_error,
        "history_error": history_error,
        "semantics": {
            "read_only_get": True,
            "streamlit_hosted_reads_required": 1,
            "consumer_source": "wnba_step18a_streamlit_consumer_latest",
            "history_source": "espn_wnba_athlete_gamelog",
            "consumer_payload_transformed_server_side": False,
            "history_payload_transformed_server_side": True,
            "projection_run": False,
            "sportsbook_network_called": False,
            "qualification_run": False,
            "ranking_run": False,
            "monte_carlo_run": False,
            "wager_action_performed": False,
        },
    }


@router.get("/players/{player_id}/pra-detail")
def wnba_pra_detail_bundle(
    player_id: int,
    season: int = Query(default=DEFAULT_SEASON, description="WNBA season"),
):
    return build_pra_detail_bundle(player_id, season)


__all__ = [
    "DATA_TYPE",
    "DEFAULT_SEASON",
    "SCHEMA_VERSION",
    "build_pra_detail_bundle",
    "router",
]
