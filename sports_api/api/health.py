from datetime import datetime, timezone

from fastapi import APIRouter

from sports_api.observability_v1 import (
    OBSERVABILITY_VERSION,
    diagnostics_snapshot,
    readiness_snapshot,
    runtime_metadata,
)

router = APIRouter(tags=["system"])


@router.get("/health")
def health_check():
    """Fast liveness probe kept intentionally lightweight for Render."""
    runtime = runtime_metadata()
    return {
        "status": "ok",
        "service": "kyre-sports-api",
        "version": "0.1.0",
        "observability_version": OBSERVABILITY_VERSION,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "deployment": {
            "branch": runtime["deploy_branch"],
            "commit": runtime["deploy_commit"],
            "branch_aligned": runtime["branch_aligned"],
        },
    }


@router.get("/health/ready")
def readiness_check():
    """Machine-readable readiness/deployment identity for debugging and CI."""
    snapshot = readiness_snapshot()
    snapshot["timestamp_utc"] = datetime.now(timezone.utc).isoformat()
    return snapshot


@router.get("/health/details")
def health_details():
    """Non-secret runtime diagnostics for fast production triage."""
    snapshot = diagnostics_snapshot()
    snapshot["timestamp_utc"] = datetime.now(timezone.utc).isoformat()
    return snapshot
