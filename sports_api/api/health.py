from datetime import datetime, timezone

from fastapi import APIRouter

from sports_api.api.cfb_markets import router as cfb_markets_router

router = APIRouter(tags=["system"])
# Register the CFB routes without nesting APIRouter lifespans into the shared
# health router. The CFB market router has no startup/shutdown handlers, so
# extending the route table preserves the existing Step17B app lifespan and
# avoids the recursive merged_lifespan startup failure seen on Render.
router.routes.extend(cfb_markets_router.routes)


@router.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "kyre-sports-api",
        "version": "0.1.0",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
