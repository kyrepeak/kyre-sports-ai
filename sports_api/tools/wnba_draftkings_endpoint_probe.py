"""Operator CLI for bounded GET-only Step 6E DraftKings WNBA endpoint probing."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from sports_api.wnba_draftkings_endpoint_discovery import probe_draftkings_wnba_endpoints


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe public DraftKings WNBA JSON endpoint candidates (GET-only).")
    parser.add_argument("--output", default=None, help="Optional sanitized JSON report path.")
    args = parser.parse_args()

    report = probe_draftkings_wnba_endpoints()
    text = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text + "\n", encoding="utf-8")
    print(text)
    # Discovery evidence is observational. A blocked/empty public endpoint does
    # not make deterministic CI fail; live_endpoint_verified carries the result.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
