"""One-read Streamlit client for the certified WNBA PRA page snapshot."""
from __future__ import annotations

from datetime import datetime
from typing import Any

import requests
from requests.adapters import HTTPAdapter

BASE_URL = "https://kyre-runless-proof.vercel.app"
PAGE_PATH = "/api/v1/wnba/pra/page-snapshot"
PAGE_SCHEMA_VERSION = "wnba_pra_page_snapshot_v1"
DEFAULT_TIMEOUT_SECONDS = 4.0

_SESSION = requests.Session()
_SESSION.mount("https://", HTTPAdapter(pool_connections=4, pool_maxsize=8, max_retries=0, pool_block=False))


class WNBAPRASnapshotClientError(RuntimeError):
    pass


def fetch_page_snapshot(
    day: str,
    season: int = 2026,
    *,
    session: Any | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    datetime.strptime(str(day), "%Y-%m-%d")
    if int(season) != 2026:
        raise WNBAPRASnapshotClientError("WNBA PRA page snapshot supports season 2026 only.")
    client = session or _SESSION
    try:
        response = client.get(
            BASE_URL + PAGE_PATH,
            params={"date": str(day), "season": int(season)},
            headers={"accept": "application/json", "user-agent": "kyre-sports-ai-wnba-pra-snapshot/1"},
            timeout=float(timeout_seconds),
            allow_redirects=True,
        )
    except requests.RequestException as exc:
        raise WNBAPRASnapshotClientError(f"WNBA PRA snapshot transport failed: {type(exc).__name__}") from exc
    if int(response.status_code) != 200:
        raise WNBAPRASnapshotClientError(f"WNBA PRA snapshot returned HTTP {response.status_code}.")
    try:
        body = response.json()
    except ValueError as exc:
        raise WNBAPRASnapshotClientError("WNBA PRA snapshot returned non-JSON data.") from exc
    if not isinstance(body, dict) or body.get("schema_version") != PAGE_SCHEMA_VERSION:
        raise WNBAPRASnapshotClientError("WNBA PRA snapshot schema is invalid.")
    if body.get("date") != str(day) or int(body.get("season") or 0) != int(season):
        raise WNBAPRASnapshotClientError("WNBA PRA snapshot identity mismatch.")
    if int(body.get("market_board_reads") or 0) != 1 or body.get("consensus_averaging") is not False:
        raise WNBAPRASnapshotClientError("WNBA PRA snapshot routing contract is invalid.")
    return body


__all__ = ["BASE_URL", "PAGE_PATH", "WNBAPRASnapshotClientError", "fetch_page_snapshot"]
