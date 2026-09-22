"""FastAPI transport for WNBA Step 5O provider onboarding, persistence, and failover."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from sports_api.collectors.wnba_prop_feed_collector import (
    WNBAPropFeedCollectorConfigError,
    WNBAPropFeedCollectorModelInputError,
    WNBAPropFeedCollectorNotReadyError,
    WNBAPropFeedCollectorUpstreamError,
)
from sports_api.collectors.wnba_sportsgameodds import WNBASportsGameOddsAdapterError
from sports_api.database.wnba_prop_feed_store import (
    MAX_HEALTH_ATTEMPTS,
    MAX_LIST_LIMIT,
    WNBAPropFeedStoreConflictError,
    WNBAPropFeedStoreError,
    get_store_status,
    list_feed_snapshots,
)
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
from sports_api.wnba_prop_feed_failover import (
    DEFAULT_MINIMUM_NORMALIZED_LINES,
    MAX_FAILOVER_PROVIDERS,
    WNBAPropFeedFailoverModelInputError,
    WNBAPropFeedFailoverNotReadyError,
    WNBAPropFeedFailoverStoreError,
    WNBAPropFeedFailoverUpstreamError,
    build_failover_daily_top_five,
    collect_failover_line_board,
    describe_provider_onboarding,
    get_failover_health,
)
from sports_api.wnba_prop_line_feed_adapter import (
    DEFAULT_MAX_SIDE_PAIR_SKEW_SECONDS,
    MAX_SIDE_PAIR_SKEW_SECONDS,
    WNBAPropLineFeedModelInputError,
    WNBAPropLineFeedNotReadyError,
    WNBAPropLineFeedUpstreamError,
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


def _raise_api_error(exc: Exception) -> None:
    if isinstance(
        exc,
        (
            ValueError,
            WNBAPropFeedCollectorConfigError,
            WNBAPropFeedCollectorModelInputError,
            WNBASportsGameOddsAdapterError,
            WNBAPropFeedFailoverModelInputError,
            WNBAPropLineFeedModelInputError,
            WNBADailySlateTopFiveModelInputError,
            WNBAPlayerPropBoardModelInputError,
        ),
    ):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if isinstance(
        exc,
        (
            WNBAPropFeedCollectorNotReadyError,
            WNBAPropFeedFailoverNotReadyError,
            WNBAPropLineFeedNotReadyError,
            WNBADailySlateTopFiveNotReadyError,
            WNBAPlayerPropBoardNotReadyError,
            WNBAPropFeedStoreConflictError,
        ),
    ):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(
        exc,
        (
            WNBAPropFeedCollectorUpstreamError,
            WNBAPropFeedFailoverUpstreamError,
            WNBAPropLineFeedUpstreamError,
            WNBADailySlateTopFiveUpstreamError,
            WNBAPlayerPropBoardUpstreamError,
        ),
    ):
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    if isinstance(exc, (WNBAPropFeedStoreError, WNBAPropFeedFailoverStoreError)):
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    raise exc


def _provider_ids(value: str | None) -> list[str] | None:
    if value is None:
        return None
    items = [item.strip() for item in value.split(",") if item.strip()]
    if not items:
        raise ValueError("provider_ids must contain at least one provider id when supplied.")
    if len(items) > MAX_FAILOVER_PROVIDERS:
        raise ValueError(f"provider_ids cannot contain more than {MAX_FAILOVER_PROVIDERS} providers.")
    return items


@router.get("/markets/player-props/providers/onboarding")
def get_prop_feed_onboarding_status():
    try:
        return describe_provider_onboarding()
    except Exception as exc:
        _raise_api_error(exc)


@router.get("/markets/player-props/collection-store/status")
def get_prop_feed_collection_store_status():
    try:
        return get_store_status()
    except Exception as exc:
        _raise_api_error(exc)


@router.get("/markets/player-props/collection-store/health")
def get_prop_feed_provider_health(
    provider_id: str | None = Query(default=None),
    attempts_per_provider: int = Query(default=20, ge=1, le=MAX_HEALTH_ATTEMPTS),
):
    try:
        return get_failover_health(provider_id, attempts_per_provider=attempts_per_provider)
    except Exception as exc:
        _raise_api_error(exc)


@router.get("/markets/player-props/collection-store/snapshots")
def get_prop_feed_collection_snapshots(
    provider_id: str | None = Query(default=None),
    date: str | None = Query(default=None),
    season: int | None = Query(default=None, ge=1),
    limit: int = Query(default=100, ge=1, le=MAX_LIST_LIMIT),
    include_payload: bool = Query(default=False),
):
    try:
        return list_feed_snapshots(
            provider_id=provider_id,
            date=date,
            season=season,
            limit=limit,
            include_payload=include_payload,
        )
    except Exception as exc:
        _raise_api_error(exc)


@router.post("/markets/player-props/collect/failover/line-board")
def collect_failover_prop_line_board(
    provider_ids: str | None = Query(
        default=None,
        description="Optional comma-separated provider order. Defaults to configured failover order/readiness.",
    ),
    date: str | None = Query(default=None),
    season: int = Query(default=CURRENT_SUPPORTED_SEASON),
    max_market_age_minutes: int = Query(default=DEFAULT_MAX_MARKET_AGE_MINUTES, ge=1, le=1440),
    exclude_stale_quotes: bool = Query(default=True),
    max_side_pair_skew_seconds: int = Query(
        default=DEFAULT_MAX_SIDE_PAIR_SKEW_SECONDS,
        ge=0,
        le=MAX_SIDE_PAIR_SKEW_SECONDS,
    ),
    minimum_normalized_lines: int = Query(default=DEFAULT_MINIMUM_NORMALIZED_LINES, ge=0, le=1000),
    require_persistent_store: bool = Query(default=True),
):
    try:
        return collect_failover_line_board(
            _provider_ids(provider_ids),
            date=date,
            season=season,
            max_market_age_minutes=max_market_age_minutes,
            exclude_stale_quotes=exclude_stale_quotes,
            max_side_pair_skew_seconds=max_side_pair_skew_seconds,
            minimum_normalized_lines=minimum_normalized_lines,
            require_persistent_store=require_persistent_store,
        )
    except Exception as exc:
        _raise_api_error(exc)


@router.post("/rankings/player-props/collect/failover/daily-top-five")
def collect_failover_daily_top_five(
    provider_ids: str | None = Query(default=None),
    date: str | None = Query(default=None),
    season: int = Query(default=CURRENT_SUPPORTED_SEASON),
    max_market_age_minutes: int = Query(default=DEFAULT_MAX_MARKET_AGE_MINUTES, ge=1, le=1440),
    exclude_stale_quotes: bool = Query(default=True),
    max_side_pair_skew_seconds: int = Query(
        default=DEFAULT_MAX_SIDE_PAIR_SKEW_SECONDS,
        ge=0,
        le=MAX_SIDE_PAIR_SKEW_SECONDS,
    ),
    minimum_normalized_lines: int = Query(default=DEFAULT_MINIMUM_NORMALIZED_LINES, ge=0, le=1000),
    require_persistent_store: bool = Query(default=True),
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
    max_snapshot_age_minutes: int = Query(default=DEFAULT_MAX_SNAPSHOT_AGE_MINUTES, ge=1, le=1440),
    require_convergence: bool = Query(default=True),
    minimum_required_ev: float = Query(default=0.0, ge=0.0, le=1.0),
    include_stored_calibration: bool = Query(default=True),
    require_slate_integrity: bool = Query(default=True),
    top_n: int = Query(default=DEFAULT_TOP_N, ge=MIN_TOP_N, le=MAX_TOP_N),
    minimum_base_probability: float = Query(default=DEFAULT_MINIMUM_BASE_PROBABILITY, ge=0.0, le=1.0),
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
        return build_failover_daily_top_five(
            _provider_ids(provider_ids),
            date=date,
            season=season,
            max_market_age_minutes=max_market_age_minutes,
            exclude_stale_quotes=exclude_stale_quotes,
            max_side_pair_skew_seconds=max_side_pair_skew_seconds,
            minimum_normalized_lines=minimum_normalized_lines,
            require_persistent_store=require_persistent_store,
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
