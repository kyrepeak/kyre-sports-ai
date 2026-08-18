'''Kyre Sports AI entrypoint — MLB V2.1.7 frozen + WNBA PRA V2.8.4 active.

Loads the current known-good app shell and preserves all seven proven MLB
production connectors exactly at the frozen V2.1.7 baseline. WNBA development is
active again and is routed through a cache-safe V2.8.4 module that adds the
SportsGameOdds WNBA market bridge without changing WNBA projection math.

MLB frozen baseline:
- commit 6f439a251329c588a097abc9281f0a528c3053be
- branch mlb-v217-frozen-20260818

WNBA V2.8.4 adds sportsbook transport/verification only:
- SportsGameOdds leagueID=WNBA using the existing SPORTSGAMEODDS_API_KEY;
- full-game moneyline, spread and total markets;
- player Points, Rebounds, Assists and PRA over/under markets when available;
- DraftKings, FanDuel, BetMGM and Caesars from the existing bookmaker secret;
- no WNBA probability/minutes/usage/matchup math changes yet.

MLB production probabilities, simulation depths, verified sportsbook market
gates, Step 3 Pick Strength, no-vig calculations and all seven connector formulas
remain unchanged.
'''
from __future__ import annotations

import subprocess
import sys
import urllib.request

import slate_multi_provider_patch_v1 as slate_multi_provider
import wnba_pra_hub_v284 as wnba_pra_v284

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

# Cache-safe WNBA override. The inherited shell currently imports
# wnba_pra_hub_v282; map that module name to the fresh V2.8.4 implementation so
# Streamlit cannot reuse a stale V2.8.3 module from the running Python process.
# This changes only the WNBA render/import path; no MLB file or formula is touched.
sys.modules["wnba_pra_hub_v282"] = wnba_pra_v284

# Install the shared MLB sportsbook transport exactly as before. Frozen MLB
# production behavior remains V2.1.7.
slate_multi_provider.install()

exec(compile(source, "kyre_sports_ai_mlb_v217_frozen_wnba_v284.py", "exec"), globals(), globals())
