"""Step 7G isolated first-party WNBA.com schedule adapter.

This module exists only to bypass the cloud-network failure affecting direct
``cdn.wnba.com``/``stats.wnba.com`` schedule reads. It consumes the same-origin
WNBA.com route used by the public site and deliberately reuses the frozen Step
4C normalization helpers so normalized game semantics do not drift.

Nothing in this module enables a scheduler, writes a feed, calls a sportsbook,
or mutates production state. The frozen ``sports_api.wnba_schedule`` fetch path
is not modified.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from threading import Lock
from time import monotonic
from typing import Any

import httpx

from sports_api.wnba_league import get_wnba_teams
from sports_api.wnba_schedule import (
    CACHE_TTL_SECONDS,
    HTTP_HEADERS,
    WNBA_LEAGUE_ID,
    WNBA_SCHEDULE_SOURCE,
    WNBAScheduleUpstreamError,
    _date_block_iso,
    _normalize_game,
    _schedule_root,
    _utc_now_iso,
)

FIRST_PARTY_SCHEDULE_URL = "https://www.wnba.com/api/schedule"
FIRST_PARTY_SOURCE_VARIANT = "wnba_com_first_party_schedule_proxy"

_CACHE: dict[int, dict[str, Any]] = {}
_CACHE_LOCK = Lock()


def _fetch_first_party_schedule_payload(
    season: int,
) -> tuple[dict[str, Any], str, str, str, bool]:
    """Return a validated official WNBA.com season schedule payload."""
    get_wnba_teams(season)
    now = monotonic()
    with _CACHE_LOCK:
        cached = _CACHE.get(season)
        if cached and cached["expires_at"] > now:
            return (
                deepcopy(cached["payload"]),
                cached["retrieved_at_utc"],
                FIRST_PARTY_SOURCE_VARIANT,
                cached["source_url"],
                True,
            )
        if cached:
            _CACHE.pop(season, None)

    params = {"season": str(season)}
    try:
        response = httpx.get(
            FIRST_PARTY_SCHEDULE_URL,
            params=params,
            headers=HTTP_HEADERS,
            timeout=20.0,
            follow_redirects=True,
        )
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise WNBAScheduleUpstreamError(
            f"Official WNBA.com first-party schedule request failed for {season}: {exc}"
        ) from exc

    if not isinstance(payload, dict):
        raise WNBAScheduleUpstreamError(
            "Official WNBA.com first-party schedule returned a non-object payload."
        )
    root = _schedule_root(payload)
    if str(root.get("seasonYear")) != str(season):
        raise WNBAScheduleUpstreamError(
            "Official WNBA.com first-party schedule season identity does not match request."
        )

    retrieved_at_utc = _utc_now_iso()
    source_url = str(response.url)
    with _CACHE_LOCK:
        _CACHE[season] = {
            "payload": deepcopy(payload),
            "retrieved_at_utc": retrieved_at_utc,
            "source_url": source_url,
            "expires_at": now + CACHE_TTL_SECONDS,
        }
    return (
        payload,
        retrieved_at_utc,
        FIRST_PARTY_SOURCE_VARIANT,
        source_url,
        False,
    )


def get_step7g_daily_schedule_dataset(target_date: str, season: int) -> dict[str, Any]:
    """Normalize one date with the frozen Step 4C game normalizer."""
    get_wnba_teams(season)
    try:
        datetime.strptime(target_date, "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("date must use YYYY-MM-DD format.") from exc

    payload, retrieved_at_utc, source_variant, source_url, cache_hit = (
        _fetch_first_party_schedule_payload(season)
    )
    root = _schedule_root(payload)

    matching_blocks: list[dict[str, Any]] = []
    for block in root.get("gameDates", []):
        if not isinstance(block, dict):
            continue
        if _date_block_iso(block.get("gameDate")) == target_date:
            matching_blocks.append(block)

    raw_games: list[dict[str, Any]] = []
    for block in matching_blocks:
        games = block.get("games")
        if isinstance(games, list):
            raw_games.extend(game for game in games if isinstance(game, dict))

    games = [_normalize_game(game, target_date, season) for game in raw_games]
    games.sort(
        key=lambda game: (
            game.get("game_datetime_utc") or "",
            game.get("game_id") or "",
        )
    )

    return {
        "source": WNBA_SCHEDULE_SOURCE,
        "source_url": source_url,
        "source_variant": source_variant,
        "league_id": WNBA_LEAGUE_ID,
        "season": season,
        "date": target_date,
        "retrieved_at_utc": retrieved_at_utc,
        "cache_hit": cache_hit,
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
        "source_date_block_count": len(matching_blocks),
        "source_game_count": len(raw_games),
        "game_count": len(games),
        "games": games,
    }


def verify_step7g_daily_slate_dataset(target_date: str, season: int) -> dict[str, Any]:
    """Apply the frozen Step 4C slate-integrity rules to first-party data."""
    dataset = get_step7g_daily_schedule_dataset(target_date, season)
    games = dataset["games"]

    game_ids = [game["game_id"] for game in games if game.get("game_id") is not None]
    duplicate_game_ids = sorted(
        {game_id for game_id in game_ids if game_ids.count(game_id) > 1}
    )

    all_game_ids_valid = all(game["verification"]["game_id_valid"] for game in games)
    all_game_ids_unique = len(game_ids) == len(set(game_ids))
    all_teams_mapped = all(
        game["verification"]["teams_mapped_to_registry"] for game in games
    )
    all_home_away_distinct = all(
        game["verification"]["home_away_distinct"] for game in games
    )
    game_count_matches_source = dataset["game_count"] == dataset["source_game_count"]
    date_block_count_valid = dataset["source_date_block_count"] <= 1

    if dataset["source_date_block_count"] == 0:
        completeness_status = "no_games_listed_for_date"
    elif dataset["source_date_block_count"] == 1:
        completeness_status = "official_date_block_verified"
    else:
        completeness_status = "duplicate_official_date_blocks"

    slate_integrity_pass = (
        date_block_count_valid
        and game_count_matches_source
        and all_game_ids_valid
        and all_game_ids_unique
        and all_teams_mapped
        and all_home_away_distinct
    )

    scheduled_games = sum(game["status"]["category"] == "scheduled" for game in games)
    live_games = sum(game["status"]["category"] == "live" for game in games)
    final_games = sum(game["status"]["category"] == "final" for game in games)
    changed_games = sum(game["schedule_change"]["schedule_changed"] for game in games)
    pregame_ready_games = sum(
        game["verification"]["playable_pregame"] for game in games
    )

    blocking_reasons: list[str] = []
    if not date_block_count_valid:
        blocking_reasons.append("duplicate_official_date_blocks")
    if not game_count_matches_source:
        blocking_reasons.append("normalized_game_count_mismatch")
    if not all_game_ids_valid:
        blocking_reasons.append("invalid_game_id")
    if not all_game_ids_unique:
        blocking_reasons.append("duplicate_game_id")
    if not all_teams_mapped:
        blocking_reasons.append("unmapped_team_identity")
    if not all_home_away_distinct:
        blocking_reasons.append("invalid_home_away_identity")

    return {
        "source": dataset["source"],
        "source_url": dataset["source_url"],
        "source_variant": dataset["source_variant"],
        "verified_by": "Kyre Sports API",
        "league_id": dataset["league_id"],
        "season": season,
        "date": target_date,
        "verified_at_utc": _utc_now_iso(),
        "source_retrieved_at_utc": dataset["retrieved_at_utc"],
        "slate": {
            "source_date_block_count": dataset["source_date_block_count"],
            "source_game_count": dataset["source_game_count"],
            "normalized_game_count": dataset["game_count"],
            "game_count_matches_source": game_count_matches_source,
            "all_game_ids_valid": all_game_ids_valid,
            "all_game_ids_unique": all_game_ids_unique,
            "duplicate_game_ids": duplicate_game_ids,
            "all_teams_mapped_to_registry": all_teams_mapped,
            "all_home_away_distinct": all_home_away_distinct,
            "completeness_status": completeness_status,
            "slate_integrity_pass": slate_integrity_pass,
            "blocking_reasons": blocking_reasons,
        },
        "status_summary": {
            "scheduled_games": scheduled_games,
            "live_games": live_games,
            "final_games": final_games,
            "schedule_changed_games": changed_games,
            "playable_pregame_games": pregame_ready_games,
        },
        "games": games,
    }
