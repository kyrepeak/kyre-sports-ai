from fastapi import APIRouter

from sports_api.wnba_step17c_production_reliability import (
    build_step17c_health,
    build_step17c_production_reliability,
)

router = APIRouter(prefix="/api/v1/wnba/runtime", tags=["wnba-runtime"])


@router.get("/step17c")
def step17c_runtime_reliability():
    return build_step17c_production_reliability()


@router.get("/step17c/health")
def step17c_runtime_health():
    return build_step17c_health()
