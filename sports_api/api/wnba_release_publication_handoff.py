from fastapi import APIRouter

from sports_api.wnba_release_publication_handoff import (
    build_release_handoff_plan,
    get_release_publication_handoff_readiness,
)

router = APIRouter(prefix="/api/v1/wnba/runtime", tags=["wnba-runtime"])


@router.get("/handoff")
def release_publication_handoff_readiness():
    return get_release_publication_handoff_readiness()


@router.get("/handoff-plan")
def release_publication_handoff_plan():
    return build_release_handoff_plan()
