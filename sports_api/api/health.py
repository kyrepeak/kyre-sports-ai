from datetime import datetime, timezone

from fastapi import APIRouter

from sports_api.observability_v1 import (
    OBSERVABILITY_VERSION,
    diagnostics_snapshot,
    readiness_snapshot,
    runtime_metadata,
)
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
    """Fast liveness probe kept intentionally lightweight for Render."""
    runtime = runtime_metadata()
    return {
        "status": "ok",
        "service": "kyre-sports-api",
        "version": "0.1.0",
        "observability_version": OBSERVABILITY_VERSION,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "deployment": {
            "branch": runtime["deploy_branch"],
            "commit": runtime["deploy_commit"],
            "branch_aligned": runtime["branch_aligned"],
        },
    }


@router.get("/health/ready")
def readiness_check():
    """Machine-readable readiness/deployment identity for debugging and CI."""
    snapshot = readiness_snapshot()
    snapshot["timestamp_utc"] = datetime.now(timezone.utc).isoformat()
    return snapshot


@router.get("/health/details")
def health_details():
    """Non-secret runtime diagnostics for fast production triage."""
    snapshot = diagnostics_snapshot()
    snapshot["timestamp_utc"] = datetime.now(timezone.utc).isoformat()
    return snapshot
