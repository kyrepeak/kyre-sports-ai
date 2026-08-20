'''Kyre Sports AI entrypoint — WNBA Daily Picks Step 8 routing layer.

This cache-safe wrapper preserves the exact deployed application at commit
6b5958d729c3999fc0188518a9dc4fb8ee63803c and changes only the WNBA Daily Picks
renderer binding from V4/Step 4 to V8/Step 8.

Daily Picks V8 preserves the passive PRA, Points and Rebounds connectors, the
Step-5 common schema, Step-6 safety audit and Step-7 duplicate/correlation
protection, then adds read-only cross-market ranking. It does not import or run
production models, launch/restore simulations, request sportsbook/network data,
refresh injuries, alter projections, or write production session state.
'''
from __future__ import annotations

import subprocess
import sys
import urllib.request

import wnba_daily_picks_hub_v8 as wnba_daily_picks_v8

# The preserved Step-4 entrypoint asks for `wnba_daily_picks_hub_v4`; route only
# that Daily Picks renderer to V8. V8 imports the real V7/V6/V5/V4 presentation
# stack before this alias is installed, so all frozen read-only helpers remain
# intact. Every PRA / Points / Rebounds / MLB production route stays preserved.
sys.modules["wnba_daily_picks_hub_v4"] = wnba_daily_picks_v8

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
        "kyre_sports_ai_preserved_app_plus_wnba_daily_picks_v8_step8_ranking.py",
        "exec",
    ),
    globals(),
    globals(),
)
