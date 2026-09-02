"""Read-only status endpoint for the MLB Step 17B controlled always-on runtime."""
from fastapi import APIRouter

from sports_api.mlb_step17b_always_on_runtime_v1 import get_step17b_status

router = APIRouter(prefix="/api/v1/mlb/runtime", tags=["mlb-runtime"])


@router.get("/step17b")
def mlb_step17b_runtime_status():
    """Return sanitized process/leadership/checkpoint status; never secrets."""
    return get_step17b_status()
