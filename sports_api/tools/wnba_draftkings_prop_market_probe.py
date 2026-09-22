from __future__ import annotations

import argparse
import json
from pathlib import Path

from sports_api.wnba_draftkings_prop_market_discovery import probe_draftkings_wnba_prop_markets


def main() -> None:
    parser = argparse.ArgumentParser(description="Read-only WNBA DraftKings prop-market discovery probe")
    parser.add_argument("--output", help="Optional JSON output path")
    args = parser.parse_args()

    report = probe_draftkings_wnba_prop_markets()
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
