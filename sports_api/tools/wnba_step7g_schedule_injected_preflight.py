"""Run the existing Step 7G official-data preflight with only the certified
first-party WNBA.com schedule source injected.

This is an OFF-only diagnostic wrapper. It deliberately does not modify the
frozen schedule provider or scheduler and does not inject any history/PBP/
rotation replacement. The purpose is to prove the schedule blocker is removed
and let the existing preflight expose the next real dependency failure.
"""
from __future__ import annotations

from typing import Any

from sports_api import wnba_schedule as frozen_schedule
from sports_api.tools import wnba_step7g_official_data_preflight as preflight
from sports_api.wnba_step7g_first_party_schedule import (
    _fetch_first_party_schedule_payload,
)


def _first_party_season_schedule_dataset(season: int) -> dict[str, Any]:
    """Build the season dataset with frozen Step-4C normalization semantics."""
    payload, retrieved_at_utc, source_variant, source_url, cache_hit = (
        _fetch_first_party_schedule_payload(season)
    )
    root = frozen_schedule._schedule_root(payload)

    games: list[dict[str, Any]] = []
    source_date_block_count = 0
    source_game_count = 0
    for block in root.get("gameDates", []):
        if not isinstance(block, dict):
            continue
        target_date = frozen_schedule._date_block_iso(block.get("gameDate"))
        if target_date is None:
            continue
        source_date_block_count += 1
        raw_games = block.get("games")
        if not isinstance(raw_games, list):
            continue
        valid_raw_games = [game for game in raw_games if isinstance(game, dict)]
        source_game_count += len(valid_raw_games)
        games.extend(
            frozen_schedule._normalize_game(game, target_date, season)
            for game in valid_raw_games
        )

    games.sort(
        key=lambda game: (
            game.get("official_schedule_date") or "",
            game.get("game_datetime_utc") or "",
            game.get("game_id") or "",
        )
    )

    return {
        "source": frozen_schedule.WNBA_SCHEDULE_SOURCE,
        "source_url": source_url,
        "source_variant": source_variant,
        "league_id": frozen_schedule.WNBA_LEAGUE_ID,
        "season": season,
        "retrieved_at_utc": retrieved_at_utc,
        "cache_hit": cache_hit,
        "source_date_block_count": source_date_block_count,
        "source_game_count": source_game_count,
        "game_count": len(games),
        "games": games,
    }


def main() -> int:
    # Inject only into this diagnostic module's local dependency reference.
    preflight._season_schedule_dataset = _first_party_season_schedule_dataset
    return preflight.main()


if __name__ == "__main__":
    raise SystemExit(main())
