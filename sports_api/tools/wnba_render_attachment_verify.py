#!/usr/bin/env python3
"""Read-only WNBA Step 5Y Render attachment verifier.

Requires RENDER_API_KEY in the environment. The token and all secret values are
never printed. This command performs GET requests only.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from sports_api.wnba_render_attachment_readiness import (
    run_render_api_attachment_verification,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify the WNBA Step 5Y Render attachment using GET-only Render API calls.")
    parser.add_argument("--service-id", required=True)
    parser.add_argument("--service-name", default="kyre-sports-api-staging")
    parser.add_argument("--image-ref", required=True)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--step5x-identity", required=True)
    parser.add_argument("--timeout-seconds", type=float, default=15.0)
    parser.add_argument("--output", default=None, help="Optional path for the sanitized JSON report.")
    args = parser.parse_args()

    report = run_render_api_attachment_verification(
        service_id=args.service_id,
        service_name=args.service_name,
        image_ref=args.image_ref,
        release_id=args.release_id,
        revision=args.revision,
        step5x_identity=args.step5x_identity,
        timeout_seconds=args.timeout_seconds,
    )
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if report.get("passed") is True else 2


if __name__ == "__main__":
    raise SystemExit(main())
