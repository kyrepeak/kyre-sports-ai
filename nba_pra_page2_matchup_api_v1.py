'''Server-side Page 2 client for Kyre Sports API NBA PRA matchup context.'''
from __future__ import annotations

from datetime import datetime
import os
from typing import Any, Callable
import requests

DEFAULT_API_BASE_URL = "https://kyre-sports-api.vercel.app"


def load_kyre_sports_api_nba_pra_matchup(
    opponent: str,
    *,
    now_utc: datetime | None = None,
    request_post: Callable[..., Any] | None = None,
    base_url: str | None = None,
    timeout: tuple[float, float] = (3.0, 18.0),
) -> dict[str, Any]:
    team = str(opponent or "").strip().upper()
    if not team:
        return {"source":"Kyre Sports API — Vercel","verification":"UNAVAILABLE","diagnostic_state":"INVALID_OPPONENT","fabrication":False}
    post = request_post or requests.post
    root = str(base_url or os.getenv("KYRE_NBA_API_BASE_URL") or DEFAULT_API_BASE_URL).rstrip("/")
    payload: dict[str, Any] = {"opponent": team}
    if now_utc is not None:
        payload["now_utc"] = now_utc.isoformat()
    try:
        response = post(f"{root}/api/v1/nba/pra/matchup", json=payload, timeout=timeout)
        if hasattr(response,"raise_for_status"):
            response.raise_for_status()
        data = response.json()
        return dict(data) if isinstance(data,dict) else {"verification":"UNAVAILABLE","diagnostic_state":"INVALID_RESPONSE","fabrication":False}
    except Exception as exc:
        return {"source":"Kyre Sports API — Vercel","verification":"UNAVAILABLE","diagnostic_state":type(exc).__name__,"fabrication":False}
