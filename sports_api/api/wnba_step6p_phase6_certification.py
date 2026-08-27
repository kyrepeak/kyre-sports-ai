"""Read-only API route for the WNBA Step 6P Phase 6 master certification."""
from __future__ import annotations

from fastapi import APIRouter

from sports_api.wnba_step6p_phase6_certification import build_step6p_phase6_certification

router = APIRouter(prefix="/api/v1/wnba/runtime", tags=["wnba-runtime"])


@router.get("/phase6-certification")
def get_phase6_certification():
    return build_step6p_phase6_certification()
