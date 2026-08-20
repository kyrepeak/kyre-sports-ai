'''Kyre Sports AI entrypoint — WNBA Daily Picks Step 7 routing layer.

This cache-safe wrapper preserves the exact deployed application at commit
6b5958d729c3999fc0188518a9dc4fb8ee63803c and changes only the WNBA Daily Picks
renderer binding from V4/Step 4 to V7/Step 7.

Daily Picks V7 preserves the passive PRA, Points and Rebounds connectors, the
Step-5 common schema and Step-6 safety audit, then adds read-only duplicate and
correlation protection. It does not import production model code, launch
simulations, restore/regrade snapshots, request sportsbook/network data, refresh
injuries, alter projections, rank picks, choose best quotes, or write production
session state.
'''
from __future__ import annotations

import subprocess
import sys
import urllib.request

import wnba_daily_picks_hub_v7 as wnba_daily_picks_v7

# The preserved Step-4 entrypoint asks for `wnba_daily_picks_hub_v4`; route only
# that Daily Picks renderer to V7. V7 imports the real V6/V5/V4 presentation stack
# before this alias is installed, so all read-only helpers remain intact.
# Every PRA / Points / Rebounds / MLB production route remains preserved.
sys.modules["wnba_daily_picks_hub_v4"] = wnba_daily_picks_v7

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
        "kyre_sports_ai_preserved_app_plus_wnba_daily_picks_v7_step7_protection.py",
        "exec",
    ),
    globals(),
    globals(),
)
