'''Kyre Sports AI entrypoint — WNBA Daily Picks Step 4 routing layer.

This cache-safe wrapper preserves the exact previously deployed application at
commit 6fb976a9e20c96eb68b71ad0d3511e3be1734292 and changes only the WNBA Daily
Picks renderer binding from V3/Step 3 to V4/Step 4.

Daily Picks V4 adds a passive Rebounds connector beside the already-passive PRA
and Points connectors. It does not import Rebounds production code, launch a
simulation, restore/regrade a snapshot, request sportsbook/network data, refresh
injuries, alter projections, write production state, or enable Top-5 ranking.
All PRA, Points, Rebounds and MLB production routes remain owned by the preserved
previous entrypoint.
'''
from __future__ import annotations

import subprocess
import sys
import urllib.request

import wnba_daily_picks_hub_v4 as wnba_daily_picks_v4

# Importing V4 loads the prior V3 Daily Picks UI helpers first. Only after that
# import is complete do we install this compatibility alias. The preserved prior
# app still asks for `wnba_daily_picks_hub_v3`; it therefore receives V4 without
# any change to PRA/Points/Rebounds production routing.
sys.modules["wnba_daily_picks_hub_v3"] = wnba_daily_picks_v4

PREVIOUS_APP_COMMIT = "6fb976a9e20c96eb68b71ad0d3511e3be1734292"
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
        "kyre_sports_ai_preserved_app_plus_wnba_daily_picks_v4_step4_rebounds_readonly.py",
        "exec",
    ),
    globals(),
    globals(),
)
