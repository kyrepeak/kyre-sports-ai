from fastapi import APIRouter, HTTPException, Query

from sports_api.wnba_game_history import ALLOWED_SEASON_TYPES
from sports_api.wnba_league import CURRENT_SUPPORTED_SEASON
from sports_api.wnba_player_event_features import (
    WNBAPlayerEventFeatureNotFoundError,
    WNBAPlayerEventFeatureUpstreamError,
    get_game_player_event_features,
    get_player_recent_event_feature_context,
)

router = APIRouter(prefix="/api/v1/wnba", tags=["wnba"])


def _value_error(exc: ValueError) -> HTTPException:
    message = str(exc)
    status_code = 400 if (
        "game_id must be exactly 10 numeric digits" in message
        or "player_id must be a positive integer" in message
    ) else 422
    return HTTPException(status_code=status_code, detail=message)


def _not_found(exc: WNBAPlayerEventFeatureNotFoundError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


def _upstream(exc: WNBAPlayerEventFeatureUpstreamError) -> HTTPException:
    return HTTPException(status_code=502, detail=str(exc))


@router.get("/games/{game_id}/player-event-features")
def game_player_event_features(
    game_id: str,
    season: int = Query(
        default=CURRENT_SUPPORTED_SEASON,
        description=(
            "WNBA season. Builds descriptive player event/floor-context features "
            "from Step 4T exact event lineups and derived possession segments."
        ),
    ),
    player_id: int | None = Query(
        default=None,
        description=(
            "Optional focal player ID. Omit to return every player observed in "
            "reconstructed Step 4T event lineups for the game."
        ),
    ),
):
    try:
        return get_game_player_event_features(
            game_id,
            season,
            player_id=player_id,
        )
    except ValueError as exc:
        raise _value_error(exc) from exc
    except WNBAPlayerEventFeatureNotFoundError as exc:
        raise _not_found(exc) from exc
    except WNBAPlayerEventFeatureUpstreamError as exc:
        raise _upstream(exc) from exc


@router.get("/players/{player_id}/event-feature-context")
def player_recent_event_feature_context(
    player_id: int,
    season: int = Query(default=CURRENT_SUPPORTED_SEASON),
    season_type: str = Query(
        default="Regular Season",
        description="Allowed: " + ", ".join(ALLOWED_SEASON_TYPES),
    ),
    last_n_games: int = Query(
        default=5,
        ge=1,
        le=20,
        description="Recent official player-game-log window, 1-20 games.",
    ),
):
    try:
        return get_player_recent_event_feature_context(
            player_id,
            season,
            season_type=season_type,
            last_n_games=last_n_games,
        )
    except ValueError as exc:
        raise _value_error(exc) from exc
    except WNBAPlayerEventFeatureNotFoundError as exc:
        raise _not_found(exc) from exc
    except WNBAPlayerEventFeatureUpstreamError as exc:
        raise _upstream(exc) from exc
