"""Build the WNBA Step 6I live reconciled-sync attestation without writing."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from sports_api.wnba_reconciled_direct_sync import build_reconciled_sync_attestation


def main() -> int:
    parser = argparse.ArgumentParser(description="Run GET-only WNBA Step 6I sync attestation probe.")
    parser.add_argument("--date", default=datetime.now(timezone.utc).date().isoformat())
    parser.add_argument("--season", type=int, default=datetime.now(timezone.utc).year)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    report = build_reconciled_sync_attestation(date=args.date, season=args.season)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("reconciliation_ready") and report.get("would_sync_if_enabled") else 2


if __name__ == "__main__":
    raise SystemExit(main())
