from fastapi import APIRouter, HTTPException, Query

from sports_api.wnba_game_history import ALLOWED_SEASON_TYPES
from sports_api.wnba_league import CURRENT_SUPPORTED_SEASON
from sports_api.wnba_season_stats import ALLOWED_PER_MODES
from sports_api.wnba_tracking import (
    TRACKING_MEASURES,
    WNBATrackingNotFoundError,
    WNBATrackingUpstreamError,
    get_player_opportunity_context_dataset,
    get_player_tracking_dataset,
)

router = APIRouter(prefix="/api/v1/wnba", tags=["wnba"])


def _value_error(exc: ValueError) -> HTTPException:
    message = str(exc)
    status_code = 400 if "player_id must be a positive integer" in message else 422
    return HTTPException(status_code=status_code, detail=message)


def _not_found_error(exc: WNBATrackingNotFoundError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


def _upstream_error(exc: WNBATrackingUpstreamError) -> HTTPException:
    return HTTPException(status_code=502, detail=str(exc))


@router.get("/tracking/players")
def get_player_tracking(
    measure: str = Query(
        default="Passing",
        description="Official tracking measure. Allowed values: " + ", ".join(TRACKING_MEASURES),
    ),
    season: int = Query(
        default=CURRENT_SUPPORTED_SEASON,
        description="WNBA season. Step 4H currently supports the verified 2026 season.",
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
        return get_player_tracking_dataset(
            season,
            measure=measure,
            season_type=season_type,
            last_n_games=last_n_games,
            per_mode=per_mode,
            team_key=team_key,
            player_id=player_id,
        )
    except ValueError as exc:
        raise _value_error(exc) from exc
    except WNBATrackingUpstreamError as exc:
        raise _upstream_error(exc) from exc


@router.get("/players/{player_id}/opportunity-context")
def get_player_opportunity_context(
    player_id: int,
    season: int = Query(
        default=CURRENT_SUPPORTED_SEASON,
        description="WNBA season. Step 4H currently supports the verified 2026 season.",
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
        return get_player_opportunity_context_dataset(
            player_id,
            season,
            season_type=season_type,
            last_n_games=last_n_games,
            per_mode=per_mode,
        )
    except ValueError as exc:
        raise _value_error(exc) from exc
    except WNBATrackingNotFoundError as exc:
        raise _not_found_error(exc) from exc
    except WNBATrackingUpstreamError as exc:
        raise _upstream_error(exc) from exc
