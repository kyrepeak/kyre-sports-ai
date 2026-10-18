"""WNBA Step 5M resilient identity successor over the frozen V1 adapter.

The original normalizer is preserved byte-for-byte in
``wnba_prop_line_feed_adapter_v1``. This compatibility owner resolves the roster
through the exact official/cache+corroboration contract before delegating all
market normalization, pairing, probability handoff, and audit semantics to V1.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

import sports_api.wnba_prop_line_feed_adapter_v1 as previous
from sports_api.wnba_prop_line_feed_adapter_v1 import *  # noqa: F401,F403
from sports_api.wnba_roster_identity_resolver_v1 import (
    WNBARosterIdentityNotReadyError,
    resolve_verified_roster,
)

MODEL_SOURCE = previous.MODEL_SOURCE
MODEL_VERSION = previous.MODEL_VERSION
SCHEMA_VERSION = previous.SCHEMA_VERSION
MODEL_FAMILY = previous.MODEL_FAMILY
CANONICAL_FEED_FORMAT = previous.CANONICAL_FEED_FORMAT
BOOKMAKER_EVENT_FEED_FORMAT = previous.BOOKMAKER_EVENT_FEED_FORMAT
SUPPORTED_FEED_FORMATS = previous.SUPPORTED_FEED_FORMATS
SUPPORTED_ODDS_FORMATS = previous.SUPPORTED_ODDS_FORMATS
DEFAULT_MAX_SIDE_PAIR_SKEW_SECONDS = previous.DEFAULT_MAX_SIDE_PAIR_SKEW_SECONDS
MAX_SIDE_PAIR_SKEW_SECONDS = previous.MAX_SIDE_PAIR_SKEW_SECONDS
DEFAULT_MAX_MARKET_AGE_MINUTES = previous.DEFAULT_MAX_MARKET_AGE_MINUTES
CURRENT_SUPPORTED_SEASON = previous.CURRENT_SUPPORTED_SEASON
WNBAPropLineFeedNotReadyError = previous.WNBAPropLineFeedNotReadyError
WNBAPropLineFeedUpstreamError = previous.WNBAPropLineFeedUpstreamError
WNBAPropLineFeedModelInputError = previous.WNBAPropLineFeedModelInputError


def build_prop_line_feed_board(
    raw_feed: dict[str, Any],
    *,
    feed_source: str,
    feed_format: str = CANONICAL_FEED_FORMAT,
    odds_format: str = "american",
    feed_captured_at_utc: str | None = None,
    date: str | None = None,
    season: int = CURRENT_SUPPORTED_SEASON,
    max_market_age_minutes: int = DEFAULT_MAX_MARKET_AGE_MINUTES,
    exclude_stale_quotes: bool = True,
    max_side_pair_skew_seconds: int = DEFAULT_MAX_SIDE_PAIR_SKEW_SECONDS,
    now_utc: datetime | None = None,
    slate_getter: Callable[..., dict[str, Any]] = previous.verify_daily_slate_dataset,
    roster_getter: Callable[..., dict[str, Any]] = previous.get_current_players_dataset,
    roster_resolver: Callable[..., dict[str, Any]] = resolve_verified_roster,
) -> dict[str, Any]:
    # Preserve the V1 fail-fast order before any schedule/network work.
    if not isinstance(season, int) or isinstance(season, bool) or season <= 0:
        raise ValueError("WNBA Step 5M season must be a positive integer.")
    target_date = previous._target_date(date)
    try:
        slate = slate_getter(target_date, season)
    except previous.WNBAScheduleUpstreamError as exc:
        raise WNBAPropLineFeedUpstreamError(f"Step 5M official slate lookup failed: {exc}") from exc
    playable_games = previous._validate_slate(slate, target_date=target_date, season=season)
    current = now_utc or previous._utc_now()
    try:
        roster = roster_resolver(
            season,
            playable_games,
            primary_getter=roster_getter,
            now_utc=current,
        )
    except WNBARosterIdentityNotReadyError as exc:
        raise WNBAPropLineFeedUpstreamError(f"Step 5M resilient roster identity failed: {exc}") from exc

    def cached_slate_getter(_date, _season):
        return slate

    def resolved_roster_getter(_season, *, current_roster_only=True):
        del _season, current_roster_only
        return roster

    return previous.build_prop_line_feed_board(
        raw_feed,
        feed_source=feed_source,
        feed_format=feed_format,
        odds_format=odds_format,
        feed_captured_at_utc=feed_captured_at_utc,
        date=target_date,
        season=season,
        max_market_age_minutes=max_market_age_minutes,
        exclude_stale_quotes=exclude_stale_quotes,
        max_side_pair_skew_seconds=max_side_pair_skew_seconds,
        now_utc=current,
        slate_getter=cached_slate_getter,
        roster_getter=resolved_roster_getter,
    )


def build_feed_daily_top_five(*args, line_board_builder=build_prop_line_feed_board, **kwargs):
    return previous.build_feed_daily_top_five(*args, line_board_builder=line_board_builder, **kwargs)


def __getattr__(name):
    return getattr(previous, name)


__all__ = [
    "build_prop_line_feed_board", "build_feed_daily_top_five",
    "WNBAPropLineFeedNotReadyError", "WNBAPropLineFeedUpstreamError",
    "WNBAPropLineFeedModelInputError",
]
