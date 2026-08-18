"""Kyre Sports AI entrypoint — Daily Game Picks V1.9.6.

Loads the current known-good app shell, preserving the full MLB/WNBA system and
the proven Moneyline V1.9.2 + Pitcher K V1.8.2 + H+R+RBI V1.7.1 connectors,
then routes Daily Game Picks through the fresh V1.9.6 bridge so Home Run V1.6.1
full-slate orchestration is live without changing calibrated HR V1.1 math.
"""
from __future__ import annotations

import subprocess
import urllib.request

BASE_COMMIT = "7205a866e3e405766d87736bf1bd7106164062d6"
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
old = "from mlb_daily_game_picks_v195 import render_daily_game_picks"
new = "from mlb_daily_game_picks_v196 import render_daily_game_picks"
if old not in source:
    raise RuntimeError("Could not locate Daily Game Picks V1.9.5 route in previous app shell.")
source = source.replace(old, new, 1)
source = source.replace("Daily Game Picks V1.9.5", "Daily Game Picks V1.9.6", 1)

exec(compile(source, "kyre_sports_ai_daily_game_picks_v196.py", "exec"), globals(), globals())
