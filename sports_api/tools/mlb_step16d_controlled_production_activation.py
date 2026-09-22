from __future__ import annotations

import json
from pathlib import Path

from sports_api.mlb_step16d_controlled_production_activation_v1 import (
    FINAL_CERTIFICATION_MARKER,
    run_step16d_controlled_production_activation,
)

OUTPUT_PATH = Path("mlb-step16d-controlled-production-activation.json")


def main() -> None:
    evidence = run_step16d_controlled_production_activation()
    OUTPUT_PATH.write_text(
        json.dumps(evidence, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(evidence, sort_keys=True))
    print(FINAL_CERTIFICATION_MARKER)


if __name__ == "__main__":
    main()
