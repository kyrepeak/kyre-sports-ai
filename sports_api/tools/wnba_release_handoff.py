"""Create a sanitized WNBA Step 5V release/staging handoff bundle."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from sports_api.wnba_release_publication_handoff import write_release_handoff_bundle


def main() -> int:
    parser = argparse.ArgumentParser(description="Write the WNBA Step 5V release publication handoff bundle.")
    parser.add_argument("output_dir", nargs="?", default=".wnba-step5v-handoff")
    args = parser.parse_args()
    result = write_release_handoff_bundle(Path(args.output_dir))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
