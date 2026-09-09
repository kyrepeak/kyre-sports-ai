from datetime import datetime, timezone

from fastapi import APIRouter

from sports_api.api.cfb_markets import router as cfb_markets_router

router = APIRouter(tags=["system"])
# CFB market transport is registered through the existing system router so
# Step 1 remains an additive API-layer change and does not touch frozen CFB
# projection modules.
router.include_router(cfb_markets_router)


@router.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "kyre-sports-api",
        "version": "0.1.0",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }