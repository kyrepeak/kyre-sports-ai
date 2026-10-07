"""WNBA PRA history runtime fallback for the shared hosted API.

Keeps the certified multi-source history adapter authoritative. Only when both
of its providers are unavailable at runtime does this layer fall through to the
repository's existing official WNBA Stats player-game-log client. This is a
read-only history transport and never changes model/projection/market logic.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from sports_api.wnba_game_history import (
    WNBA_CURRENT_STATS_BASE_URL,
    get_player_game_log_dataset,
)
from sports_api.wnba_pra_history_multisource_v1 import (
    get_multisource_player_game_log_dataset,
)


def get_runtime_player_game_log_dataset(player_id: int, season: int) -> dict[str, Any]:
    pid = int(player_id)
    year = int(season)
    primary_error = ""
    try:
        return get_multisource_player_game_log_dataset(pid, year)
    except Exception as exc:
        primary_error = type(exc).__name__

    try:
        official = get_player_game_log_dataset(
            pid,
            year,
            stats_base_url=WNBA_CURRENT_STATS_BASE_URL,
        )
    except Exception as exc:
        raise RuntimeError(
            "WNBA_HISTORY_ALL_CREDIBLE_PROVIDERS_UNAVAILABLE:"
            f"primary={primary_error or 'unknown'}:official_stats={type(exc).__name__}"
        ) from exc

    result = deepcopy(dict(official))
    verification = result.get("verification")
    verification = dict(verification) if isinstance(verification, Mapping) else {}
    verification.update(
        {
            "provider_policy": "multi_source",
            "runtime_fallback": "official_wnba_stats_api",
            "primary_multisource_error": primary_error,
            "official_wnba_stats_available": True,
            "credible_provider_count_available": 1,
            "stats_are_observed_not_projected": True,
        }
    )
    result["verification"] = verification
    result["history_sources"] = ["WNBA Stats API"]
    return result


__all__ = ["get_runtime_player_game_log_dataset"]
