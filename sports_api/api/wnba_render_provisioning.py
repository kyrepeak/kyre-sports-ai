from fastapi import APIRouter

from sports_api.wnba_render_provisioning import get_render_provisioning_status

router = APIRouter(prefix="/api/v1/wnba/runtime", tags=["wnba-runtime"])


@router.get("/render-provisioning")
def render_provisioning_status():
    return get_render_provisioning_status()
