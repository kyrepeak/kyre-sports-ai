from fastapi import APIRouter, HTTPException, Query

from sports_api.wnba_game_history import ALLOWED_SEASON_TYPES
from sports_api.wnba_league import CURRENT_SUPPORTED_SEASON
from sports_api.wnba_projection_input_snapshot import (
    WNBAProjectionInputSnapshotNotFoundError,
    WNBAProjectionInputSnapshotUpstreamError,
    get_player_game_projection_input_snapshot,
)

router = APIRouter(prefix="/api/v1/wnba", tags=["wnba"])


def _value_error(exc: ValueError) -> HTTPException:
    message = str(exc)
    status_code = 400 if (
        "player_id must be a positive integer" in message
        or "game_id must be exactly 10 numeric digits" in message
    ) else 422
    return HTTPException(status_code=status_code, detail=message)


def _not_found(exc: WNBAProjectionInputSnapshotNotFoundError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


def _upstream(exc: WNBAProjectionInputSnapshotUpstreamError) -> HTTPException:
    return HTTPException(status_code=502, detail=str(exc))


@router.get("/games/{game_id}/players/{player_id}/projection-input-snapshot")
def player_game_projection_input_snapshot(
    game_id: str,
    player_id: int,
    season: int = Query(default=CURRENT_SUPPORTED_SEASON),
    season_type: str = Query(
        default="Regular Season",
        description="Allowed: " + ", ".join(ALLOWED_SEASON_TYPES),
    ),
    last_n_games: int = Query(default=5, ge=1, le=20),
    include_current_availability: bool = Query(default=True),
    include_shot_context: bool = Query(default=True),
    include_advanced_context: bool = Query(default=True),
    include_officiating_context: bool = Query(default=True),
):
    try:
        return get_player_game_projection_input_snapshot(
            player_id,
            game_id,
            season,
            season_type=season_type,
            last_n_games=last_n_games,
            include_current_availability=include_current_availability,
            include_shot_context=include_shot_context,
            include_advanced_context=include_advanced_context,
            include_officiating_context=include_officiating_context,
        )
    except ValueError as exc:
        raise _value_error(exc) from exc
    except WNBAProjectionInputSnapshotNotFoundError as exc:
        raise _not_found(exc) from exc
    except WNBAProjectionInputSnapshotUpstreamError as exc:
        raise _upstream(exc) from exc
