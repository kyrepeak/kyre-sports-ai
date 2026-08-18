"""Kyre Sports AI entrypoint — Daily Game Picks V1.9.9.

Loads the current known-good app shell, preserving the full MLB/WNBA system and
all proven Daily Game Picks production connectors, then routes through V1.9.9 so
the 1+ Hit V2.1 fast scanner runs in bounded game batches with resumable coverage
without changing production probability or calibration math.
"""
from __future__ import annotations

import subprocess
import urllib.request

BASE_COMMIT = "06d34032b9608cba07072b02934ae3a4b7d7c295"
RAW_URL = (
    "https://raw.githubusercontent.com/kyrepeak/kyre-sports-ai/"
    f"{BASE_COMMIT}/app.py"
)


def _load_previous_app():
    try:
        return subprocess.check_output(
            ["git", "show", f"{BASE_COMMIT}:app.py"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        with urllib.request.urlopen(RAW_URL, timeout=15) as response:
            return response.read().decode("utf-8")


source = _load_previous_app()
old = "from mlb_daily_game_picks_v198 import render_daily_game_picks"
new = "from mlb_daily_game_picks_v199 import render_daily_game_picks"
if old not in source:
    raise RuntimeError("Could not locate Daily Game Picks V1.9.8 route in previous app shell.")
source = source.replace(old, new, 1)
source = source.replace("Daily Game Picks V1.9.8", "Daily Game Picks V1.9.9", 1)

exec(compile(source, "kyre_sports_ai_daily_game_picks_v199.py", "exec"), globals(), globals())
