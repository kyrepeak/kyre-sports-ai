from fastapi import APIRouter, HTTPException, Query

from sports_api.wnba_event_lineup_context import (
    WNBAEventLineupNotFoundError,
    WNBAEventLineupUpstreamError,
    get_game_event_lineups,
    get_game_possession_event_context,
)
from sports_api.wnba_league import CURRENT_SUPPORTED_SEASON
from sports_api.wnba_live_game import ALLOWED_EVENT_CATEGORIES

router = APIRouter(prefix="/api/v1/wnba", tags=["wnba"])


def _value_error(exc: ValueError) -> HTTPException:
    message = str(exc)
    status_code = 400 if "game_id must be exactly 10 numeric digits" in message else 422
    return HTTPException(status_code=status_code, detail=message)


def _not_found(exc: WNBAEventLineupNotFoundError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


def _upstream(exc: WNBAEventLineupUpstreamError) -> HTTPException:
    return HTTPException(status_code=502, detail=str(exc))


@router.get("/games/{game_id}/event-lineups")
def game_event_lineups(
    game_id: str,
    season: int = Query(
        default=CURRENT_SUPPORTED_SEASON,
        description=(
            "WNBA season. Joins official play-by-play event times to observed "
            "GameRotation stints; court context does not imply defender assignments."
        ),
    ),
    event_category: str = Query(
        default="All",
        description="Event filter. Allowed: " + ", ".join(ALLOWED_EVENT_CATEGORIES),
    ),
    limit: int = Query(
        default=0,
        ge=0,
        le=1000,
        description="0 = all matching events; otherwise return the most recent N.",
    ),
):
    try:
        return get_game_event_lineups(
            game_id,
            season,
            event_category=event_category,
            limit=limit,
        )
    except ValueError as exc:
        raise _value_error(exc) from exc
    except WNBAEventLineupNotFoundError as exc:
        raise _not_found(exc) from exc
    except WNBAEventLineupUpstreamError as exc:
        raise _upstream(exc) from exc


@router.get("/games/{game_id}/possessions")
def game_possession_event_context(
    game_id: str,
    season: int = Query(
        default=CURRENT_SUPPORTED_SEASON,
        description=(
            "WNBA season. Possession segments are conservative deterministic "
            "play-by-play features, not an official possession feed."
        ),
    ),
    limit: int = Query(
        default=0,
        ge=0,
        le=1000,
        description="0 = all reconstructed segments; otherwise return the most recent N.",
    ),
):
    try:
        return get_game_possession_event_context(game_id, season, limit=limit)
    except ValueError as exc:
        raise _value_error(exc) from exc
    except WNBAEventLineupNotFoundError as exc:
        raise _not_found(exc) from exc
    except WNBAEventLineupUpstreamError as exc:
        raise _upstream(exc) from exc
