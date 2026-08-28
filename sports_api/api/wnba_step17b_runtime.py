from fastapi import APIRouter

from sports_api.wnba_step17b_always_on_runtime import get_step17b_status

router = APIRouter(prefix="/api/v1/wnba/runtime", tags=["wnba-runtime"])


@router.get("/step17b")
def step17b_runtime_status():
    return get_step17b_status()
