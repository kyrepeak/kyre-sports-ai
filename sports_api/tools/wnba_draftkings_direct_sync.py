"""Operator CLI for one Step 6D DraftKings -> Kyre-owned feed sync.

No endpoint URL or account credential is accepted on the command line. Exact
DraftKings URLs are read from WNBA_DRAFTKINGS_MARKET_URLS_JSON so process lists
and shell history do not become accidental configuration stores.
"""
from __future__ import annotations

import argparse
import json

from sports_api.collectors.wnba_draftkings_direct import sync_draftkings_to_kyre_feed


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync public DraftKings WNBA prop JSON into the Kyre-owned market feed.")
    parser.add_argument("--date", required=True, help="Slate date YYYY-MM-DD")
    parser.add_argument("--season", required=True, type=int)
    args = parser.parse_args()
    report = sync_draftkings_to_kyre_feed(date=args.date, season=args.season)
    sanitized = {
        "provider_id": report["provider_id"],
        "synced": report["synced"],
        "offer_count": report["offer_count"],
        "source_summary": report["source_summary"],
        "storage": {
            "stored": report["storage"]["stored"],
            "path": report["storage"]["path"],
            "date": report["storage"]["date"],
            "season": report["storage"]["season"],
            "offer_count": report["storage"]["offer_count"],
            "content_sha256": report["storage"]["content_sha256"],
        },
        "sync_fingerprint_sha256": report["sync_fingerprint_sha256"],
        "safety": report["safety"],
    }
    print(json.dumps(sanitized, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
