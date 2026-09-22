"""Read-only FastAPI transport for WNBA Step 6M scheduler orchestration."""
from fastapi import APIRouter

from sports_api.wnba_step6m_scheduler_orchestration import (
    build_step6m_scheduler_orchestration_plan,
    get_step6m_scheduler_orchestration_status,
)

router = APIRouter(prefix="/api/v1/wnba/runtime", tags=["wnba"])


@router.get("/step6m-scheduler-orchestration-status")
def get_wnba_step6m_scheduler_orchestration_status():
    return get_step6m_scheduler_orchestration_status()


@router.get("/step6m-scheduler-orchestration-plan")
def get_wnba_step6m_scheduler_orchestration_plan():
    return build_step6m_scheduler_orchestration_plan()
