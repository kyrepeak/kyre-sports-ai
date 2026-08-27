"""Read-only FastAPI transport for WNBA direct DraftKings market readiness."""
from fastapi import APIRouter

from sports_api.wnba_step6d_direct_integration import get_step6d_direct_market_status
from sports_api.wnba_draftkings_shadow_ingestion import get_shadow_readiness

router = APIRouter(prefix="/api/v1/wnba", tags=["wnba"])


@router.get("/markets/direct/draftkings/status")
def get_draftkings_direct_status():
    return get_step6d_direct_market_status()


@router.get("/markets/direct/draftkings/shadow-readiness")
def get_draftkings_shadow_readiness():
    return get_shadow_readiness()
