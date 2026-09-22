from fastapi import APIRouter

from sports_api.wnba_real_staging_deployment import (
    build_real_staging_smoke_plan,
    get_real_staging_deployment_readiness,
)

router = APIRouter(prefix="/api/v1/wnba/runtime", tags=["wnba-runtime"])


@router.get("/staging-deployment")
def real_staging_deployment_readiness():
    return get_real_staging_deployment_readiness()


@router.get("/staging-deployment-smoke-plan")
def real_staging_deployment_smoke_plan():
    report = get_real_staging_deployment_readiness()
    base_url = report.get("external_url")
    if base_url:
        return build_real_staging_smoke_plan(base_url)
    return {
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
            "requires_runtime_health_503": True,
            "requires_step_5w_checkpoint_ready": True,
        },
        "blocking_reason": "A real WNBA_STAGING_EXTERNAL_URL is not available.",
    }
