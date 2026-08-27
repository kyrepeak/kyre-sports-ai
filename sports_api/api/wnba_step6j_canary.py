"""Authenticated Step 6J one-shot canary transport with Step 6S storage dispatch."""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException, Query

from sports_api.api.wnba_kyre_market_feed import require_ingest_authorization
from sports_api.wnba_step6j_canary_activation import (
    WNBAStep6JCanaryError,
    get_step6j_canary_status,
)
from sports_api.wnba_step6s_canary_storage import (
    get_step6s_canary_storage_status,
    rollback_storage_aware_step6j_canary as rollback_step6j_canary,
    run_storage_aware_step6j_canary as run_step6j_canary,
)

router = APIRouter(prefix="/markets/direct/draftkings", tags=["wnba"])


def _activation_id(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="X-WNBA-Step6J-Activation-ID is required.")
    return text


def _block_failed_canary_replay() -> None:
    """Preserve the historical filesystem replay block before transport dispatch.

    The Step 6S Supabase runner independently enforces the same terminal replay
    rule against its remote marker because this legacy status read is purposely
    network-free and cannot inspect Supabase.
    """
    status = get_step6j_canary_status()
    state = status.get("canary_state") or {}
    terminal_status = state.get("status")
    if terminal_status == "rolled_back":
        raise HTTPException(
            status_code=409,
            detail="Step 6J already failed closed and rolled back; the canary cannot be replayed.",
        )
    if terminal_status == "manually_rolled_back":
        raise HTTPException(
            status_code=409,
            detail="Step 6J was manually rolled back; the canary cannot be replayed.",
        )


@router.get("/step6j-canary/status")
def get_draftkings_step6j_canary_status():
    return get_step6j_canary_status()


@router.get("/step6j-canary/storage-status")
def get_draftkings_step6j_canary_storage_status():
    """Return network-free Step 6S backend-dispatch readiness."""
    return get_step6s_canary_storage_status()


@router.post("/step6j-canary")
def post_draftkings_step6j_canary(
    date: str = Query(..., description="UTC WNBA slate date YYYY-MM-DD."),
    season: int = Query(..., ge=1997, le=2200),
    authorization: str | None = Header(default=None),
    x_wnba_step6j_activation_id: str | None = Header(default=None, alias="X-WNBA-Step6J-Activation-ID"),
):
    require_ingest_authorization(authorization)
    _block_failed_canary_replay()
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
