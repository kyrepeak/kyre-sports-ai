"""WNBA PRA Speed V3 Step 5 — history-only fast transport.

Exposes the frozen Step-3 ESPN player-history dataset without rebuilding or
rereading the global Step-18A consumer snapshot. Step 5 uses this route only
when the same Streamlit session already has the shared consumer snapshot and
the selected player history is missing.

No new history cache is added here; the frozen Step-3 history transport remains
authoritative. Step 6 owns any longer/smarter history-cache work.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from sports_api.api.wnba_pra_detail_bundle import DEFAULT_SEASON
from sports_api.wnba_pra_speed_v3_step3_espn_history import (
    get_step3_espn_player_game_log_dataset,
)

DATA_TYPE = "wnba_pra_speed_v3_step5_fast_history"
SCHEMA_VERSION = "wnba_pra_speed_v3_step5_fast_history_v1"

router = APIRouter(prefix="/api/v1/wnba", tags=["wnba-pra-speed-v3"])


def get_fast_pra_history(player_id: int, season: int = DEFAULT_SEASON) -> dict[str, Any]:
    pid = int(player_id)
    year = int(season)
    history = get_step3_espn_player_game_log_dataset(pid, year)
    return {
        "data_type": DATA_TYPE,
        "schema_version": SCHEMA_VERSION,
        "player_id": pid,
        "season": year,
        "history": history,
        "semantics": {
            "consumer_snapshot_read": False,
            "frozen_step3_history_transport_reused": True,
            "new_history_cache_added": False,
            "projection_run": False,
            "sportsbook_network_called": False,
            "qualification_run": False,
            "ranking_run": False,
            "monte_carlo_run": False,
            "wager_action_performed": False,
        },
    }


@router.get("/players/{player_id}/pra-history-fast")
def wnba_pra_speed_v3_step5_fast_history(
    player_id: int,
    season: int = Query(default=DEFAULT_SEASON, description="WNBA season"),
):
    return get_fast_pra_history(player_id, season)


__all__ = [
    "DATA_TYPE",
    "SCHEMA_VERSION",
    "get_fast_pra_history",
    "router",
]
