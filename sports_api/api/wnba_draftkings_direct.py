"""Read-only FastAPI transport for WNBA Step 6D direct sportsbook sync status."""
from fastapi import APIRouter

from sports_api.wnba_step6d_direct_integration import get_step6d_direct_market_status

router = APIRouter(prefix="/api/v1/wnba", tags=["wnba"])


@router.get("/markets/direct/draftkings/status")
def get_draftkings_direct_status():
    return get_step6d_direct_market_status()
