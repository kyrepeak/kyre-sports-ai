#!/usr/bin/env python3
"""Validate or atomically import a Kyre-owned WNBA market feed JSON file."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from sports_api.collectors.wnba_kyre_market_feed import (
    validate_kyre_market_feed,
    write_kyre_market_feed,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Import a Kyre-owned WNBA market feed.")
    parser.add_argument("--input", required=True, help="Path to the JSON feed envelope.")
    parser.add_argument("--destination", default=None, help="Optional absolute destination path.")
    parser.add_argument("--dry-run", action="store_true", help="Validate without writing.")
    args = parser.parse_args()

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    validated = validate_kyre_market_feed(payload)
    if args.dry_run:
        result = {
            "valid": True,
            "stored": False,
            "date": validated["date"],
            "season": validated["season"],
            "captured_at_utc": validated["captured_at_utc"],
            "offer_count": len(validated["offers"]),
            "network_used": False,
            "secret_values_returned": False,
        }
    else:
        result = write_kyre_market_feed(validated, path=args.destination)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
