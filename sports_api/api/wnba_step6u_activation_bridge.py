"""Step 6U storage-aware activation bridge transport."""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from sports_api.api.wnba_kyre_market_feed import require_ingest_authorization
from sports_api.wnba_step6u_activation_bridge import (
    WNBAStep6UActivationBridgeError,
    get_step6u_activation_bridge_status,
    require_step6u_bridge_ready,
)

router = APIRouter(prefix="/api/v1/wnba/runtime", tags=["wnba-runtime"])


@router.get("/step6u-activation-bridge/status")
def step6u_activation_bridge_status():
    """Return network-free pre-activation bridge configuration status."""
    return get_step6u_activation_bridge_status()


@router.post("/step6u-activation-bridge/verify")
def post_step6u_activation_bridge_verify(
    authorization: str | None = Header(default=None),
):
    """Explicitly verify Step 6T evidence and emit the read-only bridge checkpoint."""
    require_ingest_authorization(authorization)
    try:
        return require_step6u_bridge_ready()
    except WNBAStep6UActivationBridgeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
