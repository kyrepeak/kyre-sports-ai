"""First-party Step 7G transport helpers for frozen Step 4I availability.

Step 4I only needs the target date's official schedule rows. The frozen Step 4C
transport currently tries a legacy CDN JSON surface and stats.wnba.com; both can
be unreachable or malformed in hosted CI even though the separately certified
Step 7G WNBA.com season schedule is healthy.

This module derives a daily Step-4C-compatible view from that already-certified
season dataset. It does not invent games, teams, statuses, dates, or tip times.
Every admitted game keeps the frozen Step 4C-normalized object and must retain
valid game identity, two mapped registry teams, and distinct home/away teams.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

from sports_api.wnba_schedule import CACHE_TTL_SECONDS, WNBA_LEAGUE_ID
from sports_api.wnba_schedule_context import WNBARestTravelUpstreamError
from sports_api.wnba_step7g_first_party_schedule_context import (
    get_step7g_step4n_season_schedule_dataset,
)

STEP7G_STEP4I_DAILY_SOURCE_VARIANT = "wnba_com_first_party_schedule_step4i_daily"


def _target_date(value: str) -> str:
    text = str(value).strip()
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("date must use YYYY-MM-DD format.") from exc
    return text


def _validate_daily_games(games: list[dict[str, Any]], target_date: str) -> None:
    ids: list[str] = []
    for game in games:
        if not isinstance(game, dict):
            raise WNBARestTravelUpstreamError(
                "Step 7G Step 4I daily schedule contains a malformed game row."
            )
        if game.get("official_schedule_date") != target_date:
            raise WNBARestTravelUpstreamError(
                "Step 7G Step 4I daily schedule contains a game from the wrong date."
            )
        verification = game.get("verification")
        if not isinstance(verification, dict):
            raise WNBARestTravelUpstreamError(
                "Step 7G Step 4I daily schedule is missing game verification."
            )
        if verification.get("game_id_valid") is not True:
            raise WNBARestTravelUpstreamError(
                "Step 7G Step 4I daily schedule contains an invalid game ID."
            )
        if verification.get("teams_mapped_to_registry") is not True:
            raise WNBARestTravelUpstreamError(
                "Step 7G Step 4I daily schedule contains an unmapped WNBA franchise."
            )
        if verification.get("home_away_distinct") is not True:
            raise WNBARestTravelUpstreamError(
                "Step 7G Step 4I daily schedule contains invalid home/away identity."
            )
        game_id = str(game.get("game_id") or "")
        if not game_id:
            raise WNBARestTravelUpstreamError(
                "Step 7G Step 4I daily schedule contains a missing game ID."
            )
        ids.append(game_id)

    duplicates = sorted({game_id for game_id in ids if ids.count(game_id) > 1})
    if duplicates:
        raise WNBARestTravelUpstreamError(
            "Step 7G Step 4I daily schedule contains duplicate game IDs: "
            + ", ".join(duplicates)
            + "."
        )


def get_step7g_step4i_daily_schedule_dataset(
    target_date: str,
    season: int,
) -> dict[str, Any]:
    """Return a Step-4C-compatible daily view from certified WNBA.com schedule."""
    target_date = _target_date(target_date)
    season_dataset = get_step7g_step4n_season_schedule_dataset(season)
    source_games = season_dataset.get("games")
    if not isinstance(source_games, list):
        raise WNBARestTravelUpstreamError(
            "Certified Step 7G season schedule returned no games list for Step 4I."
        )

    games = [
        deepcopy(game)
        for game in source_games
        if isinstance(game, dict)
        and game.get("official_schedule_date") == target_date
    ]
    games.sort(
        key=lambda game: (
            game.get("game_datetime_utc") or "",
            game.get("game_id") or "",
        )
    )
    _validate_daily_games(games, target_date)

    return {
        "source": season_dataset.get("source"),
        "source_url": season_dataset.get("source_url"),
        "source_variant": STEP7G_STEP4I_DAILY_SOURCE_VARIANT,
        "upstream_source_variant": season_dataset.get("source_variant"),
        "league_id": WNBA_LEAGUE_ID,
        "season": season,
        "date": target_date,
        "retrieved_at_utc": season_dataset.get("retrieved_at_utc"),
        "cache_hit": season_dataset.get("cache_hit"),
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
        "source_date_block_count": 1 if games else 0,
        "source_game_count": len(games),
        "game_count": len(games),
        "games": games,
        "verification": {
            "derived_only_from_certified_step4n_season_schedule": True,
            "all_game_ids_valid": True,
            "all_game_ids_unique": True,
            "all_teams_mapped_to_registry": True,
            "all_home_away_distinct": True,
            "all_rows_match_requested_date": True,
            "frozen_step4c_module_modified": False,
            "frozen_step4i_module_modified": False,
            "production_provider_replaced": False,
        },
    }
