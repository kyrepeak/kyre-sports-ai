"""Read-only FastAPI transport for WNBA Step 6L production feed refresh."""
from fastapi import APIRouter

from sports_api.wnba_step6l_production_feed_refresh import (
    build_step6l_production_refresh_plan,
    get_step6l_production_refresh_status,
)

router = APIRouter(prefix="/api/v1/wnba/runtime", tags=["wnba"])


@router.get("/step6l-feed-refresh-status")
def get_wnba_step6l_feed_refresh_status():
    return get_step6l_production_refresh_status()


@router.get("/step6l-feed-refresh-plan")
def get_wnba_step6l_feed_refresh_plan():
    return build_step6l_production_refresh_plan()
