"""Read-only live certification for the isolated Step 7G WNBA.com page bridge."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path

from sports_api.wnba_step7g_first_party_history import (
    EXACT_ROTATION_SUPPORTED,
    WNBAStep7GFirstPartyNotFoundError,
    get_first_party_exact_rotation_dataset,
    get_first_party_game_box_score_dataset,
    get_first_party_play_by_play_dataset,
    get_first_party_player_recent_game_log_dataset,
)

GAME_ID = "1022600288"
PLAYER_ID = 1629498
SEASON = 2026
REPORT_PATH = Path("step7g-first-party-history-cert.json")
OFF_ENV = (
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_KYRE_DIRECT_SYNC_ENABLED",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
    "WNBA_STEP6J_CANARY_ENABLED",
    "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def main() -> None:
    off_state = {key: os.getenv(key, "").strip().casefold() == "false" for key in OFF_ENV}
    if not all(off_state.values()):
        raise RuntimeError("Step 7G certification refused because a production activation flag is not OFF.")

    box = get_first_party_game_box_score_dataset(GAME_ID, SEASON)
    history = get_first_party_player_recent_game_log_dataset(
        PLAYER_ID, SEASON, season_type="Regular Season"
    )
    pbp = get_first_party_play_by_play_dataset(GAME_ID, SEASON)

    rotation_fail_closed = False
    try:
        get_first_party_exact_rotation_dataset(GAME_ID, SEASON)
    except WNBAStep7GFirstPartyNotFoundError:
        rotation_fail_closed = True

    box_ok = (
        box["game_id"] == GAME_ID
        and box["player_count"] > 0
        and box["verification"]["normalized_with_frozen_step4d_box_contract"]
        and box["verification"]["player_ids_unique"]
    )
    history_ok = (
        history["player_id"] == PLAYER_ID
        and history["game_count"] > 0
        and history["verification"]["all_game_ids_valid"]
        and history["verification"]["all_game_ids_unique"]
        and history["verification"]["normalized_with_frozen_step4d_game_log_contract"]
        and not history["history_scope"]["full_season_history_guaranteed"]
    )
    pbp_ok = (
        pbp["game_id"] == GAME_ID
        and pbp["source_action_count"] > 0
        and pbp["verification"]["action_ids_unique_when_present"]
        and pbp["verification"]["normalized_with_frozen_step4k_action_contract"]
    )

    report = {
        "data_type": "wnba_step7g_first_party_history_certification",
        "created_at_utc": _now(),
        "read_only": True,
        "branch_scope": "wnba-step7g-official-data-preflight-20260827",
        "target_game_id": GAME_ID,
        "target_player_id": PLAYER_ID,
        "season": SEASON,
        "production_flags_off": off_state,
        "box_score": {
            "passed": box_ok,
            "player_count": box["player_count"],
            "home_team_key": box["home"]["team_key"],
            "away_team_key": box["away"]["team_key"],
            "contract_shape": box["contract_shape"],
        },
        "player_recent_history": {
            "passed": history_ok,
            "game_count": history["game_count"],
            "game_ids": [game["game_id"] for game in history["games"]],
            "contract_shape": history["contract_shape"],
            "recent_history_only": history["history_scope"]["recent_history_only"],
            "full_season_history_guaranteed": history["history_scope"]["full_season_history_guaranteed"],
        },
        "play_by_play": {
            "passed": pbp_ok,
            "source_action_count": pbp["source_action_count"],
            "substitution_action_count": sum(
                action["event_category"] == "substitution" for action in pbp["actions"]
            ),
            "contract_shape": pbp["contract_shape"],
        },
        "exact_rotation": {
            "supported": EXACT_ROTATION_SUPPORTED,
            "fail_closed_verified": rotation_fail_closed,
            "pbp_reconstruction_enabled": False,
        },
        "production_mutation_performed": False,
        "supabase_mutation_performed": False,
        "sportsbook_called": False,
        "scheduler_started": False,
        "frozen_shared_provider_behavior_changed": False,
        "production_activation_allowed": False,
        "next_required_step": "Find and certify an exact official rotation-stint source; recent player history is not claimed as full-season history.",
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if not (box_ok and history_ok and pbp_ok and rotation_fail_closed):
        raise RuntimeError("Step 7G first-party history certification did not pass all fail-closed checks.")

    print(json.dumps({
        "box_score_passed": box_ok,
        "recent_history_passed": history_ok,
        "play_by_play_passed": pbp_ok,
        "exact_rotation_fail_closed": rotation_fail_closed,
        "production_activation_allowed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
