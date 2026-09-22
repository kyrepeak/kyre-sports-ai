from fastapi import APIRouter, HTTPException, Query

from sports_api.wnba_league import CURRENT_SUPPORTED_SEASON
from sports_api.wnba_live_game import (
    ALLOWED_EVENT_CATEGORIES,
    WNBALiveNotFoundError,
    WNBALiveUpstreamError,
    get_live_game_state_dataset,
    get_live_scoreboard_dataset,
    get_play_by_play_dataset,
)

router = APIRouter(prefix="/api/v1/wnba", tags=["wnba"])


def _value_error(exc: ValueError) -> HTTPException:
    message = str(exc)
    status_code = 400 if "game_id must be a 10-digit" in message else 422
    return HTTPException(status_code=status_code, detail=message)


def _not_found_error(exc: WNBALiveNotFoundError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


def _upstream_error(exc: WNBALiveUpstreamError) -> HTTPException:
    return HTTPException(status_code=502, detail=str(exc))


@router.get("/live/scoreboard")
def get_live_scoreboard(
    season: int = Query(
        default=CURRENT_SUPPORTED_SEASON,
        description="WNBA season. Step 4K currently supports the verified 2026 season.",
    ),
):
    try:
        return get_live_scoreboard_dataset(season)
    except ValueError as exc:
        raise _value_error(exc) from exc
    except WNBALiveNotFoundError as exc:
        raise _not_found_error(exc) from exc
    except WNBALiveUpstreamError as exc:
        raise _upstream_error(exc) from exc


@router.get("/games/{game_id}/live-state")
def get_live_game_state(
    game_id: str,
    season: int = Query(
        default=CURRENT_SUPPORTED_SEASON,
        description="WNBA season. Step 4K currently supports the verified 2026 season.",
    ),
):
    try:
        return get_live_game_state_dataset(game_id, season)
    except ValueError as exc:
        raise _value_error(exc) from exc
    except WNBALiveNotFoundError as exc:
        raise _not_found_error(exc) from exc
    except WNBALiveUpstreamError as exc:
        raise _upstream_error(exc) from exc


@router.get("/games/{game_id}/play-by-play")
def get_play_by_play(
    game_id: str,
    season: int = Query(
        default=CURRENT_SUPPORTED_SEASON,
        description="WNBA season. Step 4K currently supports the verified 2026 season.",
    ),
    event_category: str = Query(
        default="All",
        description="Event filter. Allowed values: " + ", ".join(ALLOWED_EVENT_CATEGORIES),
    ),
    limit: int = Query(
        default=0,
        ge=0,
        le=1000,
        description="0 = all matching events; otherwise return the most recent N matching events.",
    ),
):
    try:
        return get_play_by_play_dataset(
            game_id,
            season,
            event_category=event_category,
            limit=limit,
        )
    except ValueError as exc:
        raise _value_error(exc) from exc
    except WNBALiveNotFoundError as exc:
        raise _not_found_error(exc) from exc
    except WNBALiveUpstreamError as exc:
        raise _upstream_error(exc) from exc
