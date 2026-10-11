"""Sequential Runless wrapper for the Step-8 public production certificate.

Runless executes proof-plan commands concurrently. Keeping Playwright browser
installation and the production certificate in this single command guarantees
the matching Chromium binary exists before the browser certificate launches.
"""
from __future__ import annotations

import subprocess
import sys

from .cfb_game_total_mobile_production_step8_v1 import run_public

PRODUCTION_URL = "https://pickvault.streamlit.app"
ARTIFACT_DIR = "artifacts/cfb-game-total-step8-runless"


def main() -> None:
    subprocess.run(
        [sys.executable, "-m", "playwright", "install", "chromium"],
        check=True,
    )
    run_public(base_url=PRODUCTION_URL, artifact_dir=ARTIFACT_DIR)


if __name__ == "__main__":
    main()
