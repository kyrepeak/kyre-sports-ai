from fastapi import APIRouter

from sports_api.wnba_step18a_streamlit_consumer import build_step18a_consumer_latest

router = APIRouter(prefix="/api/v1/wnba/consumer", tags=["wnba-consumer"])


@router.get("/latest")
def wnba_consumer_latest():
    return build_step18a_consumer_latest()
