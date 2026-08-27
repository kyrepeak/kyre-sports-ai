from __future__ import annotations

import argparse
import json
import sys

from sports_api.wnba_hosted_staging_readiness import run_hosted_staging_smoke


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify a hosted WNBA staging release with GET-only checks.")
    parser.add_argument("base_url")
    parser.add_argument("--revision", required=True)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--storage-identity", required=True)
    parser.add_argument("--service-name")
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args(argv)

    result = run_hosted_staging_smoke(
        args.base_url,
        expected_revision=args.revision,
        expected_release_id=args.release_id,
        expected_storage_identity=args.storage_identity,
        expected_service_name=args.service_name,
        timeout_seconds=args.timeout,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("passed") else 1


if __name__ == "__main__":
    sys.exit(main())
