'''Kyre Sports AI entrypoint — Daily Picks V18 four-market verification + Assists V20.

This cache-safe wrapper preserves the exact application at commit
6b5958d729c3999fc0188518a9dc4fb8ee63803c and applies only two isolated routes:

1) WNBA Daily Picks' historical V4 import is rebound to Daily Picks V18. V18
   preserves the complete V17 production page and appends only a passive
   same-session four-market end-to-end verification panel for PRA, Points,
   Rebounds and Assists. No ranking, selection, guard or source-model logic is
   changed by V18.
2) The unfinished WNBA Assists fallback opens the completed Assists V20 page.

No PRA, Points, Rebounds, MLB, Daily Picks production math, or Assists production
math is modified by this entrypoint.
'''
from __future__ import annotations

import subprocess
import sys
import urllib.request

import streamlit as st
import wnba_daily_picks_hub_v18 as wnba_daily_picks_v18
import wnba_assists_hub_v20 as wnba_assists_v20

# The preserved application imports this historical module name for Daily Picks.
# Rebind only that import to the new wrapper; V18 preserves V17/V16/.../V10.
sys.modules["wnba_daily_picks_hub_v4"] = wnba_daily_picks_v18

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
        "kyre_sports_ai_preserved_app_plus_daily_picks_v18_four_market_verification_and_assists_v20.py",
        "exec",
    ),
    globals(),
    globals(),
)
