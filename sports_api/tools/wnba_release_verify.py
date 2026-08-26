"""Read-only Step 5T deployed release verifier.

Example:
python -m sports_api.tools.wnba_release_verify \
  https://api.example.com \
  --revision 0123456789abcdef0123456789abcdef01234567 \
  --image-ref ghcr.io/example/api@sha256:<64hex>
"""
from __future__ import annotations

import argparse
import json

from sports_api.wnba_release_activation_readiness import run_release_verification


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify WNBA Step 5T immutable release identity using GET requests only.")
    parser.add_argument("base_url")
    parser.add_argument("--revision", required=True)
    parser.add_argument("--image-ref", required=True)
    parser.add_argument("--release-id")
    parser.add_argument("--storage-identity")
    parser.add_argument("--timeout-seconds", type=float, default=10.0)
    args = parser.parse_args()

    result = run_release_verification(
        args.base_url,
        expected_revision=args.revision,
        expected_image_ref=args.image_ref,
        expected_release_id=args.release_id,
        expected_storage_identity=args.storage_identity,
        timeout_seconds=args.timeout_seconds,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("passed") is True else 1


if __name__ == "__main__":
    raise SystemExit(main())
