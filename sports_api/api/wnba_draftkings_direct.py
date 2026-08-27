"""Read-only FastAPI transport for WNBA direct DraftKings market readiness."""
from fastapi import APIRouter

from sports_api.api.wnba_step6j_canary import router as step6j_canary_router
from sports_api.wnba_step6d_direct_integration import get_step6d_direct_market_status
from sports_api.wnba_draftkings_shadow_ingestion import get_shadow_readiness
from sports_api.wnba_official_reconciliation import get_reconciliation_readiness
from sports_api.wnba_reconciled_direct_sync import get_reconciled_sync_status

router = APIRouter(prefix="/api/v1/wnba", tags=["wnba"])


@router.get("/markets/direct/draftkings/status")
def get_draftkings_direct_status():
    return get_step6d_direct_market_status()


@router.get("/markets/direct/draftkings/shadow-readiness")
def get_draftkings_shadow_readiness():
    return get_shadow_readiness()


@router.get("/markets/direct/draftkings/official-reconciliation-readiness")
def get_draftkings_official_reconciliation_readiness():
    return get_reconciliation_readiness()


@router.get("/markets/direct/draftkings/reconciled-sync-status")
def get_draftkings_reconciled_sync_status():
    return get_reconciled_sync_status()


router.include_router(step6j_canary_router)
