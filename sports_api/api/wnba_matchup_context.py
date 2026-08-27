from fastapi import APIRouter, HTTPException, Query

from sports_api.wnba_game_history import ALLOWED_SEASON_TYPES
from sports_api.wnba_league import CURRENT_SUPPORTED_SEASON
from sports_api.wnba_matchup_context import (
    WNBAMatchupContextNotFoundError,
    WNBAMatchupContextUpstreamError,
    get_game_opponent_overlap,
    get_matchup_source_status,
    get_player_recent_opponent_overlap_context,
)

router = APIRouter(prefix="/api/v1/wnba", tags=["wnba"])


def _value_error(exc: ValueError) -> HTTPException:
    message = str(exc)
    status_code = 400 if "positive integer" in message else 422
    return HTTPException(status_code=status_code, detail=message)


def _not_found(exc: WNBAMatchupContextNotFoundError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


def _upstream(exc: WNBAMatchupContextUpstreamError) -> HTTPException:
    return HTTPException(status_code=502, detail=str(exc))


@router.get("/matchups/source-status")
def matchup_source_status(
    season: int = Query(
        default=CURRENT_SUPPORTED_SEASON,
        description=(
            "WNBA season. Reports whether official player-vs-defender matchup "
            "assignments are supportable from current WNBA sources."
        ),
    ),
):
    try:
        return get_matchup_source_status(season)
    except ValueError as exc:
        raise _value_error(exc) from exc


@router.get("/games/{game_id}/opponent-overlap")
def game_opponent_overlap(
    game_id: str,
    season: int = Query(default=CURRENT_SUPPORTED_SEASON),
    player_id: int | None = Query(
        default=None,
        description=(
            "Optional focal player ID. When supplied, only exact shared-court "
            "overlap between that player and opponents is returned."
        ),
    ),
):
    try:
        return get_game_opponent_overlap(
            game_id,
            season,
            player_id=player_id,
        )
    except ValueError as exc:
        raise _value_error(exc) from exc
    except WNBAMatchupContextNotFoundError as exc:
        raise _not_found(exc) from exc
    except WNBAMatchupContextUpstreamError as exc:
        raise _upstream(exc) from exc


@router.get("/players/{player_id}/opponent-overlap-context")
def player_opponent_overlap_context(
    player_id: int,
    season: int = Query(default=CURRENT_SUPPORTED_SEASON),
    season_type: str = Query(
        default="Regular Season",
        description="Allowed: " + ", ".join(ALLOWED_SEASON_TYPES),
    ),
    last_n_games: int = Query(
        default=5,
        description="Recent official player-game-log window, 1-20.",
    ),
    opponent_player_id: int | None = Query(
        default=None,
        description=(
            "Optional opposing player ID. This filters shared-court time only; "
            "it does not imply a defender assignment."
        ),
    ),
):
    try:
        return get_player_recent_opponent_overlap_context(
            player_id,
            season,
            season_type=season_type,
            last_n_games=last_n_games,
            opponent_player_id=opponent_player_id,
        )
    except ValueError as exc:
        raise _value_error(exc) from exc
    except WNBAMatchupContextNotFoundError as exc:
        raise _not_found(exc) from exc
    except WNBAMatchupContextUpstreamError as exc:
        raise _upstream(exc) from exc
