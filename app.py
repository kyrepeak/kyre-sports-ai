'''Kyre Sports AI entrypoint — Daily Picks V18 + Assists V20 + Points preflight repair.

This cache-safe wrapper preserves the exact application at commit
6b5958d729c3999fc0188518a9dc4fb8ee63803c and applies three isolated routes:

1) WNBA Daily Picks' historical V4 import is rebound to Daily Picks V18. V18
   preserves V17 production logic and appends only passive four-market E2E
   verification.
2) The unfinished WNBA Assists fallback opens the completed Assists V20 page.
3) The preserved Points V1.9.8.4.1 import is rebound to V1.9.8.4.2, which changes
   preflight coverage only: every upcoming game still needs an exact simulatable
   projection+market pair, but a raw sportsbook player quote with no current
   projection can no longer deadlock all valid 5M distributions. Such unmatched
   quote rows remain excluded from simulation/output exactly as the production
   engine already does.

No PRA, Rebounds, MLB, Daily Picks production math, Assists production math,
Points projection math, Monte Carlo math, grading or calibration is modified.
'''
from __future__ import annotations

import subprocess
import sys
import urllib.request

import streamlit as st
import wnba_daily_picks_hub_v18 as wnba_daily_picks_v18
import wnba_assists_hub_v20 as wnba_assists_v20
import wnba_points_hub_v19842 as wnba_points_v19842

# The preserved application imports this historical module name for Daily Picks.
sys.modules["wnba_daily_picks_hub_v4"] = wnba_daily_picks_v18

# The preserved application imports V1.9.8.4.1 directly. The new wrapper imported
# the genuine V1.9.8.4.1 module before this alias is installed, then patches only
# the live preflight readiness helper on render.
sys.modules["wnba_points_hub_v19841"] = wnba_points_v19842

# Preserve the existing independent Assists navigation interception.
_ASSISTS_PREVIOUS_INFO = st.info


def _assists_v20_info(body, *args, **kwargs):
    text = str(body)
    if text.startswith("WNBA Assists is separate from") and (
        "production model page" in text or "model module" in text
    ):
        wnba_assists_v20.render_wnba_assists_hub(None, None, None, None)
        st.stop()
    return _ASSISTS_PREVIOUS_INFO(body, *args, **kwargs)


st.info = _assists_v20_info

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
        "kyre_sports_ai_preserved_app_plus_daily_picks_v18_assists_v20_points_v19842.py",
        "exec",
    ),
    globals(),
    globals(),
)
