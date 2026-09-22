"""Run the WNBA Step 6G DraftKings shadow-ingestion gate.

This tool is GET-only and never writes the production Kyre market feed.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from sports_api.wnba_draftkings_shadow_ingestion import run_shadow_ingestion


def main() -> int:
    parser = argparse.ArgumentParser(description="Run read-only WNBA DraftKings shadow ingestion.")
    parser.add_argument("--date", default=datetime.now(timezone.utc).date().isoformat())
    parser.add_argument("--season", type=int, default=datetime.now(timezone.utc).year)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    report = run_shadow_ingestion(date=args.date, season=args.season)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report.get("ready_for_auto_sync") else 2


if __name__ == "__main__":
    raise SystemExit(main())
