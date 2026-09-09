from datetime import datetime, timezone

from fastapi import APIRouter

from sports_api.api.cfb_markets import router as cfb_markets_router

router = APIRouter(tags=["system"])
# Register the CFB market transport through the existing shared-host system
# router so MLB/WNBA routing stays untouched. Market data remains context-only.
router.include_router(cfb_markets_router)


@router.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "kyre-sports-api",
        "version": "0.1.0",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
