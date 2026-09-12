"""Transport-hardened wrapper for the NFL Passing Yards public production cert.

GitHub-hosted runners can receive HTTP 403 from ESPN when Python requests uses
its default TLS/request fingerprint, even though the same public endpoint is
available through the urllib transport already proven by the NFL API live cert.
This wrapper changes certification transport only. Production/runtime behavior
is untouched.
"""
from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import nfl_passing_yards_public_prod_cert_v1 as base

BROWSER_HEADERS = {
    "Accept": "application/json,text/plain,*/*",
    "User-Agent": "Mozilla/5.0 (compatible; KyreSportsAPI-NFL/1.0; read-only)",
}


class _Response:
    def __init__(self, status_code: int, raw: bytes) -> None:
        self.status_code = int(status_code)
        self._raw = raw
        self.text = raw.decode("utf-8", errors="replace")

    def json(self) -> Any:
        return json.loads(self.text)


def _urllib_get(url: str, *, params: dict[str, Any] | None = None, timeout: float = 20.0) -> _Response:
    query = urlencode({str(k): str(v) for k, v in (params or {}).items()})
    target = f"{url}?{query}" if query else url
    request = Request(target, headers=BROWSER_HEADERS, method="GET")
    with urlopen(request, timeout=timeout) as response:
        return _Response(int(getattr(response, "status", 0) or 0), response.read(25_000_000))


def run_public_cert(**kwargs):
    original = base._get
    base._get = _urllib_get
    try:
        return base.run_public_cert(**kwargs)
    finally:
        base._get = original


if __name__ == "__main__":
    args = base._parse_args()
    run_public_cert(
        production_url=args.production_url,
        api_url=args.api_url,
        artifact_dir=args.artifact_dir,
    )
