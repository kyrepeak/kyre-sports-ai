'''Kyre Sports AI entrypoint — Daily Game Picks V2.1.7.

Loads the current known-good app shell, preserving the full MLB/WNBA system and
all seven proven MLB production connectors, then routes Daily Game Picks through
V2.1.7 risk-aware Final Card selection on top of the V2.1.6b mobile-safe command
center, V2.1.5 multi-provider sportsbook transport, V2.1.4b cooldown quarantine,
V2.1.3 persistent completed-card storage, and V2.1.2.x official-MLB live-risk layer.

V2.1.7 changes only Final Card decision orchestration and presentation:
- BEST BET / STRONG / MONITOR / AVOID hierarchy;
- stronger Why-this-pick explanations;
- critical starter/lineup/weather/staleness conditions auto-remove a candidate;
- confirmed hitter props must actually appear in the official starting lineup;
- unresolved MONITOR candidates receive a small selection-priority penalty so a
  comparably strong confirmed-safe candidate can replace them;
- Run Line/Total shared sportsbook-cache freshness is guarded.

Production probabilities, simulation depths, verified sportsbook market gates,
Step 3 Pick Strength, no-vig calculations and all seven connector formulas remain
unchanged. SportsGameOdds stays primary with Odds-API.io fallback.
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
new = "from mlb_daily_game_picks_v217_guard import render_daily_game_picks"
if old not in source:
    raise RuntimeError("Could not locate Daily Game Picks route in previous app shell.")
source = source.replace(old, new, 1)
source = source.replace("Daily Game Picks V1.9.8", "Daily Game Picks V2.1.7", 1)

# Install the shared sportsbook transport BEFORE the inherited shell renders the
# Slate. This makes SportsGameOdds-primary routing independent of which V20.9
# wrapper the historical app shell imports.
slate_multi_provider.install()

exec(compile(source, "kyre_sports_ai_daily_game_picks_v217.py", "exec"), globals(), globals())
