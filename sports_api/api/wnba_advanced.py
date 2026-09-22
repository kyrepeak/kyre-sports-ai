from fastapi import APIRouter, HTTPException, Query

from sports_api.wnba_advanced_stats import (
    WNBAAdvancedStatsUpstreamError,
    get_player_advanced_stats_dataset,
    get_team_advanced_stats_dataset,
)
from sports_api.wnba_game_history import ALLOWED_SEASON_TYPES
from sports_api.wnba_league import CURRENT_SUPPORTED_SEASON
from sports_api.wnba_season_stats import ALLOWED_PER_MODES

router = APIRouter(prefix="/api/v1/wnba", tags=["wnba"])


def _value_error(exc: ValueError) -> HTTPException:
    message = str(exc)
    status_code = 400 if "player_id must be a positive integer" in message else 422
    return HTTPException(status_code=status_code, detail=message)


def _upstream_error(exc: WNBAAdvancedStatsUpstreamError) -> HTTPException:
    return HTTPException(status_code=502, detail=str(exc))


@router.get("/stats/advanced/players")
def get_player_advanced_stats(
    season: int = Query(
        default=CURRENT_SUPPORTED_SEASON,
        description="WNBA season. Step 4F currently supports the verified 2026 season.",
    ),
    season_type: str = Query(
        default="Regular Season",
        description="WNBA season type. Allowed values: " + ", ".join(ALLOWED_SEASON_TYPES),
    ),
    last_n_games: int = Query(
        default=0,
        description="0 = season-to-date; otherwise official LastNGames window (1-100).",
    ),
    per_mode: str = Query(
        default="PerGame",
        description="Output mode. Allowed values: " + ", ".join(ALLOWED_PER_MODES),
    ),
    team_key: str | None = Query(
        default=None,
        description="Optional stable Step-4A team key used as a post-fetch filter.",
    ),
    player_id: int | None = Query(
        default=None,
        description="Optional official WNBA player ID used as a post-fetch filter.",
    ),
):
    try:
        return get_player_advanced_stats_dataset(
            season,
            season_type=season_type,
            last_n_games=last_n_games,
            per_mode=per_mode,
            team_key=team_key,
            player_id=player_id,
        )
    except ValueError as exc:
        raise _value_error(exc) from exc
    except WNBAAdvancedStatsUpstreamError as exc:
        raise _upstream_error(exc) from exc


@router.get("/stats/advanced/teams")
def get_team_advanced_stats(
    season: int = Query(
        default=CURRENT_SUPPORTED_SEASON,
        description="WNBA season. Step 4F currently supports the verified 2026 season.",
    ),
    season_type: str = Query(
        default="Regular Season",
        description="WNBA season type. Allowed values: " + ", ".join(ALLOWED_SEASON_TYPES),
    ),
    last_n_games: int = Query(
        default=0,
        description="0 = season-to-date; otherwise official LastNGames window (1-100).",
    ),
    per_mode: str = Query(
        default="PerGame",
        description="Output mode. Allowed values: " + ", ".join(ALLOWED_PER_MODES),
    ),
    team_key: str | None = Query(
        default=None,
        description="Optional stable Step-4A team key used as a post-fetch filter.",
    ),
):
    try:
        return get_team_advanced_stats_dataset(
            season,
            season_type=season_type,
            last_n_games=last_n_games,
            per_mode=per_mode,
            team_key=team_key,
        )
    except ValueError as exc:
        raise _value_error(exc) from exc
    except WNBAAdvancedStatsUpstreamError as exc:
        raise _upstream_error(exc) from exc
