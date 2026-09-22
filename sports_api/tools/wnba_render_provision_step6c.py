#!/usr/bin/env python3
"""Operator CLI for SportsGameOdds-free WNBA Step 6C Render provisioning."""
from __future__ import annotations

import argparse
import json
import os

from sports_api.wnba_render_provisioning import (
    GHCR_TOKEN_ENV,
    GHCR_USERNAME_ENV,
    RENDER_API_KEY_ENV,
    RENDER_OWNER_ID_ENV,
)
from sports_api.wnba_render_provisioning_step6c import (
    build_step6c_render_plan,
    provision_step6c_render_staging,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Provision Kyre-owned WNBA market staging on Render.")
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--image-ref", required=True)
    parser.add_argument("--service-name", default="kyre-sports-api-staging")
    parser.add_argument("--owner-id", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--confirm-paid-provisioning", action="store_true")
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    parser.add_argument("--deploy-timeout-seconds", type=float, default=420.0)
    parser.add_argument("--poll-seconds", type=float, default=3.0)
    args = parser.parse_args()

    owner_id = args.owner_id or os.getenv(RENDER_OWNER_ID_ENV)
    if args.dry_run:
        result = build_step6c_render_plan(
            release_id=args.release_id,
            revision=args.revision,
            image_ref=args.image_ref,
            service_name=args.service_name,
            owner_id=owner_id,
        )
    else:
        result = provision_step6c_render_staging(
            release_id=args.release_id,
            revision=args.revision,
            image_ref=args.image_ref,
            api_key=os.getenv(RENDER_API_KEY_ENV, ""),
            ghcr_username=os.getenv(GHCR_USERNAME_ENV, ""),
            ghcr_token=os.getenv(GHCR_TOKEN_ENV, ""),
            owner_id=owner_id,
            service_name=args.service_name,
            confirm_paid_provisioning=args.confirm_paid_provisioning,
            env=os.environ,
            timeout_seconds=args.timeout_seconds,
            deploy_timeout_seconds=args.deploy_timeout_seconds,
            poll_seconds=args.poll_seconds,
        )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
