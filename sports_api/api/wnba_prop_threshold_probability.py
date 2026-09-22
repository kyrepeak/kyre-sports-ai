from fastapi import APIRouter, HTTPException, Query

from sports_api.wnba_game_history import ALLOWED_SEASON_TYPES
from sports_api.wnba_league import CURRENT_SUPPORTED_SEASON
from sports_api.wnba_model_input_readiness import DEFAULT_MAX_SNAPSHOT_AGE_MINUTES
from sports_api.wnba_prop_threshold_probability import (
    DEFAULT_BATCH_SIZE,
    DEFAULT_RANDOM_SEED,
    DEFAULT_SIMULATION_COUNT,
    MAX_BATCH_SIZE,
    MAX_PROP_LINE,
    MAX_SIMULATION_COUNT,
    MIN_BATCH_SIZE,
    MIN_SIMULATION_COUNT,
    SUPPORTED_STATS,
    WNBAPropThresholdModelInputError,
    WNBAPropThresholdNotFoundError,
    WNBAPropThresholdNotReadyError,
    WNBAPropThresholdUpstreamError,
    get_player_game_prop_threshold_probability,
)

router = APIRouter(prefix="/api/v1/wnba", tags=["wnba"])


def _value_error(exc: ValueError) -> HTTPException:
    message = str(exc)
    status_code = 400 if (
        "player_id must be a positive integer" in message
        or "game_id must be exactly 10 numeric digits" in message
    ) else 422
    return HTTPException(status_code=status_code, detail=message)


@router.get("/games/{game_id}/players/{player_id}/prop-threshold-probability")
def player_game_prop_threshold_probability(
    game_id: str,
    player_id: int,
    stat: str = Query(
        ...,
        description=(
            "Prop statistic threshold to evaluate. Canonical values: "
            + ", ".join(SUPPORTED_STATS)
            + ". Common aliases such as PTS/REB/AST are accepted."
        ),
    ),
    line: float = Query(
        ...,
        ge=0.0,
        le=MAX_PROP_LINE,
        description=(
            "Post-projection statistical threshold. It does not alter the Step-5E "
            "basketball simulation. Integer lines can push; fractional lines cannot "
            "push because Step 5E outcomes are integer-valued."
        ),
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
        description="When true, Step 4X requires current roster/injury evidence before simulation.",
    ),
    max_snapshot_age_minutes: int = Query(
        default=DEFAULT_MAX_SNAPSHOT_AGE_MINUTES,
        ge=1,
        le=1440,
        description="Maximum Step-4W snapshot age allowed by the Step-4X gate.",
    ),
    require_convergence: bool = Query(
        default=True,
        description=(
            "When true, all Step-5E conditional scenarios and the threshold-level "
            "Monte Carlo precision gate must pass before fair odds are returned."
        ),
    ),
):
    try:
        return get_player_game_prop_threshold_probability(
            player_id,
            game_id,
            season,
            stat=stat,
            line=line,
            season_type=season_type,
            last_n_games=last_n_games,
            distribution_last_n_games=distribution_last_n_games,
            simulation_count=simulation_count,
            batch_size=batch_size,
            random_seed=random_seed,
            require_current_availability=require_current_availability,
            max_snapshot_age_minutes=max_snapshot_age_minutes,
            require_convergence=require_convergence,
        )
    except ValueError as exc:
        raise _value_error(exc) from exc
    except WNBAPropThresholdNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WNBAPropThresholdNotReadyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except WNBAPropThresholdModelInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except WNBAPropThresholdUpstreamError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
