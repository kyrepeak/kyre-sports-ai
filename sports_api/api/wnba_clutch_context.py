from fastapi import APIRouter, HTTPException, Query

from sports_api.wnba_clutch_context import (
    ALLOWED_AHEAD_BEHIND,
    ALLOWED_CLUTCH_TIMES,
    ALLOWED_PER_MODES,
    WNBAClutchNotFoundError,
    WNBAClutchUpstreamError,
    get_player_clutch_context,
    get_player_clutch_dataset,
    get_team_clutch_context,
    get_team_clutch_dataset,
)
from sports_api.wnba_game_history import ALLOWED_SEASON_TYPES
from sports_api.wnba_league import CURRENT_SUPPORTED_SEASON

router = APIRouter(prefix="/api/v1/wnba", tags=["wnba"])


def _value_error(exc: ValueError) -> HTTPException:
    message = str(exc)
    status_code = 400 if "player_id must be a positive integer" in message else 422
    return HTTPException(status_code=status_code, detail=message)


def _not_found(exc: WNBAClutchNotFoundError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


def _upstream(exc: WNBAClutchUpstreamError) -> HTTPException:
    return HTTPException(status_code=502, detail=str(exc))


def _common_kwargs(
    season_type: str,
    clutch_time: str,
    point_diff: int,
    ahead_behind: str,
    last_n_games: int,
    per_mode: str,
    period: int,
    location: str,
    outcome: str,
) -> dict:
    return {
        "season_type": season_type,
        "clutch_time": clutch_time,
        "point_diff": point_diff,
        "ahead_behind": ahead_behind,
        "last_n_games": last_n_games,
        "per_mode": per_mode,
        "period": period,
        "location": location,
        "outcome": outcome,
    }


@router.get("/stats/clutch/players")
def player_clutch_stats(
    season: int = Query(default=CURRENT_SUPPORTED_SEASON),
    season_type: str = Query(default="Regular Season", description="Allowed: " + ", ".join(ALLOWED_SEASON_TYPES)),
    clutch_time: str = Query(default="Last 5 Minutes", description="Allowed: " + ", ".join(ALLOWED_CLUTCH_TIMES)),
    point_diff: int = Query(default=5, description="Score-difference threshold, 1-20 points."),
    ahead_behind: str = Query(default="Ahead or Behind", description="Allowed: " + ", ".join(ALLOWED_AHEAD_BEHIND)),
    last_n_games: int = Query(default=0, description="0 = season-to-date; otherwise official LastNGames 1-100."),
    per_mode: str = Query(default="Totals", description="Allowed: " + ", ".join(ALLOWED_PER_MODES)),
    period: int = Query(default=0, description="0 = all periods; 1-4 regulation; 5+ overtime periods."),
    location: str = Query(default="", description="Blank, Home, or Road."),
    outcome: str = Query(default="", description="Blank, W, or L."),
    team_key: str | None = Query(default=None, description="Optional stable Step-4A team key."),
    player_id: int | None = Query(default=None, description="Optional official WNBA player ID."),
):
    try:
        return get_player_clutch_dataset(
            season,
            team_key=team_key,
            player_id=player_id,
            **_common_kwargs(
                season_type, clutch_time, point_diff, ahead_behind,
                last_n_games, per_mode, period, location, outcome,
            ),
        )
    except ValueError as exc:
        raise _value_error(exc) from exc
    except WNBAClutchUpstreamError as exc:
        raise _upstream(exc) from exc


@router.get("/stats/clutch/teams")
def team_clutch_stats(
    season: int = Query(default=CURRENT_SUPPORTED_SEASON),
    season_type: str = Query(default="Regular Season"),
    clutch_time: str = Query(default="Last 5 Minutes"),
    point_diff: int = Query(default=5),
    ahead_behind: str = Query(default="Ahead or Behind"),
    last_n_games: int = Query(default=0),
    per_mode: str = Query(default="Totals"),
    period: int = Query(default=0),
    location: str = Query(default=""),
    outcome: str = Query(default=""),
    team_key: str | None = Query(default=None),
):
    try:
        return get_team_clutch_dataset(
            season,
            team_key=team_key,
            **_common_kwargs(
                season_type, clutch_time, point_diff, ahead_behind,
                last_n_games, per_mode, period, location, outcome,
            ),
        )
    except ValueError as exc:
        raise _value_error(exc) from exc
    except WNBAClutchUpstreamError as exc:
        raise _upstream(exc) from exc


@router.get("/players/{player_id}/clutch-context")
def player_clutch_context(
    player_id: int,
    season: int = Query(default=CURRENT_SUPPORTED_SEASON),
    season_type: str = Query(default="Regular Season"),
    clutch_time: str = Query(default="Last 5 Minutes"),
    point_diff: int = Query(default=5),
    ahead_behind: str = Query(default="Ahead or Behind"),
    last_n_games: int = Query(default=0),
    per_mode: str = Query(default="Totals"),
    period: int = Query(default=0),
    location: str = Query(default=""),
    outcome: str = Query(default=""),
):
    try:
        return get_player_clutch_context(
            player_id,
            season,
            **_common_kwargs(
                season_type, clutch_time, point_diff, ahead_behind,
                last_n_games, per_mode, period, location, outcome,
            ),
        )
    except ValueError as exc:
        raise _value_error(exc) from exc
    except WNBAClutchNotFoundError as exc:
        raise _not_found(exc) from exc
    except WNBAClutchUpstreamError as exc:
        raise _upstream(exc) from exc


@router.get("/teams/{team_key}/clutch-context")
def team_clutch_context(
    team_key: str,
    season: int = Query(default=CURRENT_SUPPORTED_SEASON),
    season_type: str = Query(default="Regular Season"),
    clutch_time: str = Query(default="Last 5 Minutes"),
    point_diff: int = Query(default=5),
    ahead_behind: str = Query(default="Ahead or Behind"),
    last_n_games: int = Query(default=0),
    per_mode: str = Query(default="Totals"),
    period: int = Query(default=0),
    location: str = Query(default=""),
    outcome: str = Query(default=""),
):
    try:
        return get_team_clutch_context(
            team_key,
            season,
            **_common_kwargs(
                season_type, clutch_time, point_diff, ahead_behind,
                last_n_games, per_mode, period, location, outcome,
            ),
        )
    except ValueError as exc:
        raise _value_error(exc) from exc
    except WNBAClutchNotFoundError as exc:
        raise _not_found(exc) from exc
    except WNBAClutchUpstreamError as exc:
        raise _upstream(exc) from exc
