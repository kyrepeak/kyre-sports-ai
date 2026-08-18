'''Kyre Sports AI entrypoint — MLB V2.1.7 frozen + WNBA PRA V3.2.1 frozen + Points V1.1 active.

Loads the current known-good app shell and preserves all seven proven MLB
production connectors exactly at the frozen V2.1.7 baseline.

WNBA development is now split by market page:
- PRA stays on the known-good V3.2.1 persistent Final Card checkpoint;
- Points routes to its own isolated V1.1 production page;
- Rebounds, Assists, Spread and Game Total remain isolated placeholders until
  their own production pages are built.

Frozen checkpoints:
- MLB V2.1.7: branch mlb-v217-frozen-20260818
- WNBA PRA V3.2.1: branch wnba-pra-v321-frozen-20260818
  commit 5f29fc48856a198d74bcdbde47821e55e275222a

The Points page reuses verified WNBA schedule/roster/role/matchup and
SportsGameOdds transport, but PRA totals are never used as a shortcut for the
Points projection. Points is NOT fed into the WNBA Daily Master Card until the
separate Points page passes exact-market, 5M simulation, persistence and decision
validation.

Sportsbook prices never feed back into a projection/simulation distribution.
MLB production probabilities, simulation depths, verified sportsbook market
gates, Step 3 Pick Strength, no-vig calculations and all seven MLB connector
formulas remain unchanged.
'''
from __future__ import annotations

import subprocess
import sys
import urllib.request

import slate_multi_provider_patch_v1 as slate_multi_provider
import wnba_pra_hub_v321 as wnba_pra_v321

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

# The inherited league-aware shell already isolates WNBA markets. Extend only the
# WNBA placeholder so Points gets its own page while PRA keeps its frozen route.
old_wnba_placeholder = '''    else:
        section_header(f"WNBA {market}", "WNBA market module")
        st.info(f"WNBA {market} is separate from the PRA Command Center and will get its own model module.")
        st.stop()
'''
new_wnba_placeholder = '''    elif market == "Points":
        from wnba_points_hub_v11 import render_wnba_points_hub

        render_wnba_points_hub(
            section_header,
            status_info,
            None,
            h,
        )
        st.stop()
    else:
        section_header(f"WNBA {market}", "WNBA market module")
        st.info(f"WNBA {market} is separate from the frozen PRA Command Center and will get its own production model page.")
        st.stop()
'''
if old_wnba_placeholder not in source:
    raise RuntimeError("Could not locate isolated WNBA market placeholder in inherited shell.")
source = source.replace(old_wnba_placeholder, new_wnba_placeholder, 1)

# Cache-safe PRA route: the inherited shell imports wnba_pra_hub_v282. Keep that
# compatibility name pointed at the frozen V3.2.1 implementation while Points is
# developed independently.
sys.modules["wnba_pra_hub_v282"] = wnba_pra_v321

# Frozen MLB sportsbook routing stays exactly as before.
slate_multi_provider.install()

exec(
    compile(source, "kyre_sports_ai_mlb_v217_wnba_pra_v321_frozen_points_v11.py", "exec"),
    globals(),
    globals(),
)
