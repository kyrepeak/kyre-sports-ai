"""FastAPI transport for WNBA Step 5S deployment and smoke readiness."""
from __future__ import annotations

from fastapi import APIRouter, Query

from sports_api.wnba_deployment_smoke_readiness import (
    build_live_smoke_plan,
    get_deployment_readiness,
)

router = APIRouter(prefix="/api/v1/wnba", tags=["wnba"])


@router.get("/runtime/deployment")
def get_wnba_deployment_readiness():
    """Return the network-free Step 5S deployment topology/readiness report."""
    return get_deployment_readiness()


@router.get("/runtime/smoke-plan")
def get_wnba_live_smoke_plan(
    base_url: str | None = Query(
        default=None,
        description="Optional deployed API base URL. Remote URLs must use HTTPS.",
    ),
    expect_scheduler_ready: bool = Query(
        default=False,
        description="When true, the planned runtime-health check requires HTTP 200.",
    ),
):
    """Return the read-only live smoke plan without making any outbound call."""
    return build_live_smoke_plan(
        base_url,
        expect_scheduler_ready=expect_scheduler_ready,
    )
