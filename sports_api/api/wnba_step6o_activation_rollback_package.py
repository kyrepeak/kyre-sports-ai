"""GET-only FastAPI transport for WNBA Step 6O activation/rollback package."""
from fastapi import APIRouter

from sports_api.wnba_step6o_activation_rollback_package import build_step6o_activation_rollback_package

router = APIRouter(prefix="/api/v1/wnba", tags=["wnba"])


@router.get("/runtime/step6o-activation-rollback-package")
def get_step6o_activation_rollback_package():
    return build_step6o_activation_rollback_package()
