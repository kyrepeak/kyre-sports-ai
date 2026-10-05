"""NBA Over/Under read surface for the hosted Kyre Sports API."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from sports_api.nba_over_under_data_v1 import (
    NBAOverUnderDataError,
    build_nba_over_under_slate,
)

router = APIRouter(prefix="/api/v1/nba/over-under", tags=["nba-over-under"])


@router.get("/slate")
def nba_over_under_slate(
    date: str = Query(..., pattern=r"^\d{4}-\d{2}-\d{2}$"),
):
    """Return the normalized NBA slate used by the Streamlit NBA page."""
    try:
        return build_nba_over_under_slate(date)
    except NBAOverUnderDataError as exc:
        message = str(exc)
        status_code = 422 if "date must" in message else 503
        raise HTTPException(status_code=status_code, detail=message) from exc


__all__ = ["router", "nba_over_under_slate"]
