"""WNBA Step 5O FanDuel-provider successor over the preserved failover engine.

V1 remains the authoritative sequential failover, persistence, validation and
audit implementation. This wrapper only registers the dedicated read-only
FanDuel WNBA collector as a first-class provider and translates its transport
errors into the existing provider-upstream failure class.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import sports_api.wnba_prop_feed_failover_v1 as previous
from sports_api.wnba_prop_feed_failover_v1 import *  # noqa: F401,F403
from sports_api.collectors.wnba_fanduel_direct import (
    FANDUEL_PROVIDER_ID,
    WNBAFanDuelCollectorError,
    collect_fanduel_wnba_feed,
)

MODEL_SOURCE = previous.MODEL_SOURCE
MODEL_VERSION = previous.MODEL_VERSION
SCHEMA_VERSION = previous.SCHEMA_VERSION
MODEL_FAMILY = previous.MODEL_FAMILY
FAILOVER_ORDER_ENV = previous.FAILOVER_ORDER_ENV
DEFAULT_MINIMUM_NORMALIZED_LINES = previous.DEFAULT_MINIMUM_NORMALIZED_LINES
DEFAULT_MAX_MARKET_AGE_MINUTES = previous.DEFAULT_MAX_MARKET_AGE_MINUTES
DEFAULT_MAX_SIDE_PAIR_SKEW_SECONDS = previous.DEFAULT_MAX_SIDE_PAIR_SKEW_SECONDS
CURRENT_SUPPORTED_SEASON = previous.CURRENT_SUPPORTED_SEASON
WNBAPropFeedFailoverNotReadyError = previous.WNBAPropFeedFailoverNotReadyError
WNBAPropFeedFailoverUpstreamError = previous.WNBAPropFeedFailoverUpstreamError
WNBAPropFeedFailoverModelInputError = previous.WNBAPropFeedFailoverModelInputError
WNBAPropFeedFailoverStoreError = previous.WNBAPropFeedFailoverStoreError


def _fanduel_collection(
    *,
    date: str | None,
    season: int,
    env: Mapping[str, str],
    requester: Callable[..., Any] | None,
    collector: Callable[..., dict[str, Any]],
) -> dict[str, Any]:
    try:
        collection = collector(date=date, season=season, env=env, requester=requester)
    except WNBAFanDuelCollectorError as exc:
        raise previous.WNBAPropFeedCollectorUpstreamError(str(exc)) from exc
    return {
        "provider_id": collection["provider_id"],
        "collection": collection,
        "adapter": None,
        "feed_source": collection["feed_source"],
        "feed_format": collection["feed_format"],
        "odds_format": collection["odds_format"],
        "date": collection["date"],
        "season": collection["season"],
        "collected_at_utc": collection["collected_at_utc"],
        "raw_feed": collection["raw_feed"],
    }


def _collect_candidate(
    provider_id: str,
    *,
    date: str | None,
    season: int,
    env: Mapping[str, str],
    requester: Callable[..., Any] | None,
    generic_collector: Callable[..., dict[str, Any]],
    sportsgameodds_collector: Callable[..., dict[str, Any]],
    kyre_market_collector: Callable[..., dict[str, Any]],
    fanduel_collector: Callable[..., dict[str, Any]] = collect_fanduel_wnba_feed,
) -> dict[str, Any]:
    if provider_id == FANDUEL_PROVIDER_ID:
        return _fanduel_collection(
            date=date,
            season=season,
            env=env,
            requester=requester,
            collector=fanduel_collector,
        )
    return previous._collect_candidate(
        provider_id,
        date=date,
        season=season,
        env=env,
        requester=requester,
        generic_collector=generic_collector,
        sportsgameodds_collector=sportsgameodds_collector,
        kyre_market_collector=kyre_market_collector,
    )


def collect_failover_line_board(
    provider_ids: Sequence[str] | None = None,
    *,
    date: str | None = None,
    season: int = CURRENT_SUPPORTED_SEASON,
    max_market_age_minutes: int = DEFAULT_MAX_MARKET_AGE_MINUTES,
    exclude_stale_quotes: bool = True,
    max_side_pair_skew_seconds: int = DEFAULT_MAX_SIDE_PAIR_SKEW_SECONDS,
    minimum_normalized_lines: int = DEFAULT_MINIMUM_NORMALIZED_LINES,
    require_persistent_store: bool = True,
    env: Mapping[str, str] | None = None,
    store_path: str | Path | None = None,
    requester: Callable[..., Any] | None = None,
    generic_collector: Callable[..., dict[str, Any]] = previous.collect_provider_feed,
    sportsgameodds_collector: Callable[..., dict[str, Any]] = previous.collect_sportsgameodds_feed,
    kyre_market_collector: Callable[..., dict[str, Any]] = previous.collect_kyre_market_feed,
    fanduel_collector: Callable[..., dict[str, Any]] = collect_fanduel_wnba_feed,
    line_board_builder: Callable[..., dict[str, Any]] = previous.build_prop_line_feed_board,
    snapshot_persister: Callable[..., dict[str, Any]] = previous.persist_feed_snapshot,
    attempt_appender: Callable[..., dict[str, Any]] = previous.append_feed_attempt,
) -> dict[str, Any]:
    def bridged_generic_collector(provider_id: str, *, date=None, season=CURRENT_SUPPORTED_SEASON, env=None, requester=None):
        if provider_id == FANDUEL_PROVIDER_ID:
            try:
                return fanduel_collector(date=date, season=season, env=env, requester=requester)
            except WNBAFanDuelCollectorError as exc:
                raise previous.WNBAPropFeedCollectorUpstreamError(str(exc)) from exc
        return generic_collector(provider_id, date=date, season=season, env=env, requester=requester)

    return previous.collect_failover_line_board(
        provider_ids,
        date=date,
        season=season,
        max_market_age_minutes=max_market_age_minutes,
        exclude_stale_quotes=exclude_stale_quotes,
        max_side_pair_skew_seconds=max_side_pair_skew_seconds,
        minimum_normalized_lines=minimum_normalized_lines,
        require_persistent_store=require_persistent_store,
        env=env,
        store_path=store_path,
        requester=requester,
        generic_collector=bridged_generic_collector,
        sportsgameodds_collector=sportsgameodds_collector,
        kyre_market_collector=kyre_market_collector,
        line_board_builder=line_board_builder,
        snapshot_persister=snapshot_persister,
        attempt_appender=attempt_appender,
    )


def describe_provider_onboarding(env: Mapping[str, str] | None = None) -> dict[str, Any]:
    out = dict(previous.describe_provider_onboarding(env))
    out["fanduel_provider"] = {
        "provider_id": FANDUEL_PROVIDER_ID,
        "ready": True,
        "credential_required": False,
        "transport": "anonymous read-only FanDuel sportsbook JSON",
        "projection_influence": 0.0,
    }
    return out


def __getattr__(name):
    return getattr(previous, name)


__all__ = [
    "FANDUEL_PROVIDER_ID", "FAILOVER_ORDER_ENV",
    "resolve_failover_order", "describe_provider_onboarding",
    "collect_failover_line_board", "WNBAPropFeedFailoverNotReadyError",
    "WNBAPropFeedFailoverUpstreamError", "WNBAPropFeedFailoverModelInputError",
    "WNBAPropFeedFailoverStoreError",
]
