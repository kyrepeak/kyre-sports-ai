"""OFF-only live certification for the Step 7G Step 4J team-history adapter."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

from sports_api.wnba_step7g_first_party_team_history import (
    get_first_party_team_game_log_dataset,
)

SEASON = 2026
TEAM_KEY = "toronto-tempo"
SEASON_TYPE = "Regular Season"
REPORT_PATH = Path("step7g-step4j-team-history-cert.json")
OFF_KEYS = (
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_KYRE_DIRECT_SYNC_ENABLED",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
    "WNBA_STEP6J_CANARY_ENABLED",
    "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED",
)


def _assert_off() -> None:
    enabled = [
        key
        for key in OFF_KEYS
        if str(os.getenv(key, "false")).strip().casefold()
        not in {"", "0", "false", "no", "off"}
    ]
    if enabled:
        raise RuntimeError("Production switch enabled: " + ", ".join(enabled))


def _numeric(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def main() -> int:
    _assert_off()
    started = datetime.now(timezone.utc)
    dataset = get_first_party_team_game_log_dataset(
        TEAM_KEY,
        SEASON,
        season_type=SEASON_TYPE,
    )
    games = dataset.get("games") or []
    verification = dataset.get("verification") or {}
    adapter = dataset.get("step7g_adapter") or {}

    game_ids = [str(game.get("game_id")) for game in games if isinstance(game, dict)]
    dates = [game.get("game_date") for game in games if isinstance(game, dict)]
    minutes = [game.get("minutes") for game in games if isinstance(game, dict)]

    checks = {
        "team_history_nonempty": len(games) > 0,
        "game_count_matches_season_team_game_count": (
            dataset.get("game_count") == dataset.get("season_team_game_count")
        ),
        "all_rows_are_requested_team": all(
            isinstance(game, dict) and game.get("team_key") == TEAM_KEY for game in games
        ),
        "all_rows_are_paired": all(
            isinstance(game, dict) and game.get("paired_opponent_row") is True
            for game in games
        ),
        "all_opponents_are_distinct": all(
            isinstance(game, dict)
            and game.get("opponent_team_key")
            and game.get("opponent_team_key") != TEAM_KEY
            for game in games
        ),
        "all_game_ids_match_certified_2026_regular_family": all(
            game_id.startswith("10226") and len(game_id) == 10 and game_id.isdigit()
            for game_id in game_ids
        ),
        "all_game_ids_unique": len(game_ids) == len(set(game_ids)),
        "all_game_dates_present": bool(dates) and all(bool(value) for value in dates),
        "all_team_minutes_numeric_positive": bool(minutes)
        and all(_numeric(value) and float(value) > 0.0 for value in minutes),
        "all_opponent_points_numeric": all(
            _numeric(game.get("opponent_points")) for game in games if isinstance(game, dict)
        ),
        "frozen_schema_verified": verification.get("schema_verified") is True,
        "frozen_row_normalizer_reused": (
            verification.get("normalized_with_frozen_step4j_row_contract") is True
        ),
        "frozen_pairing_semantics_reused": (
            verification.get("paired_with_frozen_step4j_pairing_semantics") is True
        ),
        "frozen_filter_summary_semantics_reused": (
            verification.get("filtered_and_summarized_with_frozen_step4j_semantics") is True
        ),
        "all_rows_mapped": verification.get("all_rows_mapped_to_registry") is True,
        "all_game_ids_valid": verification.get("all_game_ids_valid") is True,
        "all_game_ids_have_two_team_rows": (
            verification.get("all_game_ids_have_two_team_rows") is True
        ),
        "opponent_identity_matches_pair": (
            verification.get("opponent_identity_matches_pair") is True
        ),
        "schedule_box_identity_match": verification.get("schedule_box_identity_match") is True,
        "schedule_box_score_match": verification.get("schedule_box_score_match") is True,
        "source_box_count_matches_selected_schedule_games": (
            verification.get("source_box_score_count_matches_selected_games") is True
        ),
        "source_box_count_matches_team_history_count": (
            adapter.get("source_box_score_count") == dataset.get("season_team_game_count")
        ),
        "frozen_team_history_source_file_not_modified_by_adapter": (
            verification.get("frozen_team_history_module_modified") is False
        ),
        "production_provider_not_replaced": (
            verification.get("production_provider_replaced") is False
            and adapter.get("production_provider_replaced") is False
        ),
    }
    failed = [name for name, passed in checks.items() if not passed]

    report = {
        "data_type": "wnba_step7g_step4j_first_party_team_history_cert_v1",
        "season": SEASON,
        "season_type": SEASON_TYPE,
        "team_key": TEAM_KEY,
        "started_at_utc": started.isoformat(),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": dataset.get("source"),
        "source_url": dataset.get("source_url"),
        "source_endpoint": dataset.get("source_endpoint"),
        "game_count": dataset.get("game_count"),
        "first_game_date": min(dates) if dates else None,
        "most_recent_game_date": max(dates) if dates else None,
        "game_ids": game_ids,
        "team_minutes": minutes,
        "summary": dataset.get("summary"),
        "verification": verification,
        "adapter": adapter,
        "checks": checks,
        "failed_checks": failed,
        "certified": not failed,
        "scope_note": (
            "The 10226xxxxx Regular Season game-ID family is certified only for the "
            "observed 2026 WNBA schedule and is not generalized to future seasons."
        ),
        "safety": {
            "production_runtime_enabled": False,
            "scheduler_started": False,
            "sportsbook_called": False,
            "supabase_mutation_performed": False,
            "persistence_performed": False,
            "production_activation_allowed": False,
        },
    }
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    _assert_off()
    if failed:
        raise RuntimeError(
            "Step 7G Step 4J team-history certification failed: " + ", ".join(failed)
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
