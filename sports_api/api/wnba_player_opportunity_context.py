from fastapi import APIRouter, HTTPException, Query

from sports_api.wnba_game_history import ALLOWED_SEASON_TYPES
from sports_api.wnba_league import CURRENT_SUPPORTED_SEASON
from sports_api.wnba_player_opportunity_context import (
    WNBAPlayerOpportunityNotFoundError,
    WNBAPlayerOpportunityUpstreamError,
    get_player_opportunity_context,
)

router = APIRouter(prefix="/api/v1/wnba", tags=["wnba"])


def _value_error(exc: ValueError) -> HTTPException:
    message = str(exc)
    status_code = 400 if "player_id must be a positive integer" in message else 422
    return HTTPException(status_code=status_code, detail=message)


def _not_found(exc: WNBAPlayerOpportunityNotFoundError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


def _upstream(exc: WNBAPlayerOpportunityUpstreamError) -> HTTPException:
    return HTTPException(status_code=502, detail=str(exc))


@router.get("/players/{player_id}/opportunity-context")
def player_opportunity_context(
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
        description="Recent observed window used across rotation, role, lineup, and event features.",
    ),
    include_current_availability: bool = Query(
        default=True,
        description=(
            "When true, enrich with the latest official injury/availability snapshot. "
            "Availability never automatically reallocates opportunity."
        ),
    ),
):
    try:
        return get_player_opportunity_context(
            player_id,
            season,
            season_type=season_type,
            last_n_games=last_n_games,
            include_current_availability=include_current_availability,
        )
    except ValueError as exc:
        raise _value_error(exc) from exc
    except WNBAPlayerOpportunityNotFoundError as exc:
        raise _not_found(exc) from exc
    except WNBAPlayerOpportunityUpstreamError as exc:
        raise _upstream(exc) from exc
