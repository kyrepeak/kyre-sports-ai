from fastapi import APIRouter, HTTPException, Query

from sports_api.wnba_league import (
    CURRENT_SUPPORTED_SEASON,
    OFFICIAL_SOURCE,
    OFFICIAL_SOURCE_URL,
    SUPPORTED_SEASONS,
    get_wnba_league_structure,
    get_wnba_teams,
)

router = APIRouter(prefix="/api/v1/wnba", tags=["wnba"])


def _unsupported_season_error(exc: ValueError) -> HTTPException:
    return HTTPException(status_code=422, detail=str(exc))


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
