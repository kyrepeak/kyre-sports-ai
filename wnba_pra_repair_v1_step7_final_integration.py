"""WNBA PRA Repair V1 — Step 7 final integration guard.

Pure fail-closed integration layer. It composes the frozen Step-6 completeness
audits and never fetches data, renders UI, or changes projection, market,
probability, qualification, ranking, or sportsbook behavior.
"""
from __future__ import annotations

from typing import Any, Mapping

import wnba_pra_repair_v1_step6_completeness_sweep as step6

MODEL_VERSION = "WNBA PRA REPAIR V1 • STEP 7 FINAL INTEGRATION"
MAY_MODIFY_WNBA_MODEL = False
MAY_MODIFY_PROJECTION_MATH = False
MAY_MODIFY_MARKET_MATH = False
MAY_MODIFY_PROBABILITY = False
MAY_MODIFY_QUALIFICATION = False
MAY_MODIFY_RANKING = False
MAY_MODIFY_OTHER_SPORTS = False
SPORTSBOOK_PROJECTION_INFLUENCE = 0.0
NETWORK_CALLS = False


def audit_game_context(
    game: Mapping[str, Any] | None,
    players: list[Mapping[str, Any]] | tuple[Mapping[str, Any], ...] | None,
) -> dict[str, Any]:
    game_result = step6.audit_game(game)
    rows = list(players or [])
    player_results = [step6.audit_player(player, game) for player in rows]

    away_id = game_result.get("away_team_id")
    home_id = game_result.get("home_team_id")
    team_counts = {
        int(team_id): 0
        for team_id in (away_id, home_id)
        if isinstance(team_id, int)
    }
    player_ids: list[int] = []
    for result in player_results:
        team_id = result.get("team_id")
        player_id = result.get("player_id")
        if isinstance(team_id, int) and team_id in team_counts:
            team_counts[team_id] += 1
        if isinstance(player_id, int):
            player_ids.append(player_id)

    duplicate_ids = tuple(sorted({pid for pid in player_ids if player_ids.count(pid) > 1}))
    players_ready = sum(1 for result in player_results if result["ready"])
    both_teams_present = len(team_counts) == 2 and all(count > 0 for count in team_counts.values())
    ready = (
        bool(game_result["ready"])
        and bool(rows)
        and players_ready == len(rows)
        and not duplicate_ids
        and both_teams_present
    )
    return {
        "ready": ready,
        "game": game_result,
        "players_seen": len(rows),
        "players_ready": players_ready,
        "team_player_counts": team_counts,
        "duplicate_player_ids": duplicate_ids,
        "incomplete_player_ids": tuple(
            sorted(
                int(result["player_id"])
                for result in player_results
                if not result["ready"] and isinstance(result.get("player_id"), int)
            )
        ),
    }


def audit_selected_player(
    player: Mapping[str, Any] | None,
    game: Mapping[str, Any] | None,
) -> dict[str, Any]:
    return step6.audit_player(player, game)


def audit_final_card(card: Mapping[str, Any] | None) -> dict[str, Any]:
    return step6.audit_card(card)


__all__ = [
    "MODEL_VERSION",
    "MAY_MODIFY_WNBA_MODEL",
    "MAY_MODIFY_PROJECTION_MATH",
    "MAY_MODIFY_MARKET_MATH",
    "MAY_MODIFY_PROBABILITY",
    "MAY_MODIFY_QUALIFICATION",
    "MAY_MODIFY_RANKING",
    "MAY_MODIFY_OTHER_SPORTS",
    "SPORTSBOOK_PROJECTION_INFLUENCE",
    "NETWORK_CALLS",
    "audit_final_card",
    "audit_game_context",
    "audit_selected_player",
]
