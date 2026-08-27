"""Step 6T durable-canary evidence verification transport."""
from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from sports_api.api.wnba_kyre_market_feed import require_ingest_authorization
from sports_api.wnba_step6t_canary_evidence import (
    WNBAStep6TEvidenceError,
    get_step6t_canary_evidence_status,
    verify_step6t_canary_evidence,
)

router = APIRouter(prefix="/api/v1/wnba/runtime", tags=["wnba-runtime"])


@router.get("/step6t-canary-evidence/status")
def step6t_canary_evidence_status():
    """Return network-free configuration readiness for Step 6T verification."""
    return get_step6t_canary_evidence_status()


@router.post("/step6t-canary-evidence/verify")
def post_step6t_canary_evidence_verify(
    authorization: str | None = Header(default=None),
):
    """Explicitly perform read-only durable evidence verification."""
    require_ingest_authorization(authorization)
    try:
        return verify_step6t_canary_evidence()
    except WNBAStep6TEvidenceError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
