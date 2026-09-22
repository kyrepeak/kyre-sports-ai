from fastapi import APIRouter, HTTPException, Query

from sports_api.wnba_correlated_monte_carlo import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_RANDOM_SEED,
    DEFAULT_SIMULATION_COUNT,
    MAX_BATCH_SIZE,
    MAX_SIMULATION_COUNT,
    MIN_BATCH_SIZE,
    MIN_SIMULATION_COUNT,
    WNBACorrelatedMonteCarloModelInputError,
    WNBACorrelatedMonteCarloNotFoundError,
    WNBACorrelatedMonteCarloNotReadyError,
    WNBACorrelatedMonteCarloUpstreamError,
    get_player_game_correlated_monte_carlo,
)
from sports_api.wnba_game_history import ALLOWED_SEASON_TYPES
from sports_api.wnba_league import CURRENT_SUPPORTED_SEASON
from sports_api.wnba_model_input_readiness import DEFAULT_MAX_SNAPSHOT_AGE_MINUTES

router = APIRouter(prefix="/api/v1/wnba", tags=["wnba"])


def _value_error(exc: ValueError) -> HTTPException:
    message = str(exc)
    status_code = 400 if (
        "player_id must be a positive integer" in message
        or "game_id must be exactly 10 numeric digits" in message
    ) else 422
    return HTTPException(status_code=status_code, detail=message)


@router.get("/games/{game_id}/players/{player_id}/monte-carlo-outcomes")
def player_game_correlated_monte_carlo(
    game_id: str,
    player_id: int,
    season: int = Query(default=CURRENT_SUPPORTED_SEASON),
    season_type: str = Query(
        default="Regular Season",
        description="Allowed: " + ", ".join(ALLOWED_SEASON_TYPES),
    ),
    last_n_games: int = Query(
        default=5,
        ge=1,
        le=20,
        description="Recent window used by the frozen 4W/4X/5A/5B/5C projection chain.",
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
        description="Monte Carlo trials per LOW/BASE/HIGH conditional scenario. Default: 5,000,000.",
    ),
    batch_size: int = Query(
        default=DEFAULT_BATCH_SIZE,
        ge=MIN_BATCH_SIZE,
        le=MAX_BATCH_SIZE,
        description="Vectorized NumPy batch size used for convergence diagnostics.",
    ),
    random_seed: int = Query(
        default=DEFAULT_RANDOM_SEED,
        ge=0,
        le=4_294_967_295,
        description="Deterministic PCG64 seed for reproducible Monte Carlo results.",
    ),
    require_current_availability: bool = Query(
        default=True,
        description="When true, Step 4X requires current roster/injury evidence before simulation.",
    ),
    max_snapshot_age_minutes: int = Query(
        default=DEFAULT_MAX_SNAPSHOT_AGE_MINUTES,
        ge=1,
        le=1440,
        description="Maximum Step-4W snapshot age allowed by the Step-4X gate.",
    ),
):
    try:
        return get_player_game_correlated_monte_carlo(
            player_id,
            game_id,
            season,
            season_type=season_type,
            last_n_games=last_n_games,
            distribution_last_n_games=distribution_last_n_games,
            simulation_count=simulation_count,
            batch_size=batch_size,
            random_seed=random_seed,
            require_current_availability=require_current_availability,
            max_snapshot_age_minutes=max_snapshot_age_minutes,
        )
    except ValueError as exc:
        raise _value_error(exc) from exc
    except WNBACorrelatedMonteCarloNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WNBACorrelatedMonteCarloNotReadyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except WNBACorrelatedMonteCarloModelInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except WNBACorrelatedMonteCarloUpstreamError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
