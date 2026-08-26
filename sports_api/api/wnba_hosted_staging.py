from fastapi import APIRouter

from sports_api.wnba_hosted_staging_readiness import (
    build_hosted_staging_smoke_plan,
    get_hosted_staging_readiness,
)

router = APIRouter(prefix="/api/v1/wnba/runtime", tags=["wnba-runtime"])


@router.get("/hosting")
def hosted_staging_readiness():
    return get_hosted_staging_readiness()


@router.get("/hosting-smoke-plan")
def hosted_staging_smoke_plan():
    report = get_hosted_staging_readiness()
    base_url = report.get("external_url")
    return build_hosted_staging_smoke_plan(base_url) if base_url else {
        "source": report.get("source"),
        "model_version": report.get("model_version"),
        "base_url": None,
        "request_count": 0,
        "requests": [],
        "safety": {
            "read_only": True,
            "all_methods_are_get": True,
            "manual_refresh_endpoint_is_not_called": True,
            "sportsbook_collection_is_not_intentionally_triggered": True,
            "monte_carlo_rebuild_is_not_intentionally_triggered": True,
            "requires_pre_activation_runtime_503": True,
        },
        "blocking_reason": "WNBA_STAGING_EXTERNAL_URL is not configured.",
    }
