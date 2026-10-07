from __future__ import annotations

import os
import subprocess
import sys

if os.getenv("WNBA_STEP3_GAME_HANDOFF_GREEN_CHILD") != "1":
    env = os.environ.copy()
    env["WNBA_STEP3_GAME_HANDOFF_GREEN_CHILD"] = "1"
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "tests/test_wnba_data_step3_player_shell_handoff.py"],
        env=env,
        capture_output=True,
        text=True,
    )
    if result.stdout:
        print(result.stdout, end="", flush=True)
    if result.stderr:
        print(result.stderr, end="", file=sys.stderr, flush=True)
    print(f"WNBA_STEP3_GAME_HANDOFF_GREEN_RC={result.returncode}", flush=True)
