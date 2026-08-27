from fastapi import APIRouter

from sports_api.wnba_render_attachment_readiness import (
    build_render_attachment_spec,
    get_render_attachment_readiness,
)

router = APIRouter(prefix="/api/v1/wnba/runtime", tags=["wnba-runtime"])


@router.get("/render-attachment")
def render_attachment_readiness():
    return get_render_attachment_readiness()


@router.get("/render-attachment-plan")
def render_attachment_plan():
    report = get_render_attachment_readiness()
    step5x = report.get("step_5x") or {}
    identity = report.get("attachment_identity_payload") or {}
    image_ref = report.get("deployed_image_ref")
    service_name = report.get("render_service_name")
    release_id = None
    revision = None

    # When Step 5X is not yet fully hosted, return a safe plan shell rather than
    # inventing release/host values. The publication workflow emits the exact
    # filled deployment bundle once an immutable digest exists.
    try:
        from sports_api.wnba_real_staging_deployment import get_real_staging_deployment_readiness

        step5x_full = get_real_staging_deployment_readiness()
        release_id = step5x_full.get("release_id")
        revision = step5x_full.get("revision")
        image_ref = step5x_full.get("published_image_ref") or image_ref
        service_name = step5x_full.get("render_service_name") or service_name
    except Exception:
        step5x_full = {}

    if release_id and revision and image_ref:
        return build_render_attachment_spec(
            release_id=release_id,
            revision=revision,
            image_ref=image_ref,
            service_name=service_name or "kyre-sports-api-staging",
        )

    return {
        "source": report.get("source"),
        "model_version": report.get("model_version"),
        "render_attachment_ready": report.get("render_attachment_ready"),
        "release_id": release_id,
        "revision": revision,
        "image_ref": image_ref,
        "service_name": service_name,
        "step_5x_deployment_identity_sha256": step5x.get("deployment_identity_sha256"),
        "attachment_identity_payload": identity,
        "blocking_reason": "The exact immutable Step 5Y deployment bundle is emitted by the Step 5Y publication workflow after GHCR returns the final digest.",
        "safety": {
            "read_only": True,
            "runtime_remains_disabled": True,
            "sportsbook_called": False,
            "monte_carlo_run": False,
        },
    }
