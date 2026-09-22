from fastapi import APIRouter, HTTPException, Query

from sports_api.wnba_game_history import ALLOWED_SEASON_TYPES
from sports_api.wnba_league import CURRENT_SUPPORTED_SEASON
from sports_api.wnba_rotation_context import (
    ALLOWED_ROTATION_STATS,
    WNBARotationNotFoundError,
    WNBARotationUpstreamError,
    get_game_player_rotation,
    get_game_rotation,
    get_player_recent_rotation_context,
)

router = APIRouter(prefix="/api/v1/wnba", tags=["wnba"])


def _value_error(exc: ValueError) -> HTTPException:
    message = str(exc)
    status_code = 400 if (
        "game_id must be exactly 10 numeric digits" in message
        or "player_id must be a positive integer" in message
    ) else 422
    return HTTPException(status_code=status_code, detail=message)


def _not_found(exc: WNBARotationNotFoundError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


def _upstream(exc: WNBARotationUpstreamError) -> HTTPException:
    return HTTPException(status_code=502, detail=str(exc))


@router.get("/games/{game_id}/rotation")
def game_rotation(
    game_id: str,
    season: int = Query(
        default=CURRENT_SUPPORTED_SEASON,
        description="WNBA season. Step 4R currently supports the verified 2026 registry.",
    ),
    rotation_stat: str = Query(
        default="PLAYER_PTS",
        description="Official GameRotation rotation-stat selector. Allowed: "
        + ", ".join(ALLOWED_ROTATION_STATS),
    ),
):
    try:
        return get_game_rotation(game_id, season, rotation_stat=rotation_stat)
    except ValueError as exc:
        raise _value_error(exc) from exc
    except WNBARotationNotFoundError as exc:
        raise _not_found(exc) from exc
    except WNBARotationUpstreamError as exc:
        raise _upstream(exc) from exc


@router.get("/games/{game_id}/rotation/players/{player_id}")
def game_player_rotation(
    game_id: str,
    player_id: int,
    season: int = Query(default=CURRENT_SUPPORTED_SEASON),
    rotation_stat: str = Query(default="PLAYER_PTS"),
):
    try:
        return get_game_player_rotation(
            game_id,
            player_id,
            season,
            rotation_stat=rotation_stat,
        )
    except ValueError as exc:
        raise _value_error(exc) from exc
    except WNBARotationNotFoundError as exc:
        raise _not_found(exc) from exc
    except WNBARotationUpstreamError as exc:
        raise _upstream(exc) from exc


@router.get("/players/{player_id}/rotation-context")
def player_rotation_context(
    player_id: int,
    season: int = Query(default=CURRENT_SUPPORTED_SEASON),
    season_type: str = Query(
        default="Regular Season",
        description="Allowed: " + ", ".join(ALLOWED_SEASON_TYPES),
    ),
    last_n_games: int = Query(
        default=5,
        description="Recent official player-game-log window used to select games, 1-20.",
    ),
    rotation_stat: str = Query(
        default="PLAYER_PTS",
        description="Allowed: " + ", ".join(ALLOWED_ROTATION_STATS),
    ),
):
    try:
        return get_player_recent_rotation_context(
            player_id,
            season,
            season_type=season_type,
            last_n_games=last_n_games,
            rotation_stat=rotation_stat,
        )
    except ValueError as exc:
        raise _value_error(exc) from exc
    except WNBARotationNotFoundError as exc:
        raise _not_found(exc) from exc
    except WNBARotationUpstreamError as exc:
        raise _upstream(exc) from exc
