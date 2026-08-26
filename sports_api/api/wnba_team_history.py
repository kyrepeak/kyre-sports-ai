from fastapi import APIRouter, HTTPException, Query

from sports_api.wnba_game_history import ALLOWED_SEASON_TYPES
from sports_api.wnba_league import CURRENT_SUPPORTED_SEASON
from sports_api.wnba_team_history import (
    ALLOWED_LOCATIONS,
    WNBATeamHistoryNotFoundError,
    WNBATeamHistoryUpstreamError,
    get_head_to_head_dataset,
    get_team_game_log_dataset,
    get_team_recent_form_dataset,
)

router = APIRouter(prefix="/api/v1/wnba", tags=["wnba"])


def _value_error(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=422, detail=str(exc))


def _not_found_error(exc: WNBATeamHistoryNotFoundError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


def _upstream_error(exc: WNBATeamHistoryUpstreamError) -> HTTPException:
    return HTTPException(status_code=502, detail=str(exc))


@router.get("/teams/{team_key}/game-log")
def get_team_game_log(
    team_key: str,
    season: int = Query(
        default=CURRENT_SUPPORTED_SEASON,
        description="WNBA season. Step 4J currently supports the verified 2026 season.",
    ),
    season_type: str = Query(
        default="Regular Season",
        description="WNBA season type. Allowed values: " + ", ".join(ALLOWED_SEASON_TYPES),
    ),
    last_n_games: int = Query(
        default=0,
        ge=0,
        le=100,
        description="0 = full season-to-date; otherwise return the most recent N games.",
    ),
    location: str = Query(
        default="All",
        description="Location filter. Allowed values: " + ", ".join(ALLOWED_LOCATIONS),
    ),
    opponent_team_key: str | None = Query(
        default=None,
        description="Optional stable Step-4A opponent team key.",
    ),
):
    try:
        return get_team_game_log_dataset(
            team_key,
            season,
            season_type=season_type,
            last_n_games=last_n_games,
            location=location,
            opponent_team_key=opponent_team_key,
        )
    except ValueError as exc:
        raise _value_error(exc) from exc
    except WNBATeamHistoryNotFoundError as exc:
        raise _not_found_error(exc) from exc
    except WNBATeamHistoryUpstreamError as exc:
        raise _upstream_error(exc) from exc


@router.get("/teams/{team_key}/recent-form")
def get_team_recent_form(
    team_key: str,
    season: int = Query(
        default=CURRENT_SUPPORTED_SEASON,
        description="WNBA season. Step 4J currently supports the verified 2026 season.",
    ),
    season_type: str = Query(
        default="Regular Season",
        description="WNBA season type. Allowed values: " + ", ".join(ALLOWED_SEASON_TYPES),
    ),
    last_n_games: int = Query(
        default=5,
        ge=1,
        le=100,
        description="Observed recent-form window (1-100 games).",
    ),
    location: str = Query(
        default="All",
        description="Location filter. Allowed values: " + ", ".join(ALLOWED_LOCATIONS),
    ),
):
    try:
        return get_team_recent_form_dataset(
            team_key,
            season,
            season_type=season_type,
            last_n_games=last_n_games,
            location=location,
        )
    except ValueError as exc:
        raise _value_error(exc) from exc
    except WNBATeamHistoryNotFoundError as exc:
        raise _not_found_error(exc) from exc
    except WNBATeamHistoryUpstreamError as exc:
        raise _upstream_error(exc) from exc


@router.get("/teams/{team_key}/head-to-head/{opponent_team_key}")
def get_head_to_head(
    team_key: str,
    opponent_team_key: str,
    season: int = Query(
        default=CURRENT_SUPPORTED_SEASON,
        description="WNBA season. Step 4J currently supports the verified 2026 season.",
    ),
    season_type: str = Query(
        default="Regular Season",
        description="WNBA season type. Allowed values: " + ", ".join(ALLOWED_SEASON_TYPES),
    ),
    last_n_games: int = Query(
        default=0,
        ge=0,
        le=100,
        description="0 = all meetings in the selected season; otherwise most recent N.",
    ),
    location: str = Query(
        default="All",
        description="Location from the first team's perspective. Allowed values: "
        + ", ".join(ALLOWED_LOCATIONS),
    ),
):
    try:
        return get_head_to_head_dataset(
            team_key,
            opponent_team_key,
            season,
            season_type=season_type,
            last_n_games=last_n_games,
            location=location,
        )
    except ValueError as exc:
        raise _value_error(exc) from exc
    except WNBATeamHistoryNotFoundError as exc:
        raise _not_found_error(exc) from exc
    except WNBATeamHistoryUpstreamError as exc:
        raise _upstream_error(exc) from exc
