from __future__ import annotations

import hmac

from fastapi import HTTPException


def require_bearer(authorization: str | None, expected_token: str) -> None:
    value = str(authorization or "")
    prefix = "Bearer "
    if not value.startswith(prefix):
        raise HTTPException(status_code=401, detail="RUNLESS_V2_AUTH_REQUIRED")
    supplied = value[len(prefix):]
    if not supplied or not hmac.compare_digest(supplied, expected_token):
        raise HTTPException(status_code=401, detail="RUNLESS_V2_AUTH_INVALID")
