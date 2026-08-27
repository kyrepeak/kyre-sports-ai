"""GET-only FastAPI transport for WNBA Step 6N production observability."""
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from sports_api.wnba_league import CURRENT_SUPPORTED_SEASON
from sports_api.wnba_step6n_production_observability import (
    build_step6n_health,
    build_step6n_production_observability,
)

router = APIRouter(prefix="/api/v1/wnba", tags=["wnba"])


@router.get("/runtime/step6n-observability")
def get_step6n_observability(
    date: str | None = Query(default=None),
    season: int = Query(default=CURRENT_SUPPORTED_SEASON, ge=1),
):
    return build_step6n_production_observability(date=date, season=season)


@router.get("/runtime/step6n-health")
def get_step6n_health(
    date: str | None = Query(default=None),
    season: int = Query(default=CURRENT_SUPPORTED_SEASON, ge=1),
):
    report = build_step6n_health(date=date, season=season)
    # Safe-deferred and degraded are observable states, not process failures.
    # Only a true critical production invariant returns 503.
    status_code = 503 if report.get("status") == "critical" else 200
    return JSONResponse(status_code=status_code, content=report)
