'''Kyre Sports AI entrypoint — MLB V2.1.7 frozen + WNBA PRA V3.1.1 active.

Loads the current known-good app shell and preserves all seven proven MLB
production connectors exactly at the frozen V2.1.7 baseline. WNBA development is
active and routed through PRA V3.1.1 Step 8 on top of the proven V3.0
schedule/roster/context/availability/minutes-role/matchup stack and V2.9 exact
SportsGameOdds market grading.

MLB frozen baseline:
- commit 6f439a251329c588a097abc9281f0a528c3053be
- branch mlb-v217-frozen-20260818

WNBA V3.1.1 keeps:
- SportsGameOdds leagueID=WNBA using the existing SPORTSGAMEODDS_API_KEY;
- full-game moneyline, spread and total visibility;
- player Points, Rebounds, Assists and PRA market transport;
- exact PRA player/game/line/book matching and same-book no-vig grading;
- separate capped PTS/REB/AST matchup + pace adjustments;
- H2H descriptive only; confirmed starters/lineups never inferred;
- no fabricated markets and FINAL games excluded from grading;
- actual 5,000,000 standard / 10,000,000 finalist Monte Carlo counts with
  deterministic seed, batch count, MC standard error and convergence reporting.

WNBA V3.1.1 fixes the empirical covariance handoff exposed by V3.1 diagnostics:
- existing verified player-id game logs remain first priority;
- ESPN WNBA team + normalized player-name game-summary logs are the verified
  fallback before any independent variance is allowed;
- PTS/REB/AST sample standard deviations and correlations are computed from the
  actual prior game log when >=5 games are available;
- old V3.1 stored 5M results are invalidated once so the user cannot silently
  view fallback covariance results under the hotfix label.

Sportsbook prices never feed back into the player projection/simulation mean.
MLB production probabilities, simulation depths, verified sportsbook market
gates, Step 3 Pick Strength, no-vig calculations and all seven MLB connector
formulas remain unchanged.
'''
from __future__ import annotations

import subprocess
import sys
import urllib.request

import slate_multi_provider_patch_v1 as slate_multi_provider
import wnba_pra_hub_v311 as wnba_pra_v311

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
# that compatibility name to the fresh V3.1.1 implementation. This is a WNBA-only
# render/import override and does not alter any frozen MLB model module.
sys.modules["wnba_pra_hub_v282"] = wnba_pra_v311

# Frozen MLB sportsbook routing stays exactly as before.
slate_multi_provider.install()

exec(compile(source, "kyre_sports_ai_mlb_v217_frozen_wnba_v311.py", "exec"), globals(), globals())
