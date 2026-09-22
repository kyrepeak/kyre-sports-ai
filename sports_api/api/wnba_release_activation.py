from fastapi import APIRouter

from sports_api.wnba_release_activation_readiness import (
    build_activation_plan,
    build_rollback_plan,
    get_release_readiness,
)

router = APIRouter(prefix="/api/v1/wnba/runtime", tags=["wnba", "runtime", "release"])


@router.get("/release")
def release_readiness():
    return get_release_readiness()


@router.get("/activation-plan")
def activation_plan(base_url: str | None = None):
    return build_activation_plan(base_url=base_url)


@router.get("/rollback-plan")
def rollback_plan():
    return build_rollback_plan()
