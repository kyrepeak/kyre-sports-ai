'''Kyre Sports AI entrypoint — MLB V2.1.7 frozen + WNBA PRA V2.9 active.

Loads the current known-good app shell and preserves all seven proven MLB
production connectors exactly at the frozen V2.1.7 baseline. WNBA development is
active and routed through PRA V2.9 Step 6: SportsGameOdds exact-market grading on
top of the proven V2.8.x schedule/roster/context/availability/minutes-role stack.

MLB frozen baseline:
- commit 6f439a251329c588a097abc9281f0a528c3053be
- branch mlb-v217-frozen-20260818

WNBA V2.9 adds:
- SportsGameOdds leagueID=WNBA using the existing SPORTSGAMEODDS_API_KEY;
- full-game moneyline, spread and total visibility;
- player Points, Rebounds, Assists and PRA market transport;
- Step 6 exact PRA player/game/line/book matching;
- same-book, same-line no-vig grading;
- preliminary empirical model-vs-market probability/fair-price/EV calibration;
- no fabricated markets and FINAL games excluded from grading.

Opponent-defense adjustments and the production 5M/10M Monte Carlo engine are
still later WNBA steps. Sportsbook prices do not feed back into the Step-5 player
projection. MLB production probabilities, simulation depths, verified sportsbook
market gates, Step 3 Pick Strength, no-vig calculations and all seven MLB
connector formulas remain unchanged.
'''
from __future__ import annotations

import subprocess
import sys
import urllib.request

import slate_multi_provider_patch_v1 as slate_multi_provider
import wnba_pra_hub_v29 as wnba_pra_v29

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

# Cache-safe WNBA override. The inherited shell imports wnba_pra_hub_v282; map
# that compatibility name to the fresh V2.9 implementation. This is a WNBA-only
# render/import override and does not alter any frozen MLB model module.
sys.modules["wnba_pra_hub_v282"] = wnba_pra_v29

# Frozen MLB sportsbook routing stays exactly as before.
slate_multi_provider.install()

exec(compile(source, "kyre_sports_ai_mlb_v217_frozen_wnba_v29.py", "exec"), globals(), globals())
