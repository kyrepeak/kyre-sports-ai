from fastapi import APIRouter, HTTPException, Query

from sports_api.wnba_game_history import WNBAHistoryUpstreamError
from sports_api.wnba_league import CURRENT_SUPPORTED_SEASON
from sports_api.wnba_rosters import WNBAStatsUpstreamError
from sports_api.wnba_team_history import WNBATeamHistoryUpstreamError
from sports_api.wnba_defensive_activity import (
    WNBADefensiveActivityNotFoundError,
    WNBADefensiveActivityUpstreamError,
    get_game_defensive_tracking,
    get_hustle_source_status,
    get_player_defensive_tracking,
    get_team_defensive_tracking,
)

router = APIRouter(prefix="/api/v1/wnba", tags=["wnba-defensive-activity"])


def _raise_http(exc: Exception) -> None:
    if isinstance(exc, WNBADefensiveActivityNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if isinstance(
        exc,
        (
            WNBADefensiveActivityUpstreamError,
            WNBAStatsUpstreamError,
            WNBAHistoryUpstreamError,
            WNBATeamHistoryUpstreamError,
        ),
    ):
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    raise exc


@router.get("/hustle/source-status")
def hustle_source_status(
    season: int = Query(CURRENT_SUPPORTED_SEASON),
):
    try:
        return get_hustle_source_status(season)
    except Exception as exc:
        _raise_http(exc)


@router.get("/games/{game_id}/defensive-tracking")
def game_defensive_tracking(
    game_id: str,
    season: int = Query(CURRENT_SUPPORTED_SEASON),
):
    try:
        return get_game_defensive_tracking(game_id, season)
    except Exception as exc:
        _raise_http(exc)


@router.get("/players/{player_id}/defensive-tracking")
def player_defensive_tracking(
    player_id: int,
    season: int = Query(CURRENT_SUPPORTED_SEASON),
    season_type: str = Query("Regular Season"),
    last_n_games: int = Query(5, ge=1, le=20),
):
    try:
        return get_player_defensive_tracking(
            player_id,
            season,
            season_type=season_type,
            last_n_games=last_n_games,
        )
    except Exception as exc:
        _raise_http(exc)


@router.get("/teams/{team_key}/defensive-tracking")
def team_defensive_tracking(
    team_key: str,
    season: int = Query(CURRENT_SUPPORTED_SEASON),
    season_type: str = Query("Regular Season"),
    last_n_games: int = Query(5, ge=1, le=20),
):
    try:
        return get_team_defensive_tracking(
            team_key,
            season,
            season_type=season_type,
            last_n_games=last_n_games,
        )
    except Exception as exc:
        _raise_http(exc)
