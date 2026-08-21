'''Kyre Sports AI entrypoint — Daily Picks V18 + Assists V20 + Points preflight repair + PRA V3.6.1 speed route + WNBA Spread V1.4.

This cache-safe wrapper preserves the exact application at commit
6b5958d729c3999fc0188518a9dc4fb8ee63803c and applies five isolated routes:

1) WNBA Daily Picks' historical V4 import is rebound to Daily Picks V18. V18
   preserves V17 production logic and appends only passive four-market E2E
   verification.
2) The unfinished WNBA Assists fallback opens the completed Assists V20 page.
3) The preserved Points V1.9.8.4.1 import is rebound to V1.9.8.4.3. V1.9.8.4.2
   preserves full upcoming-game projection+exact-market coverage while excluding
   raw sportsbook player quotes that have no current projection. V1.9.8.4.3 then
   repairs the inherited sanity gate so a >35% Points deviation is a hard blocker
   only when the scoring-rate change is unexplained. A deviation driven by a
   material minutes change, with projected points/minute still inside the verified
   ±30% historical band, remains visible as MONITOR but no longer deadlocks 5M.
4) The preserved PRA V3.2.1 compatibility import is rebound to PRA V3.6.1.
   V3.6.1 preserves V3.6 model/grading/simulation math and only reuses duplicate
   Step-5 game projections + per-player variance calculations inside one render.
   The memo is reset on every Streamlit rerun; SportsGameOdds refresh is unchanged.
5) The unfinished WNBA Spread fallback opens isolated Spread V1.4. Spread V1.4
   preserves the V1.3.1 exact-spread integrity layer and adds Step 5: an independent
   projected score/margin model using date-cut season/recent scoring, venue splits,
   recent pace/efficiency and verified availability. Sportsbook lines/prices are
   explicitly excluded from projection inputs. Cover probability and Monte Carlo
   remain off.

No PRA projection/grading/calibration math, Rebounds, MLB, Daily Picks production
math, Assists production math, Points projection math, or existing Monte Carlo math
is modified.
'''
from __future__ import annotations

import subprocess
import sys
import urllib.request

import streamlit as st
import wnba_daily_picks_hub_v18 as wnba_daily_picks_v18
import wnba_assists_hub_v20 as wnba_assists_v20
import wnba_points_hub_v19843 as wnba_points_v19843
import wnba_pra_hub_v361 as wnba_pra_v361
import wnba_spread_hub_v14 as wnba_spread_v14

# The preserved application imports this historical module name for Daily Picks.
sys.modules["wnba_daily_picks_hub_v4"] = wnba_daily_picks_v18

# The preserved application imports V1.9.8.4.1 directly. The new wrapper imported
# the genuine V1.9.8.4.1 module before this alias is installed, then patches only
# the live Points preflight coverage + explainable sanity-gate helpers on render.
sys.modules["wnba_points_hub_v19841"] = wnba_points_v19843

# Cache-safe PRA route: the preserved application imports this compatibility name
# before it later aliases the older V2.8.2 path. Rebinding here guarantees a
# long-lived Streamlit process cannot keep the pre-performance V3.6 object.
sys.modules["wnba_pra_hub_v321"] = wnba_pra_v361

# Preserve the existing fallback behavior while intercepting only unfinished
# WNBA pages that now have isolated production/foundation modules.
_PREVIOUS_INFO = st.info


def _wnba_market_route_info(body, *args, **kwargs):
    text = str(body)
    unfinished = "production model page" in text or "model module" in text
    if text.startswith("WNBA Assists is separate from") and unfinished:
        wnba_assists_v20.render_wnba_assists_hub(None, None, None, None)
        st.stop()
    if text.startswith("WNBA Spread is separate from") and unfinished:
        wnba_spread_v14.render_wnba_spread_hub(None, None, None, None)
        st.stop()
    return _PREVIOUS_INFO(body, *args, **kwargs)


st.info = _wnba_market_route_info

PREVIOUS_APP_COMMIT = "6b5958d729c3999fc0188518a9dc4fb8ee63803c"
RAW_URL = (
    "https://raw.githubusercontent.com/kyrepeak/kyre-sports-ai/"
    f"{PREVIOUS_APP_COMMIT}/app.py"
)


def _load_previous_app() -> str:
    try:
        return subprocess.check_output(
            ["git", "show", f"{PREVIOUS_APP_COMMIT}:app.py"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        with urllib.request.urlopen(RAW_URL, timeout=15) as response:
            return response.read().decode("utf-8")


source = _load_previous_app()
exec(
    compile(
        source,
        "kyre_sports_ai_preserved_app_plus_daily_picks_v18_assists_v20_points_v19843_pra_v361_spread_v14.py",
        "exec",
    ),
    globals(),
    globals(),
)
