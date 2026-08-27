"""Read-only WNBA Step 5S live deployment smoke runner.

Examples:
  python -m sports_api.tools.wnba_live_smoke https://api.example.com
  python -m sports_api.tools.wnba_live_smoke https://api.example.com --expect-scheduler-ready

This script never calls the manual refresh endpoint.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

from sports_api.wnba_deployment_smoke_readiness import (
    SMOKE_BASE_URL_ENV,
    run_live_smoke,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the read-only WNBA Step 5S deployment smoke test.")
    parser.add_argument(
        "base_url",
        nargs="?",
        default=os.environ.get(SMOKE_BASE_URL_ENV),
        help=f"Deployed API base URL. Defaults to {SMOKE_BASE_URL_ENV}.",
    )
    parser.add_argument(
        "--expect-scheduler-ready",
        action="store_true",
        help="Require the Step 5R runtime health endpoint to be green (HTTP 200).",
    )
    parser.add_argument("--timeout", type=float, default=10.0, help="Per-request timeout in seconds (max 60).")
    args = parser.parse_args()
    if not args.base_url:
        parser.error(f"base_url is required or set {SMOKE_BASE_URL_ENV}.")

    result = run_live_smoke(
        args.base_url,
        expect_scheduler_ready=args.expect_scheduler_ready,
        timeout_seconds=args.timeout,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("passed") is True else 1


if __name__ == "__main__":
    sys.exit(main())
