"""FastAPI transport for WNBA Step 5M real prop-line feed normalization."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from sports_api.wnba_daily_slate_top_five import (
    WNBADailySlateTopFiveModelInputError,
    WNBADailySlateTopFiveNotReadyError,
    WNBADailySlateTopFiveUpstreamError,
)
from sports_api.wnba_league import CURRENT_SUPPORTED_SEASON
from sports_api.wnba_model_input_readiness import DEFAULT_MAX_SNAPSHOT_AGE_MINUTES
from sports_api.wnba_multi_sportsbook_market_consensus import DEFAULT_MAX_MARKET_AGE_MINUTES
from sports_api.wnba_player_prop_top_five_board import (
    DEFAULT_MAXIMUM_SCENARIO_SPAN_PERCENTAGE_POINTS,
    DEFAULT_MINIMUM_BASE_PROBABILITY,
    DEFAULT_MINIMUM_WORST_SCENARIO_PROBABILITY,
    DEFAULT_TOP_N,
    MAX_TOP_N,
    MIN_TOP_N,
    WNBAPlayerPropBoardModelInputError,
    WNBAPlayerPropBoardNotReadyError,
    WNBAPlayerPropBoardUpstreamError,
)
from sports_api.wnba_prop_line_feed_adapter import (
    CANONICAL_FEED_FORMAT,
    DEFAULT_MAX_SIDE_PAIR_SKEW_SECONDS,
    MAX_SIDE_PAIR_SKEW_SECONDS,
    WNBAPropLineFeedModelInputError,
    WNBAPropLineFeedNotReadyError,
    WNBAPropLineFeedUpstreamError,
    build_feed_daily_top_five,
    build_prop_line_feed_board,
)
from sports_api.wnba_prop_threshold_probability import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_RANDOM_SEED,
    DEFAULT_SIMULATION_COUNT,
    MAX_BATCH_SIZE,
    MAX_SIMULATION_COUNT,
    MIN_BATCH_SIZE,
    MIN_SIMULATION_COUNT,
)

router = APIRouter(prefix="/api/v1/wnba", tags=["wnba"])


class RealPropLineFeedInput(BaseModel):
    feed_source: str
    feed_format: str = CANONICAL_FEED_FORMAT
    odds_format: str = "american"
    feed_captured_at_utc: str | None = None
    raw_feed: dict[str, Any]


def _raise_api_error(exc: Exception) -> None:
    if isinstance(
        exc,
        (
            ValueError,
            WNBAPropLineFeedModelInputError,
            WNBADailySlateTopFiveModelInputError,
            WNBAPlayerPropBoardModelInputError,
        ),
    ):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if isinstance(
        exc,
        (
            WNBAPropLineFeedNotReadyError,
            WNBADailySlateTopFiveNotReadyError,
            WNBAPlayerPropBoardNotReadyError,
        ),
    ):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(
        exc,
        (
            WNBAPropLineFeedUpstreamError,
            WNBADailySlateTopFiveUpstreamError,
            WNBAPlayerPropBoardUpstreamError,
        ),
    ):
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    raise exc


@router.post("/markets/player-props/line-board")
def normalize_real_prop_line_feed(
    payload: RealPropLineFeedInput,
    date: str | None = Query(
        default=None,
        description="Official WNBA slate date in YYYY-MM-DD. Defaults to today's Arizona date.",
    ),
    season: int = Query(default=CURRENT_SUPPORTED_SEASON),
    max_market_age_minutes: int = Query(
        default=DEFAULT_MAX_MARKET_AGE_MINUTES,
        ge=1,
        le=1440,
    ),
    exclude_stale_quotes: bool = Query(default=True),
    max_side_pair_skew_seconds: int = Query(
        default=DEFAULT_MAX_SIDE_PAIR_SKEW_SECONDS,
        ge=0,
        le=MAX_SIDE_PAIR_SKEW_SECONDS,
    ),
):
    try:
        return build_prop_line_feed_board(
            payload.raw_feed,
            feed_source=payload.feed_source,
            feed_format=payload.feed_format,
            odds_format=payload.odds_format,
            feed_captured_at_utc=payload.feed_captured_at_utc,
            date=date,
            season=season,
            max_market_age_minutes=max_market_age_minutes,
            exclude_stale_quotes=exclude_stale_quotes,
            max_side_pair_skew_seconds=max_side_pair_skew_seconds,
        )
    except Exception as exc:
        _raise_api_error(exc)


@router.post("/rankings/player-props/feed-daily-top-five")
def create_feed_daily_top_five(
    payload: RealPropLineFeedInput,
    date: str | None = Query(
        default=None,
        description="Official WNBA slate date in YYYY-MM-DD. Defaults to today's Arizona date.",
    ),
    season: int = Query(default=CURRENT_SUPPORTED_SEASON),
    max_market_age_minutes: int = Query(
        default=DEFAULT_MAX_MARKET_AGE_MINUTES,
        ge=1,
        le=1440,
    ),
    exclude_stale_quotes: bool = Query(default=True),
    max_side_pair_skew_seconds: int = Query(
        default=DEFAULT_MAX_SIDE_PAIR_SKEW_SECONDS,
        ge=0,
        le=MAX_SIDE_PAIR_SKEW_SECONDS,
    ),
    season_type: str = Query(default="Regular Season"),
    last_n_games: int = Query(default=5, ge=1, le=20),
    distribution_last_n_games: int = Query(default=10, ge=1, le=50),
    simulation_count: int = Query(
        default=DEFAULT_SIMULATION_COUNT,
        ge=MIN_SIMULATION_COUNT,
        le=MAX_SIMULATION_COUNT,
    ),
    batch_size: int = Query(
        default=DEFAULT_BATCH_SIZE,
        ge=MIN_BATCH_SIZE,
        le=MAX_BATCH_SIZE,
    ),
    random_seed: int = Query(default=DEFAULT_RANDOM_SEED, ge=0, le=4_294_967_295),
    require_current_availability: bool = Query(default=True),
    max_snapshot_age_minutes: int = Query(
        default=DEFAULT_MAX_SNAPSHOT_AGE_MINUTES,
        ge=1,
        le=1440,
    ),
    require_convergence: bool = Query(default=True),
    minimum_required_ev: float = Query(default=0.0, ge=0.0, le=1.0),
    include_stored_calibration: bool = Query(default=True),
    require_slate_integrity: bool = Query(default=True),
    top_n: int = Query(default=DEFAULT_TOP_N, ge=MIN_TOP_N, le=MAX_TOP_N),
    minimum_base_probability: float = Query(
        default=DEFAULT_MINIMUM_BASE_PROBABILITY,
        ge=0.0,
        le=1.0,
    ),
    minimum_worst_scenario_probability: float = Query(
        default=DEFAULT_MINIMUM_WORST_SCENARIO_PROBABILITY,
        ge=0.0,
        le=1.0,
    ),
    maximum_scenario_span_percentage_points: float = Query(
        default=DEFAULT_MAXIMUM_SCENARIO_SPAN_PERCENTAGE_POINTS,
        ge=0.0,
        le=100.0,
    ),
    require_same_favored_side_all_scenarios: bool = Query(default=True),
    require_strict_numerical_readiness: bool = Query(default=True),
    require_mature_calibration: bool = Query(default=False),
    one_line_per_player_stat: bool = Query(default=True),
):
    try:
        return build_feed_daily_top_five(
            payload.raw_feed,
            feed_source=payload.feed_source,
            feed_format=payload.feed_format,
            odds_format=payload.odds_format,
            feed_captured_at_utc=payload.feed_captured_at_utc,
            date=date,
            season=season,
            max_market_age_minutes=max_market_age_minutes,
            exclude_stale_quotes=exclude_stale_quotes,
            max_side_pair_skew_seconds=max_side_pair_skew_seconds,
            season_type=season_type,
            last_n_games=last_n_games,
            distribution_last_n_games=distribution_last_n_games,
            simulation_count=simulation_count,
            batch_size=batch_size,
            random_seed=random_seed,
            require_current_availability=require_current_availability,
            max_snapshot_age_minutes=max_snapshot_age_minutes,
            require_convergence=require_convergence,
            minimum_required_ev=minimum_required_ev,
            include_stored_calibration=include_stored_calibration,
            require_slate_integrity=require_slate_integrity,
            top_n=top_n,
            minimum_base_probability=minimum_base_probability,
            minimum_worst_scenario_probability=minimum_worst_scenario_probability,
            maximum_scenario_span_percentage_points=maximum_scenario_span_percentage_points,
            require_same_favored_side_all_scenarios=require_same_favored_side_all_scenarios,
            require_strict_numerical_readiness=require_strict_numerical_readiness,
            require_mature_calibration=require_mature_calibration,
            one_line_per_player_stat=one_line_per_player_stat,
        )
    except Exception as exc:
        _raise_api_error(exc)
