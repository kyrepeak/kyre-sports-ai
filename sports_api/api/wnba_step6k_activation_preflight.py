"""Read-only FastAPI transport for WNBA Step 6K activation preflight."""
from fastapi import APIRouter

from sports_api.wnba_step6k_activation_preflight import (
    build_step6k_activation_plan,
    get_step6k_activation_preflight,
)

router = APIRouter(prefix="/api/v1/wnba/runtime", tags=["wnba"])


@router.get("/step6k-preflight")
def get_wnba_step6k_preflight():
    return get_step6k_activation_preflight()


@router.get("/step6k-plan")
def get_wnba_step6k_plan():
    return build_step6k_activation_plan()
