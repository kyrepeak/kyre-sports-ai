'''Kyre Sports AI entrypoint — WNBA Assists Step 11 pace routing layer.

This wrapper preserves the exact deployed application at commit
759d0052b1d0e2a739b0618a03e1fe6e4f017dff (including WNBA Daily Picks Step 10)
and changes only the unfinished WNBA Assists fallback so the existing Assists
navigation item opens the Step-11 page.

Assists V11 preserves Steps 1–10 and adds only season + L10/L5/L3 pace and
expected possession-volume context derived from completed WNBA box scores.
No H2H, final assist projection, SportsGameOdds, market grading, Monte Carlo,
PRA, Points, Rebounds or Daily Picks production math is added by this route.
'''
from __future__ import annotations

import subprocess
import urllib.request

import streamlit as st
import wnba_assists_hub_v11 as wnba_assists_v11

PREVIOUS_APP_COMMIT = "759d0052b1d0e2a739b0618a03e1fe6e4f017dff"
RAW_URL = (
    "https://raw.githubusercontent.com/kyrepeak/kyre-sports-ai/"
    f"{PREVIOUS_APP_COMMIT}/app.py"
)

# The preserved WNBA shell already exposes Assists in its market selector but
# routes unfinished markets through a generic st.info fallback. Intercept only
# that Assists fallback. Rebounds/Daily Picks guards remain unchanged.
_ASSISTS_PREVIOUS_INFO = st.info


def _assists_step11_info(body, *args, **kwargs):
    text = str(body)
    if text.startswith("WNBA Assists is separate from") and (
        "production model page" in text or "model module" in text
    ):
        wnba_assists_v11.render_wnba_assists_hub(None, None, None, None)
        st.stop()
    return _ASSISTS_PREVIOUS_INFO(body, *args, **kwargs)


st.info = _assists_step11_info


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
        "kyre_sports_ai_preserved_daily_picks_v10_plus_wnba_assists_v11_step11.py",
        "exec",
    ),
    globals(),
    globals(),
)
