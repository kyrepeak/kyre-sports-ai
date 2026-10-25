"""Non-secret deployment receipt for API2 Step 2F stable-production parity."""
from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

from fastapi import APIRouter


SCHEMA_VERSION = "API2_STEP2F_DEPLOYMENT_RECEIPT_V1"
router = APIRouter(prefix="/api/v1/system", tags=["api2-step2f"])


def deployment_receipt_from_env(env: Mapping[str, str]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "service": "Kyre Sports API",
        "environment": str(env.get("VERCEL_ENV") or "").strip(),
        "target_environment": str(env.get("VERCEL_TARGET_ENV") or env.get("VERCEL_ENV") or "").strip(),
        "git_commit_sha": str(env.get("VERCEL_GIT_COMMIT_SHA") or "").strip(),
        "git_commit_ref": str(env.get("VERCEL_GIT_COMMIT_REF") or "").strip(),
        "deployment_url": str(env.get("VERCEL_URL") or "").strip(),
        "production_url": str(env.get("VERCEL_PROJECT_PRODUCTION_URL") or "").strip(),
        "vercel_runtime": str(env.get("VERCEL") or "").strip() == "1",
        "contains_secrets": False,
    }


@router.get("/deployment-receipt")
def deployment_receipt() -> dict[str, Any]:
    return deployment_receipt_from_env(os.environ)


__all__ = ["SCHEMA_VERSION", "deployment_receipt", "deployment_receipt_from_env", "router"]
