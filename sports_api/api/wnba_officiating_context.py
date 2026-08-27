from fastapi import APIRouter, HTTPException, Query

from sports_api.wnba_league import CURRENT_SUPPORTED_SEASON
from sports_api.wnba_officiating_context import (
    WNBAOfficiatingNotFoundError,
    WNBAOfficiatingUpstreamError,
    get_game_officials_dataset,
    get_game_whistle_context,
    get_player_foul_ft_context,
    get_team_foul_ft_context,
)

router = APIRouter(prefix="/api/v1/wnba", tags=["wnba-officiating"])


def _raise_http(exc: Exception) -> None:
    if isinstance(exc, WNBAOfficiatingNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if isinstance(exc, WNBAOfficiatingUpstreamError):
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    raise exc


@router.get("/games/{game_id}/officials")
def game_officials(
    game_id: str,
    season: int = Query(CURRENT_SUPPORTED_SEASON),
):
    try:
        return get_game_officials_dataset(game_id, season)
    except Exception as exc:
        _raise_http(exc)


@router.get("/teams/{team_key}/foul-free-throw-context")
def team_foul_free_throw_context(
    team_key: str,
    season: int = Query(CURRENT_SUPPORTED_SEASON),
    season_type: str = Query("Regular Season"),
    last_n_games: int = Query(0, ge=0, le=100),
):
    try:
        return get_team_foul_ft_context(
            team_key,
            season,
            season_type=season_type,
            last_n_games=last_n_games,
        )
    except Exception as exc:
        _raise_http(exc)


@router.get("/players/{player_id}/foul-free-throw-context")
def player_foul_free_throw_context(
    player_id: int,
    season: int = Query(CURRENT_SUPPORTED_SEASON),
    season_type: str = Query("Regular Season"),
    last_n_games: int = Query(0, ge=0, le=100),
):
    try:
        return get_player_foul_ft_context(
            player_id,
            season,
            season_type=season_type,
            last_n_games=last_n_games,
        )
    except Exception as exc:
        _raise_http(exc)


@router.get("/games/{game_id}/whistle-context")
def game_whistle_context(
    game_id: str,
    season: int = Query(CURRENT_SUPPORTED_SEASON),
    season_type: str = Query("Regular Season"),
    last_n_games: int = Query(0, ge=0, le=100),
):
    try:
        return get_game_whistle_context(
            game_id,
            season,
            season_type=season_type,
            last_n_games=last_n_games,
        )
    except Exception as exc:
        _raise_http(exc)
