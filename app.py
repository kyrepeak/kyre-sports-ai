'''Kyre Sports AI entrypoint — Daily Game Picks V2.1.6b.

Loads the current known-good app shell, preserving the full MLB/WNBA system and
all seven proven MLB production connectors, then routes Daily Game Picks through
V2.1.6b mobile-safe command-center presentation on top of V2.1.5 multi-provider
sportsbook transport, V2.1.4b cooldown quarantine, V2.1.3 persistent completed-card
storage, and the V2.1.2.x live-risk/market-gap decision screen.

V2.1.5 keeps SportsGameOdds as the primary sportsbook source when
SPORTSGAMEODDS_API_KEY is configured and keeps Odds-API.io as automatic fallback.
V2.1.6b adds readiness/provider/cache/next-action visibility only and forces the
mobile command-center layout to use inline styling for Safari/Streamlit stability.
The app-shell sportsbook patch gives the MLB Slate V20.9 board the same provider
routing. Both providers are normalized into the existing sportsbook snapshot
contract, so production model math, simulation depths, no-vig calculations,
sportsbook market verification gates, normalization, Step 5/6 selection rules,
team logos, confidence badges, and identity firewalls remain unchanged.
'''
from __future__ import annotations

import subprocess
import urllib.request

import slate_multi_provider_patch_v1 as slate_multi_provider

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
new = "from mlb_daily_game_picks_v216 import render_daily_game_picks"
if old not in source:
    raise RuntimeError("Could not locate Daily Game Picks route in previous app shell.")
source = source.replace(old, new, 1)
source = source.replace("Daily Game Picks V1.9.8", "Daily Game Picks V2.1.6b", 1)

# Install the shared sportsbook transport BEFORE the inherited shell renders the
# Slate. This makes SportsGameOdds-primary routing independent of which V20.9
# wrapper the historical app shell imports.
slate_multi_provider.install()

exec(compile(source, "kyre_sports_ai_daily_game_picks_v216b.py", "exec"), globals(), globals())
