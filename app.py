"""Kyre Sports AI entrypoint — Daily Game Picks V2.0.8.

Loads the current known-good app shell, preserving the full MLB/WNBA system and
all seven proven MLB production connectors, then routes Daily Game Picks through
V2.0.8 so one tap can build/resume the complete seven-market MLB card while
V2.0.7 market-neutral normalization, Step 5, Step 6, production model math,
sportsbook gates, and identity firewalls remain unchanged.
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
new = "from mlb_daily_game_picks_v208 import render_daily_game_picks"
if old not in source:
    raise RuntimeError("Could not locate Daily Game Picks route in previous app shell.")
source = source.replace(old, new, 1)
source = source.replace("Daily Game Picks V1.9.8", "Daily Game Picks V2.0.8", 1)

exec(compile(source, "kyre_sports_ai_daily_game_picks_v208.py", "exec"), globals(), globals())
