from fastapi import APIRouter, HTTPException, Query

from sports_api.wnba_game_history import ALLOWED_SEASON_TYPES
from sports_api.wnba_league import CURRENT_SUPPORTED_SEASON
from sports_api.wnba_shot_context import (
    WNBAShotContextNotFoundError,
    WNBAShotContextUpstreamError,
    get_opponent_defense_by_shot_zone_dataset,
    get_player_shot_chart_dataset,
    get_team_shot_zones_dataset,
)

router = APIRouter(prefix="/api/v1/wnba", tags=["wnba"])


def _value_error(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=422, detail=str(exc))


def _not_found_error(exc: WNBAShotContextNotFoundError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


def _upstream_error(exc: WNBAShotContextUpstreamError) -> HTTPException:
    return HTTPException(status_code=502, detail=str(exc))


@router.get("/players/{player_id}/shot-chart")
def get_player_shot_chart(
    player_id: int,
    season: int = Query(
        default=CURRENT_SUPPORTED_SEASON,
        description="WNBA season. Step 4L currently supports the verified 2026 season.",
    ),
    season_type: str = Query(
        default="Regular Season",
        description="WNBA season type. Allowed values: " + ", ".join(ALLOWED_SEASON_TYPES),
    ),
    last_n_games: int = Query(
        default=0,
        ge=0,
        le=100,
        description="0 = season-to-date; otherwise use the official LastNGames filter.",
    ),
    opponent_team_key: str | None = Query(
        default=None,
        description="Optional stable Step-4A opponent team key.",
    ),
):
    try:
        return get_player_shot_chart_dataset(
            player_id,
            season,
            season_type=season_type,
            last_n_games=last_n_games,
            opponent_team_key=opponent_team_key,
        )
    except ValueError as exc:
        raise _value_error(exc) from exc
    except WNBAShotContextNotFoundError as exc:
        raise _not_found_error(exc) from exc
    except WNBAShotContextUpstreamError as exc:
        raise _upstream_error(exc) from exc


@router.get("/teams/{team_key}/shot-zones")
def get_team_shot_zones(
    team_key: str,
    season: int = Query(
        default=CURRENT_SUPPORTED_SEASON,
        description="WNBA season. Step 4L currently supports the verified 2026 season.",
    ),
    season_type: str = Query(
        default="Regular Season",
        description="WNBA season type. Allowed values: " + ", ".join(ALLOWED_SEASON_TYPES),
    ),
    last_n_games: int = Query(
        default=0,
        ge=0,
        le=100,
        description="0 = season-to-date; otherwise use the official LastNGames filter.",
    ),
):
    try:
        return get_team_shot_zones_dataset(
            team_key,
            season,
            season_type=season_type,
            last_n_games=last_n_games,
        )
    except ValueError as exc:
        raise _value_error(exc) from exc
    except WNBAShotContextNotFoundError as exc:
        raise _not_found_error(exc) from exc
    except WNBAShotContextUpstreamError as exc:
        raise _upstream_error(exc) from exc


@router.get("/teams/{team_key}/defense-by-shot-zone")
def get_opponent_defense_by_shot_zone(
    team_key: str,
    season: int = Query(
        default=CURRENT_SUPPORTED_SEASON,
        description="WNBA season. Step 4L currently supports the verified 2026 season.",
    ),
    season_type: str = Query(
        default="Regular Season",
        description="WNBA season type. Allowed values: " + ", ".join(ALLOWED_SEASON_TYPES),
    ),
    last_n_games: int = Query(
        default=0,
        ge=0,
        le=100,
        description=(
            "Official source LastNGames filter. This is exposed as source semantics, "
            "not relabeled as a custom defensive-window calculation."
        ),
    ),
):
    try:
        return get_opponent_defense_by_shot_zone_dataset(
            team_key,
            season,
            season_type=season_type,
            last_n_games=last_n_games,
        )
    except ValueError as exc:
        raise _value_error(exc) from exc
    except WNBAShotContextNotFoundError as exc:
        raise _not_found_error(exc) from exc
    except WNBAShotContextUpstreamError as exc:
        raise _upstream_error(exc) from exc
