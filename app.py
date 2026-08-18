"""Kyre Sports AI entrypoint — force Daily Game Picks V1.9.2 fresh import.

Loads the last known-good full app shell, preserving every existing MLB/WNBA
module and the persistent MLB date control, then changes only the Daily Game Picks
route to the fresh V1.9.2 module name so Streamlit cannot reuse cached V1.9.1 code.
"""
from __future__ import annotations

import subprocess
import urllib.request

BASE_COMMIT = "8fb675ad2922cadbd0647e4e82ad97072029f4ca"
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
old = "from mlb_daily_game_picks_v19 import render_daily_game_picks"
new = "from mlb_daily_game_picks_v192 import render_daily_game_picks"
if old not in source:
    raise RuntimeError("Could not locate Daily Game Picks V1.9 route in previous app shell.")
source = source.replace(old, new, 1)
source = source.replace("Daily Game Picks V1.9", "Daily Game Picks V1.9.2", 1)

exec(compile(source, "kyre_sports_ai_daily_game_picks_v192.py", "exec"), globals(), globals())
