from fastapi import APIRouter

from sports_api.wnba_step6w_final_certification import build_step6w_final_certification

router = APIRouter(tags=["wnba-runtime"])


@router.get("/api/v1/wnba/runtime/step6w-final-certification")
def get_step6w_final_certification():
    return build_step6w_final_certification()
