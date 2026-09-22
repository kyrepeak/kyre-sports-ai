#!/usr/bin/env python3
"""Step 7C Render Free compatibility wrapper.

Render Free rejects the maxShutdownDelaySeconds field accepted by paid plans.
This wrapper removes that one unsupported field while preserving every Step 7C
free-only, diskless, pre-activation safety invariant from the frozen operator.
"""
from __future__ import annotations

import json
from typing import Any

import sports_api.tools.wnba_step7c_render_free_deploy as base

MODEL_VERSION = "wnba_step_7c_render_free_deploy_v2"
_ORIGINAL_BUILD_FREE_SERVICE_PAYLOAD = base.build_free_service_payload


def build_free_service_payload(*, owner_id: str) -> dict[str, Any]:
    payload = _ORIGINAL_BUILD_FREE_SERVICE_PAYLOAD(owner_id=owner_id)
    details = payload.get("serviceDetails")
    if not isinstance(details, dict):
        raise base.Step7CRenderError("Step 7C serviceDetails are required.")
    details.pop("maxShutdownDelaySeconds", None)
    base.validate_free_payload(payload)
    if "maxShutdownDelaySeconds" in details:
        raise base.Step7CRenderError("Render Free payload must not include maxShutdownDelaySeconds.")
    return payload


def deploy_free_render_service(*, env=None) -> dict[str, Any]:
    previous = base.build_free_service_payload
    base.build_free_service_payload = build_free_service_payload
    try:
        report = base.deploy_free_render_service(env=env)
    finally:
        base.build_free_service_payload = previous
    report["model_version"] = MODEL_VERSION
    report.setdefault("compatibility", {})["free_tier_max_shutdown_delay_omitted"] = True
    return report


def main() -> int:
    print(json.dumps(deploy_free_render_service(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
