from datetime import datetime, timezone

from fastapi import APIRouter

from sports_api.api.cfb_render_fanduel_transport_v1 import install_hosted_transport
from sports_api.api.cfb_markets import router as cfb_markets_router
from sports_api.api.cfb_market_identity_v1 import router as cfb_market_identity_router
from sports_api.api.cfb_odds_v1 import router as cfb_odds_router

# Shared-host hotfix: swap only the outbound FanDuel GET transport. The frozen
# CFB cache/freshness, parser, identity, and projection contracts stay intact.
install_hosted_transport()

router = APIRouter(tags=["system"])
# Register CFB routes by extending the shared route table instead of nesting
# APIRouter lifespans. This preserves the certified Step17B shared-host lifespan
# and the Render startup-recursion fix from CFB Step 1.
router.routes.extend(cfb_markets_router.routes)
router.routes.extend(cfb_market_identity_router.routes)
router.routes.extend(cfb_odds_router.routes)


@router.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "kyre-sports-api",
        "version": "0.1.0",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    }
