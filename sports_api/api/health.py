from datetime import datetime, timezone

from fastapi import APIRouter

from sports_api.api.cfb_markets import router as cfb_markets_router
from sports_api.api.cfb_market_identity_v1 import router as cfb_market_identity_router

router = APIRouter(tags=["system"])
# CFB market transport is registered through the existing system router so
# the odds integration remains isolated from frozen CFB projection modules.
router.include_router(cfb_markets_router)
router.include_router(cfb_market_identity_router)


@router.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "kyre-sports-api",
        "version": "0.1.0",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
