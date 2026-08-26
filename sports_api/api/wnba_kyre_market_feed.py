"""Secured transport for the Kyre-owned WNBA market feed."""
from __future__ import annotations

from collections.abc import Mapping
import hmac
import os
from typing import Any

from fastapi import APIRouter, Body, Header, HTTPException

from sports_api.collectors.wnba_kyre_market_feed import (
    WNBAKyreMarketFeedModelInputError,
    WNBAKyreMarketFeedNotReadyError,
    WNBAKyreMarketFeedUpstreamError,
    describe_kyre_market_onboarding,
    write_kyre_market_feed,
)

router = APIRouter(prefix="/api/v1/wnba/markets/owned", tags=["wnba"])
INGEST_TOKEN_ENV = "WNBA_KYRE_MARKET_INGEST_TOKEN"


def _environment(env: Mapping[str, str] | None = None) -> Mapping[str, str]:
    return os.environ if env is None else env


def _clean(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def require_ingest_authorization(
    authorization: str | None,
    *,
    env: Mapping[str, str] | None = None,
) -> None:
    environment = _environment(env)
    expected = _clean(environment.get(INGEST_TOKEN_ENV))
    if not expected:
        raise HTTPException(
            status_code=503,
            detail=f"Kyre market ingestion is unavailable because {INGEST_TOKEN_ENV} is not configured.",
        )
    header = _clean(authorization)
    if not header or not header.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="A valid bearer token is required.")
    supplied = header[7:].strip()
    if not supplied or not hmac.compare_digest(supplied.encode("utf-8"), expected.encode("utf-8")):
        raise HTTPException(status_code=401, detail="A valid bearer token is required.")


def _raise_feed_error(exc: Exception) -> None:
    if isinstance(exc, WNBAKyreMarketFeedModelInputError):
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if isinstance(exc, WNBAKyreMarketFeedNotReadyError):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(exc, WNBAKyreMarketFeedUpstreamError):
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    if isinstance(exc, (OSError, ValueError)):
        raise HTTPException(status_code=500, detail="Kyre market feed could not be stored.") from exc
    raise exc


@router.get("/status")
def get_owned_market_feed_status():
    try:
        result = describe_kyre_market_onboarding()
        result["ingest_api"] = {
            "enabled": bool(_clean(os.environ.get(INGEST_TOKEN_ENV))),
            "authentication": "bearer_token",
            "token_returned": False,
            "write_endpoint": "/api/v1/wnba/markets/owned/feed",
        }
        return result
    except Exception as exc:
        _raise_feed_error(exc)


@router.post("/feed")
def put_owned_market_feed(
    payload: dict[str, Any] = Body(...),
    authorization: str | None = Header(default=None),
):
    require_ingest_authorization(authorization)
    try:
        stored = write_kyre_market_feed(payload)
    except Exception as exc:
        _raise_feed_error(exc)
    return {
        "source": "Kyre Sports API WNBA Step 6C owned market ingest",
        "data_type": "wnba_owned_market_feed_ingest_result",
        "stored": True,
        "storage": stored,
        "scheduler_triggered": False,
        "monte_carlo_run": False,
        "sportsbook_vendor_called": False,
        "authorization_token_returned": False,
    }
