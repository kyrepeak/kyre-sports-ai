from __future__ import annotations

import argparse
import json
import sys

from sports_api.wnba_real_staging_deployment import run_real_staging_smoke


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Verify the real WNBA Step 5X hosted staging deployment with GET-only checks."
    )
    parser.add_argument("base_url")
    parser.add_argument("--revision", required=True)
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--image-ref", required=True)
    parser.add_argument("--service-name", required=True)
    parser.add_argument("--storage-identity", required=True)
    parser.add_argument("--checkpoint")
    parser.add_argument("--timeout", type=float, default=10.0)
    args = parser.parse_args(argv)

    result = run_real_staging_smoke(
        args.base_url,
        expected_revision=args.revision,
        expected_release_id=args.release_id,
        expected_image_ref=args.image_ref,
        expected_service_name=args.service_name,
        expected_storage_identity=args.storage_identity,
        expected_checkpoint=args.checkpoint,
        timeout_seconds=args.timeout,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("passed") else 1


if __name__ == "__main__":
    sys.exit(main())
