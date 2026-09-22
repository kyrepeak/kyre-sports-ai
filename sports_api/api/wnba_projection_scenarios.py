from fastapi import APIRouter, HTTPException, Query

from sports_api.wnba_game_history import ALLOWED_SEASON_TYPES
from sports_api.wnba_league import CURRENT_SUPPORTED_SEASON
from sports_api.wnba_model_input_readiness import DEFAULT_MAX_SNAPSHOT_AGE_MINUTES
from sports_api.wnba_projection_scenarios import (
    WNBAProjectionScenarioModelInputError,
    WNBAProjectionScenarioNotFoundError,
    WNBAProjectionScenarioNotReadyError,
    WNBAProjectionScenarioUpstreamError,
    get_player_game_projection_scenarios,
)

router = APIRouter(prefix="/api/v1/wnba", tags=["wnba"])


def _value_error(exc: ValueError) -> HTTPException:
    message = str(exc)
    status_code = 400 if (
        "player_id must be a positive integer" in message
        or "game_id must be exactly 10 numeric digits" in message
    ) else 422
    return HTTPException(status_code=status_code, detail=message)


@router.get("/games/{game_id}/players/{player_id}/projection-scenarios")
def player_game_projection_scenarios(
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
        description="Recent observed window used by frozen 4W/4X/5A/5B evidence and 5C scenarios.",
    ),
    require_current_availability: bool = Query(
        default=True,
        description="When true, Step 4X requires current roster/injury evidence before 5C may run.",
    ),
    max_snapshot_age_minutes: int = Query(
        default=DEFAULT_MAX_SNAPSHOT_AGE_MINUTES,
        ge=1,
        le=1440,
        description="Maximum Step-4W snapshot age allowed by the Step-4X gate.",
    ),
):
    try:
        return get_player_game_projection_scenarios(
            player_id,
            game_id,
            season,
            season_type=season_type,
            last_n_games=last_n_games,
            require_current_availability=require_current_availability,
            max_snapshot_age_minutes=max_snapshot_age_minutes,
        )
    except ValueError as exc:
        raise _value_error(exc) from exc
    except WNBAProjectionScenarioNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WNBAProjectionScenarioNotReadyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except WNBAProjectionScenarioModelInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except WNBAProjectionScenarioUpstreamError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
