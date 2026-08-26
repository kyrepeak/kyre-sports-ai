from fastapi import APIRouter, HTTPException, Query

from sports_api.wnba_league import (
    CURRENT_SUPPORTED_SEASON,
    OFFICIAL_SOURCE,
    OFFICIAL_SOURCE_URL,
    SUPPORTED_SEASONS,
    get_wnba_league_structure,
    get_wnba_teams,
)
from sports_api.wnba_rosters import (
    WNBAEntityNotFoundError,
    WNBAStatsUpstreamError,
    get_current_players_dataset,
    get_player_profile_dataset,
    get_team_roster_dataset,
)

router = APIRouter(prefix="/api/v1/wnba", tags=["wnba"])


def _unsupported_season_error(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=422, detail=str(exc))


def _not_found_error(exc: WNBAEntityNotFoundError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


def _upstream_error(exc: WNBAStatsUpstreamError) -> HTTPException:
    return HTTPException(status_code=502, detail=str(exc))


@router.get("/teams")
def get_teams(
    season: int = Query(
        default=CURRENT_SUPPORTED_SEASON,
        description="WNBA season. Step 4A currently loads the verified 2026 alignment only.",
    )
):
    try:
        teams = get_wnba_teams(season)
    except ValueError as exc:
        raise _unsupported_season_error(exc) from exc

    return {
        "source": OFFICIAL_SOURCE,
        "source_url": OFFICIAL_SOURCE_URL,
        "data_type": "official_league_structure",
        "season": season,
        "supported_seasons": list(SUPPORTED_SEASONS),
        "team_count": len(teams),
        "teams": teams,
    }


@router.get("/league")
def get_league(
    season: int = Query(
        default=CURRENT_SUPPORTED_SEASON,
        description="WNBA season. Step 4A currently loads the verified 2026 alignment only.",
    )
):
    try:
        league = get_wnba_league_structure(season)
    except ValueError as exc:
        raise _unsupported_season_error(exc) from exc

    return {
        "source": OFFICIAL_SOURCE,
        "source_url": OFFICIAL_SOURCE_URL,
        "data_type": "official_league_structure",
        "supported_seasons": list(SUPPORTED_SEASONS),
        **league,
    }


@router.get("/players")
def get_players(
    season: int = Query(
        default=CURRENT_SUPPORTED_SEASON,
        description="WNBA season. Step 4B currently supports the verified 2026 season.",
    ),
    current_roster_only: bool = Query(
        default=True,
        description=(
            "When true, return only players whose official WNBA roster status is current "
            "and whose team maps to the Step 4A league registry."
        ),
    ),
):
    try:
        return get_current_players_dataset(
            season,
            current_roster_only=current_roster_only,
        )
    except ValueError as exc:
        raise _unsupported_season_error(exc) from exc
    except WNBAStatsUpstreamError as exc:
        raise _upstream_error(exc) from exc


@router.get("/players/{player_id}")
def get_player(player_id: int):
    try:
        return get_player_profile_dataset(player_id)
    except WNBAEntityNotFoundError as exc:
        raise _not_found_error(exc) from exc
    except WNBAStatsUpstreamError as exc:
        raise _upstream_error(exc) from exc


@router.get("/teams/{team_key}/roster")
def get_team_roster(
    team_key: str,
    season: int = Query(
        default=CURRENT_SUPPORTED_SEASON,
        description="WNBA season. Step 4B currently supports the verified 2026 season.",
    ),
):
    try:
        return get_team_roster_dataset(team_key, season)
    except ValueError as exc:
        raise _unsupported_season_error(exc) from exc
    except WNBAEntityNotFoundError as exc:
        raise _not_found_error(exc) from exc
    except WNBAStatsUpstreamError as exc:
        raise _upstream_error(exc) from exc
