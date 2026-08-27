from fastapi import APIRouter

from sports_api.wnba_draftkings_endpoint_discovery import get_endpoint_discovery_status

router = APIRouter(prefix="/api/v1/wnba/markets/direct/draftkings", tags=["wnba-markets"])


@router.get("/discovery")
def get_draftkings_discovery_status():
    """Return network-free Step 6E endpoint discovery configuration/status."""
    return get_endpoint_discovery_status()
