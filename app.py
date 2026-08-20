'''Kyre Sports AI entrypoint — WNBA Assists Step 17 Monte Carlo routing layer.

This wrapper preserves the exact deployed application at commit
759d0052b1d0e2a739b0618a03e1fe6e4f017dff (including WNBA Daily Picks Step 10)
and changes only the unfinished WNBA Assists fallback so the existing Assists
navigation item opens the Step-17 page.

Assists V17 preserves Steps 1–16, keeps the sportsbook/no-vig branch separate,
and adds only the explicit 5,000,000-trial-per-player Monte Carlo validation,
convergence diagnostics and sensitivity layer. Step 17 does not create
line-specific O/U probabilities, calculate EV, rank picks, or change PRA,
Points, Rebounds or Daily Picks production math.
'''
from __future__ import annotations

import subprocess
import urllib.request

import streamlit as st
import wnba_assists_hub_v17 as wnba_assists_v17

PREVIOUS_APP_COMMIT = "759d0052b1d0e2a739b0618a03e1fe6e4f017dff"
RAW_URL = (
    "https://raw.githubusercontent.com/kyrepeak/kyre-sports-ai/"
    f"{PREVIOUS_APP_COMMIT}/app.py"
)

_ASSISTS_PREVIOUS_INFO = st.info


def _assists_step17_info(body, *args, **kwargs):
    text = str(body)
    if text.startswith("WNBA Assists is separate from") and (
        "production model page" in text or "model module" in text
    ):
        wnba_assists_v17.render_wnba_assists_hub(None, None, None, None)
        st.stop()
    return _ASSISTS_PREVIOUS_INFO(body, *args, **kwargs)


st.info = _assists_step17_info


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
        "kyre_sports_ai_preserved_daily_picks_v10_plus_wnba_assists_v17_monte_carlo.py",
        "exec",
    ),
    globals(),
    globals(),
)
