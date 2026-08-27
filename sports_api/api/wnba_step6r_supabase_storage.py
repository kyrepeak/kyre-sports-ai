from __future__ import annotations

from fastapi import APIRouter

from sports_api.wnba_step6r_supabase_storage import get_step6r_supabase_storage_status

router = APIRouter(prefix="/api/v1/wnba/runtime", tags=["wnba-runtime"])


@router.get("/step6r-supabase-storage")
def step6r_supabase_storage_status():
    """Return network-free Step 6R Supabase backend/schema readiness."""
    return get_step6r_supabase_storage_status()
