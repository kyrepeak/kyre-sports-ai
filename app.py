"""Kyre Sports AI entrypoint — Daily Game Picks V1.9.5.

Loads the current known-good app shell, preserving the full MLB/WNBA system and
the proven Moneyline V1.9.2 + Pitcher K V1.8.2 connectors, then routes Daily Game
Picks through the fresh V1.9.5 bridge so H+R+RBI V1.7.1 full-slate orchestration
is live without changing production probability math.
"""
from __future__ import annotations

import subprocess
import urllib.request

BASE_COMMIT = "82f19306e6b9e949f5b3604539ba6014e3ca029d"
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
old = "from mlb_daily_game_picks_v194 import render_daily_game_picks"
new = "from mlb_daily_game_picks_v195 import render_daily_game_picks"
if old not in source:
    raise RuntimeError("Could not locate Daily Game Picks V1.9.4 route in previous app shell.")
source = source.replace(old, new, 1)
source = source.replace("Daily Game Picks V1.9.4", "Daily Game Picks V1.9.5", 1)

exec(compile(source, "kyre_sports_ai_daily_game_picks_v195.py", "exec"), globals(), globals())
