from __future__ import annotations

from fastapi import APIRouter

from sports_api.wnba_step6q_durable_storage import get_step6q_durable_storage_status

router = APIRouter(prefix="/api/v1/wnba/runtime", tags=["wnba-runtime"])


@router.get("/step6q-durable-storage")
def step6q_durable_storage_status():
    """Return the read-only Step 6Q durable-storage contract and backend status."""
    return get_step6q_durable_storage_status()
