"""Kyre Sports AI entrypoint — Daily Game Picks V1.9.7.

Loads the current known-good app shell, preserving the full MLB/WNBA system and
all proven Daily Game Picks production connectors, then routes through V1.9.7 so
the Home Run candidate intake can recover from stale empty MLB lineup-cache data
without changing calibrated HR V1.1 probability math.
"""
from __future__ import annotations

import subprocess
import urllib.request

BASE_COMMIT = "ecc8506c7b1e62d710c1e6152cd066f21229a53c"
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
old = "from mlb_daily_game_picks_v196 import render_daily_game_picks"
new = "from mlb_daily_game_picks_v197 import render_daily_game_picks"
if old not in source:
    raise RuntimeError("Could not locate Daily Game Picks V1.9.6 route in previous app shell.")
source = source.replace(old, new, 1)
source = source.replace("Daily Game Picks V1.9.6", "Daily Game Picks V1.9.7", 1)

exec(compile(source, "kyre_sports_ai_daily_game_picks_v197.py", "exec"), globals(), globals())
