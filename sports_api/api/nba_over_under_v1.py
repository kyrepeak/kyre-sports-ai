"""NBA Over/Under Step 2 read-only Kyre Sports API route."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from sports_api.nba_over_under_data_v1 import (
    NBAOverUnderDataError,
    build_nba_over_under_slate,
)

router = APIRouter(prefix="/api/v1/nba/over-under", tags=["nba-over-under"])


@router.get("/slate")
def nba_over_under_slate(
    date: str = Query(..., min_length=10, max_length=10),
):
    try:
        return build_nba_over_under_slate(date)
    except NBAOverUnderDataError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="NBA slate unavailable") from exc
