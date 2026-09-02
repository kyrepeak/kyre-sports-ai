"""OFF-only certification for the Step 7G Step 4N schedule-context adapter."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Any

from sports_api.wnba_step7g_first_party_schedule_context import (
    get_step7g_step4n_season_schedule_dataset,
)

SEASON = 2026
REPORT_PATH = Path("step7g-step4n-schedule-context-cert.json")
EXPECTED_PRESEASON_ONE_SIDED_IDS = {
    "1012600011",
    "1012600012",
    "1012600013",
    "1012600014",
    "1012600017",
}
EXPECTED_BOTH_UNMAPPED_IDS = {"1032600001"}
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


def _ids(rows: Any) -> set[str]:
    if not isinstance(rows, list):
        return set()
    return {
        str(row.get("game_id"))
        for row in rows
        if isinstance(row, dict) and row.get("game_id") is not None
    }


def main() -> int:
    _assert_off()
    started = datetime.now(timezone.utc)
    dataset = get_step7g_step4n_season_schedule_dataset(SEASON)
    verification = dataset.get("verification") or {}
    preseason_rows = verification.get("excluded_explicit_preseason_one_sided_games") or []
    two_unmapped_rows = verification.get("excluded_two_unmapped_games") or []

    preseason_ids = _ids(preseason_rows)
    two_unmapped_ids = _ids(two_unmapped_rows)
    preseason_labels_exact = all(
        isinstance(row, dict)
        and str(row.get("game_label") or "").strip().casefold() == "preseason"
        for row in preseason_rows
    )
    preseason_rows_exactly_one_side_mapped = all(
        isinstance(row, dict)
        and (
            int(bool(row.get("away_mapped_to_registry")))
            + int(bool(row.get("home_mapped_to_registry")))
            == 1
        )
        for row in preseason_rows
    )
    two_unmapped_rows_really_two_unmapped = all(
        isinstance(row, dict)
        and not bool(row.get("away_mapped_to_registry"))
        and not bool(row.get("home_mapped_to_registry"))
        for row in two_unmapped_rows
    )

    games = dataset.get("games") or []
    included_ids = [
        str(game.get("game_id"))
        for game in games
        if isinstance(game, dict) and game.get("game_id") is not None
    ]
    included_all_valid = all(
        isinstance(game, dict)
        and bool((game.get("verification") or {}).get("game_id_valid"))
        for game in games
    )
    included_all_mapped = all(
        isinstance(game, dict)
        and bool((game.get("verification") or {}).get("teams_mapped_to_registry"))
        for game in games
    )
    included_all_distinct = all(
        isinstance(game, dict)
        and bool((game.get("verification") or {}).get("home_away_distinct"))
        for game in games
    )

    checks = {
        "source_normalized_game_count_is_350": verification.get("source_normalized_game_count") == 350,
        "included_franchise_game_count_is_344": dataset.get("game_count") == 344,
        "excluded_preseason_one_sided_ids_match_observed_2026_set": preseason_ids == EXPECTED_PRESEASON_ONE_SIDED_IDS,
        "excluded_preseason_rows_have_exact_preseason_label": preseason_labels_exact,
        "excluded_preseason_rows_have_exactly_one_mapped_side": preseason_rows_exactly_one_side_mapped,
        "excluded_two_unmapped_ids_match_observed_2026_set": two_unmapped_ids == EXPECTED_BOTH_UNMAPPED_IDS,
        "excluded_two_unmapped_rows_really_have_zero_mapped_sides": two_unmapped_rows_really_two_unmapped,
        "included_game_ids_unique": len(included_ids) == len(set(included_ids)),
        "included_game_ids_valid": included_all_valid,
        "included_teams_mapped": included_all_mapped,
        "included_home_away_distinct": included_all_distinct,
        "one_sided_exclusion_requires_exact_preseason_label": verification.get("one_sided_exclusion_requires_exact_preseason_label") is True,
        "unexpected_one_sided_still_fails_closed": verification.get("unexpected_one_sided_unmapped_still_fails_closed") is True,
        "daily_slate_semantics_unchanged": verification.get("daily_slate_semantics_changed") is False,
        "frozen_schedule_context_module_not_modified_by_adapter": verification.get("frozen_schedule_context_module_modified") is False,
        "production_provider_not_replaced": verification.get("production_provider_replaced") is False,
    }
    failed = [name for name, passed in checks.items() if not passed]

    report: dict[str, Any] = {
        "data_type": "wnba_step7g_step4n_schedule_context_cert_v1",
        "season": SEASON,
        "started_at_utc": started.isoformat(),
        "completed_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_url": dataset.get("source_url"),
        "source_variant": dataset.get("source_variant"),
        "upstream_source_variant": dataset.get("upstream_source_variant"),
        "game_count": dataset.get("game_count"),
        "verification": verification,
        "checks": checks,
        "failed_checks": failed,
        "certified": not failed,
        "observed_2026_scope_note": (
            "The five one-sided exclusions are certified only as the observed 2026 "
            "first-party schedule set at this run; no universal game-ID-prefix rule is inferred."
        ),
        "safety": {
            "production_runtime_enabled": False,
            "scheduler_started": False,
            "sportsbook_called": False,
            "supabase_mutation_performed": False,
            "persistence_performed": False,
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
            "Step 7G Step 4N schedule-context certification failed: "
            + ", ".join(failed)
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
