"""Current-season official WNBA schedule transport.

The WNBA moved the current public schedule document to the unsuffixed
``scheduleLeagueV2.json`` CDN path in 2026.  Step 6H uses this narrow adapter
instead of falling through to the retired/unstable stats schedule endpoint.

This module is read-only and retains the established Step 4C normalized daily
schedule shape so downstream slate reconciliation does not change semantics.
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

WNBA_CURRENT_CDN_SCHEDULE_URL = (
    "https://cdn.wnba.com/static/json/staticData/scheduleLeagueV2.json"
)
MAX_RESPONSE_BYTES = 20_000_000

_CACHE: dict[int, dict[str, Any]] = {}
_CACHE_LOCK = Lock()


def _fetch_current_schedule_payload(season: int) -> tuple[dict[str, Any], str, bool]:
    now = monotonic()
    with _CACHE_LOCK:
        cached = _CACHE.get(int(season))
        if cached and cached["expires_at"] > now:
            return deepcopy(cached["payload"]), cached["retrieved_at_utc"], True
        if cached:
            _CACHE.pop(int(season), None)

    try:
        response = httpx.get(
            WNBA_CURRENT_CDN_SCHEDULE_URL,
            headers=HTTP_HEADERS,
            timeout=20.0,
            follow_redirects=True,
        )
        response.raise_for_status()
    except (httpx.HTTPError, OSError, TimeoutError) as exc:
        raise WNBAScheduleUpstreamError("Current official WNBA CDN schedule GET failed.") from exc

    if len(response.content) <= 0 or len(response.content) > MAX_RESPONSE_BYTES:
        raise WNBAScheduleUpstreamError("Current official WNBA CDN schedule response size was invalid.")
    try:
        payload = response.json()
    except Exception as exc:
        raise WNBAScheduleUpstreamError("Current official WNBA CDN schedule returned invalid JSON.") from exc
    if not isinstance(payload, dict):
        raise WNBAScheduleUpstreamError("Current official WNBA CDN schedule returned a non-object payload.")

    root = _schedule_root(payload)
    if str(root.get("seasonYear")) != str(int(season)):
        raise WNBAScheduleUpstreamError(
            f"Current official WNBA CDN schedule season {root.get('seasonYear')!r} does not match {season}."
        )

    retrieved = _utc_now_iso()
    with _CACHE_LOCK:
        _CACHE[int(season)] = {
            "payload": deepcopy(payload),
            "retrieved_at_utc": retrieved,
            "expires_at": now + CACHE_TTL_SECONDS,
        }
    return payload, retrieved, False


def get_daily_schedule_dataset(target_date: str, season: int) -> dict[str, Any]:
    """Return Step-4C-compatible daily data from the current official CDN."""
    get_wnba_teams(int(season))
    try:
        datetime.strptime(str(target_date), "%Y-%m-%d")
    except ValueError as exc:
        raise ValueError("date must use YYYY-MM-DD format.") from exc

    payload, retrieved_at_utc, cache_hit = _fetch_current_schedule_payload(int(season))
    root = _schedule_root(payload)
    matching_blocks = [
        block
        for block in root.get("gameDates", [])
        if isinstance(block, dict) and _date_block_iso(block.get("gameDate")) == str(target_date)
    ]
    raw_games: list[dict[str, Any]] = []
    for block in matching_blocks:
        games = block.get("games")
        if isinstance(games, list):
            raw_games.extend(row for row in games if isinstance(row, dict))

    games = [_normalize_game(row, str(target_date), int(season)) for row in raw_games]
    games.sort(key=lambda row: (row.get("game_datetime_utc") or "", row.get("game_id") or ""))
    return {
        "source": WNBA_SCHEDULE_SOURCE,
        "source_url": WNBA_CURRENT_CDN_SCHEDULE_URL,
        "source_variant": "wnba_current_cdn_schedule_unsuffixed",
        "league_id": WNBA_LEAGUE_ID,
        "season": int(season),
        "date": str(target_date),
        "retrieved_at_utc": retrieved_at_utc,
        "cache_hit": cache_hit,
        "cache_ttl_seconds": CACHE_TTL_SECONDS,
        "source_date_block_count": len(matching_blocks),
        "source_game_count": len(raw_games),
        "game_count": len(games),
        "games": games,
    }
