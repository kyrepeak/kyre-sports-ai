from fastapi import APIRouter, HTTPException, Query

from sports_api.wnba_availability import (
    MAX_DISCOVERY_LOOKBACK_HOURS,
    WNBAAvailabilityNotFoundError,
    WNBAAvailabilityUpstreamError,
    get_game_availability_context_dataset,
    get_latest_injury_report_dataset,
    get_team_availability_context_dataset,
)
from sports_api.wnba_league import CURRENT_SUPPORTED_SEASON

router = APIRouter(prefix="/api/v1/wnba", tags=["wnba"])


def _value_error(exc: ValueError) -> HTTPException:
    message = str(exc)
    status_code = 400 if "report_url" in message else 422
    return HTTPException(status_code=status_code, detail=message)


def _not_found_error(exc: WNBAAvailabilityNotFoundError) -> HTTPException:
    return HTTPException(status_code=404, detail=str(exc))


def _upstream_error(exc: WNBAAvailabilityUpstreamError) -> HTTPException:
    return HTTPException(status_code=502, detail=str(exc))


@router.get("/injuries/report")
def get_injury_report(
    season: int = Query(
        default=CURRENT_SUPPORTED_SEASON,
        description="WNBA season. Step 4I currently supports the verified 2026 season.",
    ),
    report_url: str | None = Query(
        default=None,
        description=(
            "Optional exact official WNBA injury-report PDF URL. If omitted, "
            "the API discovers the latest report in the configured lookback window."
        ),
    ),
    lookback_hours: int = Query(
        default=36,
        ge=1,
        le=MAX_DISCOVERY_LOOKBACK_HOURS,
        description="How far back to probe quarter-hour official report slots when report_url is omitted.",
    ),
):
    try:
        return get_latest_injury_report_dataset(
            season,
            report_url=report_url,
            lookback_hours=lookback_hours,
        )
    except ValueError as exc:
        raise _value_error(exc) from exc
    except WNBAAvailabilityNotFoundError as exc:
        raise _not_found_error(exc) from exc
    except WNBAAvailabilityUpstreamError as exc:
        raise _upstream_error(exc) from exc


@router.get("/teams/{team_key}/availability-context")
def get_team_availability_context(
    team_key: str,
    season: int = Query(
        default=CURRENT_SUPPORTED_SEASON,
        description="WNBA season. Step 4I currently supports the verified 2026 season.",
    ),
    last_n_games: int = Query(
        default=5,
        ge=1,
        le=20,
        description="Observed recent-game window used for rotation ranking (1-20).",
    ),
    report_url: str | None = Query(
        default=None,
        description="Optional exact official WNBA injury-report PDF URL.",
    ),
    lookback_hours: int = Query(
        default=36,
        ge=1,
        le=MAX_DISCOVERY_LOOKBACK_HOURS,
        description="Official injury-report discovery lookback when report_url is omitted.",
    ),
):
    try:
        return get_team_availability_context_dataset(
            team_key,
            season,
            last_n_games=last_n_games,
            report_url=report_url,
            lookback_hours=lookback_hours,
        )
    except ValueError as exc:
        raise _value_error(exc) from exc
    except WNBAAvailabilityNotFoundError as exc:
        raise _not_found_error(exc) from exc
    except WNBAAvailabilityUpstreamError as exc:
        raise _upstream_error(exc) from exc


@router.get("/games/{game_id}/availability-context")
def get_game_availability_context(
    game_id: str,
    date: str = Query(
        ...,
        description="Official WNBA schedule date in YYYY-MM-DD format.",
    ),
    season: int = Query(
        default=CURRENT_SUPPORTED_SEASON,
        description="WNBA season. Step 4I currently supports the verified 2026 season.",
    ),
    last_n_games: int = Query(
        default=5,
        ge=1,
        le=20,
        description="Observed recent-game window used for rotation ranking (1-20).",
    ),
    report_url: str | None = Query(
        default=None,
        description="Optional exact official WNBA injury-report PDF URL.",
    ),
    lookback_hours: int = Query(
        default=36,
        ge=1,
        le=MAX_DISCOVERY_LOOKBACK_HOURS,
        description="Official injury-report discovery lookback when report_url is omitted.",
    ),
):
    try:
        return get_game_availability_context_dataset(
            game_id,
            date,
            season,
            last_n_games=last_n_games,
            report_url=report_url,
            lookback_hours=lookback_hours,
        )
    except ValueError as exc:
        raise _value_error(exc) from exc
    except WNBAAvailabilityNotFoundError as exc:
        raise _not_found_error(exc) from exc
    except WNBAAvailabilityUpstreamError as exc:
        raise _upstream_error(exc) from exc
