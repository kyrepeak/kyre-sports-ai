"""No-secret Streamlit trigger for server-owned WNBA PRA artifact refresh."""
from __future__ import annotations

import threading
from typing import Any

import requests

BASE_URL = "https://kyre-runless-proof.vercel.app"
REFRESH_PATH = "/api/v1/wnba/pra/page-snapshot/refresh-request"
DEFAULT_TIMEOUT_SECONDS = 180.0
_SESSION = requests.Session()

class WNBAPRASnapshotPublishError(RuntimeError):
    pass

def _request(day: str, *, season: int = 2026, session: Any | None = None) -> dict[str, Any]:
    client = session or _SESSION
    try:
        response = client.post(
            BASE_URL + REFRESH_PATH, json={"date":str(day),"season":int(season)},
            headers={"accept":"application/json","content-type":"application/json"}, timeout=DEFAULT_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise WNBAPRASnapshotPublishError(f"WNBA PRA refresh transport failed: {type(exc).__name__}") from exc
    if int(response.status_code) != 200:
        raise WNBAPRASnapshotPublishError(f"WNBA PRA refresh returned HTTP {response.status_code}.")
    try:
        body=response.json()
    except ValueError as exc:
        raise WNBAPRASnapshotPublishError("WNBA PRA refresh returned non-JSON data.") from exc
    if not isinstance(body,dict):
        raise WNBAPRASnapshotPublishError("WNBA PRA refresh returned invalid data.")
    return body

def request_refresh(day: str, *, season: int = 2026, session: Any | None = None, background: bool = True) -> dict[str, Any]:
    if not background:
        return _request(day,season=season,session=session)
    result={"state":"REQUESTED"}
    def work() -> None:
        try: _request(day,season=season,session=session)
        except Exception: pass
    threading.Thread(target=work,name=f"wnba-pra-refresh-{day}",daemon=True).start()
    return result

def refresh_if_claimed(day: str, *, season: int = 2026, owner_id: str | None = None, background: bool = True, **kwargs: Any) -> bool:
    request_refresh(day,season=season,background=background,session=kwargs.get("session"))
    return True

__all__=["WNBAPRASnapshotPublishError","request_refresh","refresh_if_claimed"]
