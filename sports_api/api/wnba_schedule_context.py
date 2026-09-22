from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query

from sports_api.wnba_league import CURRENT_SUPPORTED_SEASON
from sports_api.wnba_schedule import WNBAScheduleUpstreamError
from sports_api.wnba_schedule_context import (
    WNBARestTravelNotFoundError,
    WNBARestTravelUpstreamError,
    get_game_rest_travel_context,
    get_rest_travel_board,
    get_team_rest_travel_context,
)

router = APIRouter(prefix="/api/v1/wnba", tags=["wnba-rest-travel"])
ARIZONA_TZ = ZoneInfo("America/Phoenix")


def _today_arizona() -> str:
    return datetime.now(ARIZONA_TZ).date().isoformat()


def _raise_http(exc: Exception) -> None:
    if isinstance(exc, WNBARestTravelNotFoundError):
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    if isinstance(exc, ValueError):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if isinstance(exc, (WNBARestTravelUpstreamError, WNBAScheduleUpstreamError)):
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    raise exc


@router.get("/teams/{team_key}/rest-travel-context")
def team_rest_travel_context(
    team_key: str,
    season: int = Query(CURRENT_SUPPORTED_SEASON),
    date: str | None = Query(
        None,
        description="YYYY-MM-DD; defaults to current Arizona date.",
    ),
    include_observed_workload: bool = Query(True),
):
    try:
        return get_team_rest_travel_context(
            team_key,
            season,
            date or _today_arizona(),
            include_observed_workload=include_observed_workload,
        )
    except Exception as exc:
        _raise_http(exc)


@router.get("/games/{game_id}/rest-travel-context")
def game_rest_travel_context(
    game_id: str,
    season: int = Query(CURRENT_SUPPORTED_SEASON),
    include_observed_workload: bool = Query(True),
):
    try:
        return get_game_rest_travel_context(
            game_id,
            season,
            include_observed_workload=include_observed_workload,
        )
    except Exception as exc:
        _raise_http(exc)


@router.get("/rest-travel-board")
def rest_travel_board(
    season: int = Query(CURRENT_SUPPORTED_SEASON),
    date: str | None = Query(
        None,
        description="YYYY-MM-DD; defaults to current Arizona date.",
    ),
    games_only: bool = Query(True),
    include_observed_workload: bool = Query(False),
):
    try:
        return get_rest_travel_board(
            season,
            date or _today_arizona(),
            games_only=games_only,
            include_observed_workload=include_observed_workload,
        )
    except Exception as exc:
        _raise_http(exc)
