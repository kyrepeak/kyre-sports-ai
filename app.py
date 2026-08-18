'''Kyre Sports AI entrypoint — MLB V2.1.7 frozen + WNBA V3.3 active.

Loads the current known-good app shell and preserves all seven proven MLB
production connectors exactly at the frozen V2.1.7 baseline. WNBA development is
active and routed through V3.3 with PRA + Points production connectors and one
unified WNBA Daily Master Card.

MLB frozen baseline:
- commit 6f439a251329c588a097abc9281f0a528c3053be
- branch mlb-v217-frozen-20260818

WNBA V3.3 keeps the proven PRA stack:
- verified schedule, current rosters, matchup context, availability and minutes/role;
- SportsGameOdds leagueID=WNBA transport;
- exact PRA player/game/line/book matching and same-book no-vig grading;
- capped component matchup + pace adjustments;
- empirical correlated PTS/REB/AST covariance from verified prior game logs;
- actual 5,000,000 standard / 10,000,000 finalist Monte Carlo;
- reload-safe completed-simulation summary persistence.

V3.3 adds the independent Points production connector:
- points-only projection from verified minutes/role (PRA is never used as a shortcut);
- points-specific matchup/pace adjustment already produced by the component model;
- exact SportsGameOdds Points Over/Under same-book pairs;
- empirical points variance from verified historical WNBA game logs;
- actual 5M standard / optional 10M finalist Monte Carlo with seed, batches,
  MC standard error, max batch difference and convergence reporting;
- Points summary persistence across reloads/redeploys;
- unified WNBA Daily Master Card where PRA + Points compete slate-wide;
- no forced five, one final pick per game, and no repeated player.

Sportsbook prices never feed back into the projection/simulation distribution.
MLB production probabilities, simulation depths, verified sportsbook market
gates, Step 3 Pick Strength, no-vig calculations and all seven MLB connector
formulas remain unchanged.
'''
from __future__ import annotations

import subprocess
import sys
import urllib.request

import slate_multi_provider_patch_v1 as slate_multi_provider
import wnba_pra_hub_v33 as wnba_v33

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
# that compatibility name to the fresh V3.3 implementation. This is a WNBA-only
# render/import override and does not alter any frozen MLB model module.
sys.modules["wnba_pra_hub_v282"] = wnba_v33

# Frozen MLB sportsbook routing stays exactly as before.
slate_multi_provider.install()

exec(compile(source, "kyre_sports_ai_mlb_v217_frozen_wnba_v33.py", "exec"), globals(), globals())
