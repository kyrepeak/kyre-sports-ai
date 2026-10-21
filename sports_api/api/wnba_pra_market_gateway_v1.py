"""HTTP transport for the Kyre Sports API WNBA PRA market gateway."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from sports_api.wnba_pra_market_gateway_v1 import build_pra_market_board

router = APIRouter(prefix="/api/v1/wnba", tags=["wnba"])


@router.get("/pra/market-board")
def get_wnba_pra_market_board(
    date: str = Query(..., description="WNBA slate date in YYYY-MM-DD format"),
    season: int = Query(2026, ge=1),
):
    try:
        return build_pra_market_board(date=date, season=season)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"WNBA PRA market gateway unavailable: {type(exc).__name__}",
        ) from exc


__all__ = ["router", "get_wnba_pra_market_board"]
