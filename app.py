'''Kyre Sports AI entrypoint — WNBA Daily Picks Step 5 routing layer.

This cache-safe wrapper preserves the exact deployed application at commit
6b5958d729c3999fc0188518a9dc4fb8ee63803c and changes only the WNBA Daily Picks
renderer binding from V4/Step 4 to V5/Step 5.

Daily Picks V5 adds a passive common-schema adapter over the already-passive PRA,
Points and Rebounds connectors. It does not import production model code, launch
simulations, restore/regrade snapshots, request sportsbook/network data, refresh
injuries, alter projections, rank picks, or write production session state.
'''
from __future__ import annotations

import subprocess
import sys
import urllib.request

import wnba_daily_picks_hub_v5 as wnba_daily_picks_v5

# Step 5 imports Step 4 as its UI compatibility layer. Step 4 itself keeps the
# original Step-3 presentation helpers on its nested `ui` module. Promote only
# those display helpers so Step 5 can render without reaching into production
# state or changing any model behavior.
_v4_ui = getattr(wnba_daily_picks_v5, "ui", None)
_v3_ui = getattr(_v4_ui, "ui", None) if _v4_ui is not None else None
for _helper in ("_status_card", "_pra_preview_display", "_points_preview_display"):
    if _v4_ui is not None and not hasattr(_v4_ui, _helper) and _v3_ui is not None and hasattr(_v3_ui, _helper):
        setattr(_v4_ui, _helper, getattr(_v3_ui, _helper))

# V5 imports the real V4 module before this alias is installed. The preserved
# Step-4 entrypoint asks for `wnba_daily_picks_hub_v4`; it therefore receives V5
# while every PRA / Points / Rebounds / MLB production route stays preserved.
sys.modules["wnba_daily_picks_hub_v4"] = wnba_daily_picks_v5

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
        "kyre_sports_ai_preserved_app_plus_wnba_daily_picks_v5_step5_common_schema.py",
        "exec",
    ),
    globals(),
    globals(),
)
