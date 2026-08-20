'''Kyre Sports AI entrypoint — WNBA Assists Step 20 final-production routing layer.

This wrapper preserves the exact deployed application at commit
759d0052b1d0e2a739b0618a03e1fe6e4f017dff (including WNBA Daily Picks Step 10)
and changes only the unfinished WNBA Assists fallback so the existing Assists
navigation item opens the Step-20 page.

Assists V20 preserves Steps 1–19, including the corrected same-day ET tip parser,
and adds only the final risk-adjusted qualification / Top-5 publisher. It does
not change projection math, Step-16 distributions, Step-17 Monte Carlo results,
Step-18 probabilities, Step-19 EV math, or PRA/Points/Rebounds/Daily Picks
production math. It publishes up to five only and never forces five.
'''
from __future__ import annotations

import subprocess
import urllib.request

import streamlit as st
import wnba_assists_hub_v20 as wnba_assists_v20

PREVIOUS_APP_COMMIT = "759d0052b1d0e2a739b0618a03e1fe6e4f017dff"
RAW_URL = (
    "https://raw.githubusercontent.com/kyrepeak/kyre-sports-ai/"
    f"{PREVIOUS_APP_COMMIT}/app.py"
)

_ASSISTS_PREVIOUS_INFO = st.info


def _assists_step20_info(body, *args, **kwargs):
    text = str(body)
    if text.startswith("WNBA Assists is separate from") and (
        "production model page" in text or "model module" in text
    ):
        wnba_assists_v20.render_wnba_assists_hub(None, None, None, None)
        st.stop()
    return _ASSISTS_PREVIOUS_INFO(body, *args, **kwargs)


st.info = _assists_step20_info


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
        "kyre_sports_ai_preserved_daily_picks_v10_plus_wnba_assists_v20_final.py",
        "exec",
    ),
    globals(),
    globals(),
)
