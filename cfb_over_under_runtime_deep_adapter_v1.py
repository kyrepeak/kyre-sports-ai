"""Adapter that lets the frozen V13 deep-data slate consume runtime-reconciled profiles."""
from __future__ import annotations

from typing import Any, Mapping

import cfb_over_under_runtime_team_data_v1 as runtime_team_data

MODEL_VERSION = "CFB O/U RUNTIME DEEP ADAPTER V1"


def reconcile_matchup(
    game: Mapping[str, Any],
    as_of_day: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    game2, away, home, diag = runtime_team_data.reconcile_runtime(
        game,
        as_of_day,
    )
    return {
        "game": game2,
        "away": away,
        "home": home,
    }, diag


def clear_reconciliation_cache() -> None:
    runtime_team_data.clear_team_data_cache()


__all__ = [
    "MODEL_VERSION",
    "clear_reconciliation_cache",
    "reconcile_matchup",
]
