from fastapi import APIRouter

from sports_api.wnba_step7a_release_candidate import build_step7a_release_candidate

router = APIRouter(tags=["wnba-runtime"])


@router.get("/api/v1/wnba/runtime/step7a-release-candidate")
def get_step7a_release_candidate():
    return build_step7a_release_candidate()
