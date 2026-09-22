from __future__ import annotations

import json
from pathlib import Path

from sports_api.mlb_step16c_live_postgresql_canary_v1 import (
    FINAL_CERTIFICATION_MARKER,
    run_step16c_live_postgresql_canary_sync,
)

OUTPUT_PATH = Path("mlb-step16c-live-postgresql-canary.json")

def main() -> None:
    evidence = run_step16c_live_postgresql_canary_sync()
    OUTPUT_PATH.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(evidence, sort_keys=True))
    print(FINAL_CERTIFICATION_MARKER)

if __name__ == "__main__":
    main()
