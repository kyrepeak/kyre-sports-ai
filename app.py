'''Kyre Sports AI entrypoint — WNBA Assists Step 1 isolated routing layer.

This wrapper preserves the exact deployed application at commit
759d0052b1d0e2a739b0618a03e1fe6e4f017dff (including WNBA Daily Picks Step 10)
and changes only the unfinished WNBA Assists fallback so the existing Assists
navigation item opens the new isolated Step-1 page.

Assists V1 Step 1 is display-only: no schedule, roster, injury, sportsbook,
projection, Monte Carlo, PRA, Points, Rebounds or Daily Picks production module
is imported by the Assists page. All existing production routes remain owned by
the preserved application.
'''
from __future__ import annotations

import subprocess
import urllib.request

import streamlit as st
import wnba_assists_hub_v1 as wnba_assists_v1

PREVIOUS_APP_COMMIT = "759d0052b1d0e2a739b0618a03e1fe6e4f017dff"
RAW_URL = (
    "https://raw.githubusercontent.com/kyrepeak/kyre-sports-ai/"
    f"{PREVIOUS_APP_COMMIT}/app.py"
)

# The preserved WNBA shell already exposes Assists in its market selector but
# routes unfinished markets through a generic st.info fallback. Intercept only
# that Assists fallback. The preserved shell later layers its Rebounds/Daily
# Picks guards on top of this function, so those routes remain unchanged.
_ASSISTS_PREVIOUS_INFO = st.info


def _assists_step1_info(body, *args, **kwargs):
    text = str(body)
    if text.startswith("WNBA Assists is separate from") and (
        "production model page" in text or "model module" in text
    ):
        wnba_assists_v1.render_wnba_assists_hub(None, None, None, None)
        st.stop()
    return _ASSISTS_PREVIOUS_INFO(body, *args, **kwargs)


st.info = _assists_step1_info


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
        "kyre_sports_ai_preserved_daily_picks_v10_plus_wnba_assists_v1_step1.py",
        "exec",
    ),
    globals(),
    globals(),
)
