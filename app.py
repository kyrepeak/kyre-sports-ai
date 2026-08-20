'''Kyre Sports AI entrypoint — Daily Picks Assists Connector Step 5 + Assists V20.

This cache-safe wrapper preserves the exact application at commit
6b5958d729c3999fc0188518a9dc4fb8ee63803c and applies only two isolated routes:

1) WNBA Daily Picks' historical V4 import is rebound to Daily Picks V15. V15
   renders the complete existing Daily Picks Steps 1–10 and Assists Connector
   Steps 1–4, then appends only Step 5 cross-market ranking integration. Assists
   is NOT yet allowed into final Top-5 selection or the final production guard.
2) The unfinished WNBA Assists fallback opens the completed Assists V20 page.

No PRA, Points, Rebounds, MLB, Daily Picks production math, or Assists production
math is modified by this entrypoint.
'''
from __future__ import annotations

import subprocess
import sys
import urllib.request

import streamlit as st
import wnba_daily_picks_hub_v15 as wnba_daily_picks_v15
import wnba_assists_hub_v20 as wnba_assists_v20

# The preserved application imports this historical module name for Daily Picks.
# Rebind only that import to the new wrapper; V15 preserves V14/V13/V12/V11/V10.
sys.modules["wnba_daily_picks_hub_v4"] = wnba_daily_picks_v15

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
        "kyre_sports_ai_preserved_app_plus_daily_picks_assists_connector_step5_and_assists_v20.py",
        "exec",
    ),
    globals(),
    globals(),
)
