"""Step 7G isolated first-party schedule adapter for frozen Step 4N context.

Frozen Step 4N consumes a season-wide franchise schedule. WNBA.com's 2026
first-party schedule also contains a small set of source-labeled preseason
exhibitions where exactly one participant is not a WNBA franchise. Frozen Step
4N correctly fails closed on a one-sided unmapped identity, which blocks all
regular-season rest/travel context before the target game can be evaluated.

This isolated adapter makes one narrow distinction for the Step 7G dependency
path: a one-sided unmapped row is excluded only when the official source itself
labels the row exactly ``Preseason`` (case-insensitive). Any other one-sided
unmapped identity still fails closed. Two-unmapped non-franchise events remain
excluded exactly as frozen Step 4N already does.

Daily slate verification is NOT changed. The frozen ``wnba_schedule_context``
and ``wnba_schedule`` modules are NOT modified. This module never starts a
scheduler, writes a feed, calls a sportsbook, or mutates production state.
"""
from __future__ import annotations

from typing import Any

from sports_api.wnba_league import get_wnba_teams
from sports_api.wnba_schedule import (
    WNBA_LEAGUE_ID,
    WNBA_SCHEDULE_SOURCE,
    _date_block_iso,
    _normalize_game,
    _schedule_root,
)
from sports_api.wnba_schedule_context import WNBARestTravelUpstreamError
from sports_api.wnba_step7g_first_party_schedule import (
    _fetch_first_party_schedule_payload,
)

STEP7G_STEP4N_SOURCE_VARIANT = "wnba_com_first_party_schedule_step4n_context"


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _mapped(team: Any) -> bool:
    return bool(isinstance(team, dict) and team.get("mapped_to_registry"))


def _explicit_preseason(game: dict[str, Any]) -> bool:
    competition = game.get("competition")
    if not isinstance(competition, dict):
        return False
    label = _clean(competition.get("game_label"))
    return bool(label and label.casefold() == "preseason")


def classify_step7g_step4n_game(game: dict[str, Any]) -> str:
    """Classify one frozen-normalized game for Step 7G Step 4N context.

    Returns ``include``, ``exclude_two_unmapped`` or
    ``exclude_explicit_preseason_one_sided``. Unexpected one-sided identities
    raise the same Step 4N upstream error family used by frozen code.
    """
    if not isinstance(game, dict):
        raise WNBARestTravelUpstreamError(
            "Step 7G Step 4N schedule adapter received a malformed game row."
        )
    away_mapped = _mapped(game.get("away"))
    home_mapped = _mapped(game.get("home"))
    mapped_count = int(away_mapped) + int(home_mapped)

    if mapped_count == 2:
        return "include"
    if mapped_count == 0:
        return "exclude_two_unmapped"
    if _explicit_preseason(game):
        return "exclude_explicit_preseason_one_sided"

    raise WNBARestTravelUpstreamError(
        "Official WNBA schedule returned a one-sided unmapped team identity "
        "outside an explicitly source-labeled Preseason game."
    )


def _validate_included_games(games: list[dict[str, Any]]) -> None:
    ids = [game.get("game_id") for game in games if game.get("game_id")]
    duplicates = sorted({game_id for game_id in ids if ids.count(game_id) > 1})
    invalid = sorted(
        {
            game.get("game_id")
            for game in games
            if not game.get("verification", {}).get("game_id_valid")
        },
        key=lambda item: item or "",
    )
    unmapped = [
        game.get("game_id")
        for game in games
        if not game.get("verification", {}).get("teams_mapped_to_registry")
    ]
    invalid_home_away = [
        game.get("game_id")
        for game in games
        if not game.get("verification", {}).get("home_away_distinct")
    ]
    if duplicates or invalid or unmapped or invalid_home_away:
        raise WNBARestTravelUpstreamError(
            "Official WNBA season schedule failed Step 7G Step 4N integrity checks."
        )


def _build_step7g_step4n_schedule_dataset(
    payload: dict[str, Any],
    season: int,
    *,
    retrieved_at_utc: str,
    source_variant: str,
    source_url: str,
    cache_hit: bool,
) -> dict[str, Any]:
    """Build a Step-4N-compatible season view from a validated schedule payload."""
    get_wnba_teams(season)
    root = _schedule_root(payload)

    games: list[dict[str, Any]] = []
    excluded_two_unmapped: list[dict[str, Any]] = []
    excluded_preseason_one_sided: list[dict[str, Any]] = []
    source_normalized_game_count = 0

    for block in root.get("gameDates", []):
        if not isinstance(block, dict):
            continue
        official_date = _date_block_iso(block.get("gameDate"))
        if official_date is None:
            continue
        raw_games = block.get("games")
        if not isinstance(raw_games, list):
            continue
        for raw in raw_games:
            if not isinstance(raw, dict):
                continue
            source_normalized_game_count += 1
            game = _normalize_game(raw, official_date, season)
            classification = classify_step7g_step4n_game(game)
            if classification == "include":
                games.append(game)
                continue

            evidence = {
                "game_id": game.get("game_id"),
                "official_schedule_date": game.get("official_schedule_date"),
                "game_label": (game.get("competition") or {}).get("game_label"),
                "away_official_team_id": (game.get("away") or {}).get("official_team_id"),
                "away_team_key": (game.get("away") or {}).get("team_key"),
                "away_mapped_to_registry": bool(
                    (game.get("away") or {}).get("mapped_to_registry")
                ),
                "home_official_team_id": (game.get("home") or {}).get("official_team_id"),
                "home_team_key": (game.get("home") or {}).get("team_key"),
                "home_mapped_to_registry": bool(
                    (game.get("home") or {}).get("mapped_to_registry")
                ),
                "classification": classification,
            }
            if classification == "exclude_two_unmapped":
                excluded_two_unmapped.append(evidence)
            else:
                excluded_preseason_one_sided.append(evidence)

    _validate_included_games(games)
    games.sort(
        key=lambda game: (
            game.get("official_schedule_date") or "",
            game.get("game_datetime_utc") or "",
            game.get("game_id") or "",
        )
    )

    return {
        "source": WNBA_SCHEDULE_SOURCE,
        "source_url": source_url,
        "source_variant": STEP7G_STEP4N_SOURCE_VARIANT,
        "upstream_source_variant": source_variant,
        "league_id": WNBA_LEAGUE_ID,
        "season": season,
        "retrieved_at_utc": retrieved_at_utc,
        "cache_hit": cache_hit,
        "game_count": len(games),
        "games": games,
        "verification": {
            "all_game_ids_valid": True,
            "all_game_ids_unique": True,
            "all_teams_mapped_to_registry": True,
            "all_home_away_distinct": True,
            "source_normalized_game_count": source_normalized_game_count,
            "included_franchise_game_count": len(games),
            "excluded_two_unmapped_count": len(excluded_two_unmapped),
            "excluded_two_unmapped_games": excluded_two_unmapped,
            "excluded_explicit_preseason_one_sided_count": len(
                excluded_preseason_one_sided
            ),
            "excluded_explicit_preseason_one_sided_games": (
                excluded_preseason_one_sided
            ),
            "one_sided_exclusion_requires_exact_preseason_label": True,
            "unexpected_one_sided_unmapped_still_fails_closed": True,
            "daily_slate_semantics_changed": False,
            "frozen_schedule_context_module_modified": False,
            "production_provider_replaced": False,
        },
    }


def get_step7g_step4n_season_schedule_dataset(season: int) -> dict[str, Any]:
    """Fetch official WNBA.com data and return the isolated Step 4N season view."""
    payload, retrieved, variant, source_url, cache_hit = (
        _fetch_first_party_schedule_payload(season)
    )
    return _build_step7g_step4n_schedule_dataset(
        payload,
        season,
        retrieved_at_utc=retrieved,
        source_variant=variant,
        source_url=source_url,
        cache_hit=cache_hit,
    )
