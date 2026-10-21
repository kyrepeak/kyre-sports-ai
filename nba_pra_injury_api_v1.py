"""Application client for the Kyre Sports API NBA injury route."""
from __future__ import annotations

from datetime import datetime, timezone
import os
from typing import Any, Callable, Mapping

import requests

DEFAULT_API_BASE_URL = "https://kyre-runless-proof.vercel.app"


def load_kyre_sports_api_nba_injuries(games, *, now_utc: datetime | None = None, request_post: Callable[..., Any] | None = None, base_url: str | None = None, timeout=(3.0, 20.0)) -> dict[str, Any]:
    now = now_utc or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    post = request_post or requests.post
    base = str(base_url or os.getenv("KYRE_NBA_API_BASE_URL") or DEFAULT_API_BASE_URL).rstrip("/")
    try:
        response = post(f"{base}/api/v1/nba/pra/injuries", json={"games":list(games or []),"now_utc":now.astimezone(timezone.utc).isoformat()}, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        return {"source":"Kyre Sports API — Vercel","verification":"UNAVAILABLE","diagnostic_state":f"KYRE_VERCEL_ERROR:{type(exc).__name__}","players":{},"fabrication":False}
    if not isinstance(payload, Mapping) or payload.get("fabrication") is not False:
        return {"source":"Kyre Sports API — Vercel","verification":"UNAVAILABLE","diagnostic_state":"KYRE_VERCEL_CONTRACT_INVALID","players":{},"fabrication":False}
    return dict(payload)
