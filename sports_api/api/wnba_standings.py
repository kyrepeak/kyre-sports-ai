from fastapi import APIRouter, HTTPException, Query

from sports_api.wnba_league import CURRENT_SUPPORTED_SEASON
from sports_api.wnba_standings import (
    ALLOWED_STANDINGS_SEASON_TYPES,
    WNBAStandingsNotFoundError,
    WNBAStandingsUpstreamError,
    get_conference_standings_dataset,
    get_standings_dataset,
    get_team_standings_context_dataset,
)

router = APIRouter(prefix="/api/v1/wnba", tags=["wnba"])


def _value_error(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=422, detail=str(exc))


def _not_found_error(exc: WNBAStandingsNotFoundError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


def _upstream_error(exc: WNBAStandingsUpstreamError) -> HTTPException:
    return HTTPException(status_code=502, detail=str(exc))


@router.get("/standings")
def get_wnba_standings(
    season: int = Query(
        default=CURRENT_SUPPORTED_SEASON,
        description="WNBA season. Step 4M currently supports the verified 2026 season.",
    ),
    season_type: str = Query(
        default="Regular Season",
        description=(
            "Standings season type. Allowed values: "
            + ", ".join(ALLOWED_STANDINGS_SEASON_TYPES)
        ),
    ),
):
    try:
        return get_standings_dataset(season, season_type=season_type)
    except ValueError as exc:
        raise _value_error(exc) from exc
    except WNBAStandingsNotFoundError as exc:
        raise _not_found_error(exc) from exc
    except WNBAStandingsUpstreamError as exc:
        raise _upstream_error(exc) from exc


@router.get("/standings/conference/{conference}")
def get_wnba_conference_standings(
    conference: str,
    season: int = Query(
        default=CURRENT_SUPPORTED_SEASON,
        description="WNBA season. Step 4M currently supports the verified 2026 season.",
    ),
    season_type: str = Query(
        default="Regular Season",
        description=(
            "Standings season type. Allowed values: "
            + ", ".join(ALLOWED_STANDINGS_SEASON_TYPES)
        ),
    ),
):
    try:
        return get_conference_standings_dataset(
            conference, season, season_type=season_type
        )
    except ValueError as exc:
        raise _value_error(exc) from exc
    except WNBAStandingsNotFoundError as exc:
        raise _not_found_error(exc) from exc
    except WNBAStandingsUpstreamError as exc:
        raise _upstream_error(exc) from exc


@router.get("/teams/{team_key}/standings-context")
def get_wnba_team_standings_context(
    team_key: str,
    season: int = Query(
        default=CURRENT_SUPPORTED_SEASON,
        description="WNBA season. Step 4M currently supports the verified 2026 season.",
    ),
    season_type: str = Query(
        default="Regular Season",
        description=(
            "Standings season type. Allowed values: "
            + ", ".join(ALLOWED_STANDINGS_SEASON_TYPES)
        ),
    ),
):
    try:
        return get_team_standings_context_dataset(
            team_key, season, season_type=season_type
        )
    except ValueError as exc:
        raise _value_error(exc) from exc
    except WNBAStandingsNotFoundError as exc:
        raise _not_found_error(exc) from exc
    except WNBAStandingsUpstreamError as exc:
        raise _upstream_error(exc) from exc
