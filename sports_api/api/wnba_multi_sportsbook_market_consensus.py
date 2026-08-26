from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from sports_api.wnba_game_history import ALLOWED_SEASON_TYPES
from sports_api.wnba_league import CURRENT_SUPPORTED_SEASON
from sports_api.wnba_model_input_readiness import DEFAULT_MAX_SNAPSHOT_AGE_MINUTES
from sports_api.wnba_multi_sportsbook_market_consensus import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_MAX_MARKET_AGE_MINUTES,
    DEFAULT_RANDOM_SEED,
    DEFAULT_SIMULATION_COUNT,
    MAX_BATCH_SIZE,
    MAX_MARKET_AGE_MINUTES,
    MAX_PROP_LINE,
    MAX_SIMULATION_COUNT,
    MIN_BATCH_SIZE,
    MIN_SIMULATION_COUNT,
    WNBAMultiSportsbookModelInputError,
    WNBAMultiSportsbookNotFoundError,
    WNBAMultiSportsbookNotReadyError,
    WNBAMultiSportsbookUpstreamError,
    get_player_game_multi_sportsbook_market_consensus,
)

router = APIRouter(prefix="/api/v1/wnba", tags=["wnba"])


class SportsbookQuoteInput(BaseModel):
    sportsbook: str
    over_odds: int
    under_odds: int
    market_captured_at_utc: str


class MultiSportsbookQuoteBatch(BaseModel):
    quotes: list[SportsbookQuoteInput]


def _dump_model(value: BaseModel) -> dict:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return value.dict()


def _value_error(exc: ValueError) -> HTTPException:
    message = str(exc)
    status_code = 400 if (
        "player_id must be a positive integer" in message
        or "game_id must be exactly 10 numeric digits" in message
    ) else 422
    return HTTPException(status_code=status_code, detail=message)


@router.post("/games/{game_id}/players/{player_id}/multi-sportsbook-market-consensus")
def player_game_multi_sportsbook_market_consensus(
    game_id: str,
    player_id: int,
    quote_batch: MultiSportsbookQuoteBatch,
    stat: str = Query(
        ...,
        description="Prop statistic. Canonical values: points, rebounds, assists, pra. Common aliases are accepted.",
    ),
    line: float = Query(
        ...,
        ge=0.0,
        le=MAX_PROP_LINE,
        description="Common statistical line shared by every sportsbook quote in the request body.",
    ),
    season: int = Query(default=CURRENT_SUPPORTED_SEASON),
    season_type: str = Query(
        default="Regular Season",
        description="Allowed: " + ", ".join(ALLOWED_SEASON_TYPES),
    ),
    last_n_games: int = Query(
        default=5,
        ge=1,
        le=20,
        description="Recent window used by the frozen projection-context chain.",
    ),
    distribution_last_n_games: int = Query(
        default=10,
        ge=1,
        le=50,
        description="Maximum complete target-team pregame observations used by Step 5D/5E.",
    ),
    simulation_count: int = Query(
        default=DEFAULT_SIMULATION_COUNT,
        ge=MIN_SIMULATION_COUNT,
        le=MAX_SIMULATION_COUNT,
        description="Step-5E Monte Carlo trials per LOW/BASE/HIGH conditional scenario.",
    ),
    batch_size: int = Query(
        default=DEFAULT_BATCH_SIZE,
        ge=MIN_BATCH_SIZE,
        le=MAX_BATCH_SIZE,
        description="Step-5E vectorized NumPy batch size.",
    ),
    random_seed: int = Query(
        default=DEFAULT_RANDOM_SEED,
        ge=0,
        le=4_294_967_295,
        description="Deterministic Step-5E PCG64 seed.",
    ),
    require_current_availability: bool = Query(
        default=True,
        description="When true, Step 4X requires current roster/injury evidence before projection.",
    ),
    max_snapshot_age_minutes: int = Query(
        default=DEFAULT_MAX_SNAPSHOT_AGE_MINUTES,
        ge=1,
        le=1440,
        description="Maximum Step-4W snapshot age allowed by Step 4X.",
    ),
    require_convergence: bool = Query(
        default=True,
        description="Require Step-5E numerical convergence and Step-5F threshold precision before market comparison.",
    ),
    minimum_required_ev: float = Query(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Minimum expected net profit per unit stake used by playable-price checks. 0.05 means +5% EV.",
    ),
    max_market_age_minutes: int = Query(
        default=DEFAULT_MAX_MARKET_AGE_MINUTES,
        ge=1,
        le=MAX_MARKET_AGE_MINUTES,
        description="Maximum quote age before a sportsbook is classified stale.",
    ),
    exclude_stale_quotes: bool = Query(
        default=True,
        description="Exclude stale books from best-price, EV-ranking, and consensus calculations while retaining them in the audit trail.",
    ),
):
    quotes = [_dump_model(item) for item in quote_batch.quotes]
    try:
        return get_player_game_multi_sportsbook_market_consensus(
            player_id,
            game_id,
            season,
            stat=stat,
            line=line,
            quotes=quotes,
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
            max_market_age_minutes=max_market_age_minutes,
            exclude_stale_quotes=exclude_stale_quotes,
        )
    except ValueError as exc:
        raise _value_error(exc) from exc
    except WNBAMultiSportsbookNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WNBAMultiSportsbookNotReadyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except WNBAMultiSportsbookModelInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except WNBAMultiSportsbookUpstreamError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
