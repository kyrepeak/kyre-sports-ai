"""OFF-only live certification for the exact 2026 Commissioner's Cup exclusion."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

from sports_api.wnba_step7g_first_party_schedule_context import (
    get_step7g_step4n_season_schedule_dataset,
)
from sports_api.wnba_step7g_first_party_team_history_cup_safe import (
    CERTIFIED_NON_REGULAR_GAME_IDS_BY_SEASON,
    get_first_party_team_game_log_dataset,
    install_exact_cup_exclusion,
)

SEASON = 2026
CUP_GAME_ID = "1052600001"
TARGET_TEAM_KEY = "new-york-liberty"
REPORT_PATH = Path("step7g-step4j-cup-exclusion-cert.json")
_OFF_ENV_KEYS = (
    "WNBA_PRODUCTION_RUNTIME_ENABLED",
    "WNBA_BOARD_SCHEDULER_ENABLED",
    "WNBA_KYRE_DIRECT_SYNC_ENABLED",
    "WNBA_KYRE_RECONCILED_SYNC_ENABLED",
    "WNBA_STEP6J_CANARY_ENABLED",
    "WNBA_STEP6L_PRODUCTION_REFRESH_ENABLED",
)


def _assert_off() -> None:
    bad = {
        key: os.getenv(key)
        for key in _OFF_ENV_KEYS
        if str(os.getenv(key, "false")).strip().casefold()
        not in {"", "0", "false", "no", "off"}
    }
    if bad:
        raise RuntimeError(
            "Cup exclusion certification refuses to run while a production switch is enabled: "
            + ", ".join(sorted(bad))
        )


def _team_keys(game: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    for side in ("away", "home"):
        row = game.get(side)
        if isinstance(row, dict) and row.get("team_key"):
            result.add(str(row["team_key"]))
    return result


def main() -> int:
    _assert_off()
    started = datetime.now(timezone.utc)
    install_exact_cup_exclusion()

    schedule = get_step7g_step4n_season_schedule_dataset(SEASON)
    schedule_games = schedule.get("games")
    if not isinstance(schedule_games, list):
        raise RuntimeError("Certified Step 4N schedule returned no games list.")

    cup_matches = [
        game
        for game in schedule_games
        if isinstance(game, dict) and str(game.get("game_id") or "") == CUP_GAME_ID
    ]
    if len(cup_matches) != 1:
        raise RuntimeError(
            f"Expected exactly one official schedule row for Cup game {CUP_GAME_ID}; found {len(cup_matches)}."
        )
    cup_game = cup_matches[0]
    cup_team_keys = _team_keys(cup_game)
    if TARGET_TEAM_KEY not in cup_team_keys:
        raise RuntimeError(
            f"Cup game {CUP_GAME_ID} does not contain expected certification team {TARGET_TEAM_KEY}."
        )

    dataset = get_first_party_team_game_log_dataset(
        TARGET_TEAM_KEY,
        SEASON,
        season_type="Regular Season",
    )
    games = dataset.get("games")
    if not isinstance(games, list):
        raise RuntimeError("Cup-safe Step 4J dataset returned no games list.")
    ids = [str(game.get("game_id") or "") for game in games if isinstance(game, dict)]
    verification = dataset.get("verification") or {}

    checks = {
        "exact_game_id_is_certified_non_regular": CUP_GAME_ID
        in CERTIFIED_NON_REGULAR_GAME_IDS_BY_SEASON.get(SEASON, frozenset()),
        "official_schedule_contains_exact_cup_game": len(cup_matches) == 1,
        "cup_game_contains_target_team": TARGET_TEAM_KEY in cup_team_keys,
        "cup_game_excluded_from_regular_history": CUP_GAME_ID not in ids,
        "all_admitted_regular_ids_use_certified_family": all(
            game_id.startswith("10226") for game_id in ids
        ),
        "all_rows_mapped": verification.get("all_rows_mapped_to_registry") is True,
        "all_opponents_resolved": verification.get("all_opponent_team_keys_resolved") is True,
        "schedule_box_identity_match": verification.get("schedule_box_identity_match") is True,
        "schedule_box_score_match": verification.get("schedule_box_score_match") is True,
    }
    failed = [name for name, passed in checks.items() if not passed]
    report = {
        "data_type": "wnba_step7g_step4j_exact_cup_exclusion_cert_v1",
        "started_at_utc": started.isoformat(),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "season": SEASON,
        "cup_game_id": CUP_GAME_ID,
        "cup_schedule_status": (cup_game.get("status") or {}).get("category"),
        "cup_schedule_label": (cup_game.get("competition") or {}).get("game_label"),
        "cup_team_keys": sorted(cup_team_keys),
        "target_team_key": TARGET_TEAM_KEY,
        "regular_history_game_count": dataset.get("game_count"),
        "checks": checks,
        "failed_checks": failed,
        "certified": not failed,
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
        raise RuntimeError("Exact Cup exclusion certification failed: " + ", ".join(failed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
