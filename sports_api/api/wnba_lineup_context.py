from fastapi import APIRouter, HTTPException, Query

from sports_api.wnba_game_history import ALLOWED_SEASON_TYPES
from sports_api.wnba_league import CURRENT_SUPPORTED_SEASON
from sports_api.wnba_lineup_context import (
    WNBALineupContextNotFoundError,
    WNBALineupContextUpstreamError,
    get_lineups_dataset,
    get_player_role_context_dataset,
    get_team_on_off_dataset,
)
from sports_api.wnba_season_stats import ALLOWED_PER_MODES

router = APIRouter(prefix="/api/v1/wnba", tags=["wnba"])


def _value_error(exc: ValueError) -> HTTPException:
    message = str(exc)
    status_code = 400 if "player_id must be a positive integer" in message else 422
    return HTTPException(status_code=status_code, detail=message)


def _not_found_error(exc: WNBALineupContextNotFoundError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


def _upstream_error(exc: WNBALineupContextUpstreamError) -> HTTPException:
    return HTTPException(status_code=502, detail=str(exc))


@router.get("/lineups")
def get_lineups(
    season: int = Query(
        default=CURRENT_SUPPORTED_SEASON,
        description="WNBA season. Step 4G currently supports the verified 2026 season.",
    ),
    season_type: str = Query(
        default="Regular Season",
        description="WNBA season type. Allowed values: " + ", ".join(ALLOWED_SEASON_TYPES),
    ),
    group_quantity: int = Query(
        default=5,
        ge=2,
        le=5,
        description="Number of players in each official lineup group (2-5).",
    ),
    last_n_games: int = Query(
        default=0,
        ge=0,
        le=100,
        description="0 = season-to-date; otherwise official LastNGames window (1-100).",
    ),
    per_mode: str = Query(
        default="PerGame",
        description="Output mode. Allowed values: " + ", ".join(ALLOWED_PER_MODES),
    ),
    team_key: str | None = Query(
        default=None,
        description="Optional stable Step-4A team key. When supplied, the official team ID is resolved first.",
    ),
    player_id: int | None = Query(
        default=None,
        description="Optional official WNBA player ID used to keep lineups containing that player.",
    ),
):
    try:
        return get_lineups_dataset(
            season,
            season_type=season_type,
            group_quantity=group_quantity,
            last_n_games=last_n_games,
            per_mode=per_mode,
            team_key=team_key,
            player_id=player_id,
        )
    except ValueError as exc:
        raise _value_error(exc) from exc
    except WNBALineupContextUpstreamError as exc:
        raise _upstream_error(exc) from exc


@router.get("/teams/{team_key}/on-off")
def get_team_on_off(
    team_key: str,
    season: int = Query(
        default=CURRENT_SUPPORTED_SEASON,
        description="WNBA season. Step 4G currently supports the verified 2026 season.",
    ),
    season_type: str = Query(
        default="Regular Season",
        description="WNBA season type. Allowed values: " + ", ".join(ALLOWED_SEASON_TYPES),
    ),
    last_n_games: int = Query(
        default=0,
        ge=0,
        le=100,
        description="0 = season-to-date; otherwise official LastNGames window (1-100).",
    ),
    per_mode: str = Query(
        default="Totals",
        description="Output mode. Allowed values: " + ", ".join(ALLOWED_PER_MODES),
    ),
):
    try:
        return get_team_on_off_dataset(
            team_key,
            season,
            season_type=season_type,
            last_n_games=last_n_games,
            per_mode=per_mode,
        )
    except ValueError as exc:
        raise _value_error(exc) from exc
    except WNBALineupContextUpstreamError as exc:
        raise _upstream_error(exc) from exc


@router.get("/players/{player_id}/role-context")
def get_player_role_context(
    player_id: int,
    season: int = Query(
        default=CURRENT_SUPPORTED_SEASON,
        description="WNBA season. Step 4G currently supports the verified 2026 season.",
    ),
    season_type: str = Query(
        default="Regular Season",
        description="WNBA season type. Allowed values: " + ", ".join(ALLOWED_SEASON_TYPES),
    ),
    last_n_games: int = Query(
        default=0,
        ge=0,
        le=100,
        description="0 = season-to-date; otherwise official LastNGames window (1-100).",
    ),
    per_mode: str = Query(
        default="PerGame",
        description="Output mode. Allowed values: " + ", ".join(ALLOWED_PER_MODES),
    ),
):
    try:
        return get_player_role_context_dataset(
            player_id,
            season,
            season_type=season_type,
            last_n_games=last_n_games,
            per_mode=per_mode,
        )
    except ValueError as exc:
        raise _value_error(exc) from exc
    except WNBALineupContextNotFoundError as exc:
        raise _not_found_error(exc) from exc
    except WNBALineupContextUpstreamError as exc:
        raise _upstream_error(exc) from exc
