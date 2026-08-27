"""Authenticated Step 6J one-shot canary transport."""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Query

from sports_api.api.wnba_kyre_market_feed import require_ingest_authorization
from sports_api.wnba_step6j_canary_activation import (
    WNBAStep6JCanaryError,
    get_step6j_canary_status,
    rollback_step6j_canary,
    run_step6j_canary,
)

router = APIRouter(prefix="/markets/direct/draftkings", tags=["wnba"])


def _activation_id(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="X-WNBA-Step6J-Activation-ID is required.")
    return text


@router.get("/step6j-canary/status")
def get_draftkings_step6j_canary_status():
    return get_step6j_canary_status()


@router.post("/step6j-canary")
def post_draftkings_step6j_canary(
    date: str = Query(..., description="UTC WNBA slate date YYYY-MM-DD."),
    season: int = Query(..., ge=1997, le=2200),
    authorization: str | None = Header(default=None),
    x_wnba_step6j_activation_id: str | None = Header(default=None, alias="X-WNBA-Step6J-Activation-ID"),
):
    require_ingest_authorization(authorization)
    try:
        return run_step6j_canary(
            date=date,
            season=season,
            activation_id=_activation_id(x_wnba_step6j_activation_id),
        )
    except WNBAStep6JCanaryError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/step6j-canary/rollback")
def post_draftkings_step6j_canary_rollback(
    authorization: str | None = Header(default=None),
    x_wnba_step6j_activation_id: str | None = Header(default=None, alias="X-WNBA-Step6J-Activation-ID"),
):
    require_ingest_authorization(authorization)
    try:
        return rollback_step6j_canary(
            activation_id=_activation_id(x_wnba_step6j_activation_id),
        )
    except WNBAStep6JCanaryError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
