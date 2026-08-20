'''Kyre Sports AI entrypoint — WNBA Assists Step 16 distribution routing layer.

This wrapper preserves the exact deployed application at commit
759d0052b1d0e2a739b0618a03e1fe6e4f017dff (including WNBA Daily Picks Step 10)
and changes only the unfinished WNBA Assists fallback so the existing Assists
navigation item opens the Step-16 page.

Assists V16 preserves Steps 1–15, keeps the sportsbook/no-vig branch separate,
and adds only analytical uncertainty + discrete assist-count distribution
calibration around the market-independent Step-15 mean. It does not run Monte
Carlo, create line-specific O/U probabilities, calculate EV, or change PRA,
Points, Rebounds or Daily Picks production math.
'''
from __future__ import annotations

import subprocess
import urllib.request

import streamlit as st
import wnba_assists_hub_v16 as wnba_assists_v16

PREVIOUS_APP_COMMIT = "759d0052b1d0e2a739b0618a03e1fe6e4f017dff"
RAW_URL = (
    "https://raw.githubusercontent.com/kyrepeak/kyre-sports-ai/"
    f"{PREVIOUS_APP_COMMIT}/app.py"
)

_ASSISTS_PREVIOUS_INFO = st.info


def _assists_step16_info(body, *args, **kwargs):
    text = str(body)
    if text.startswith("WNBA Assists is separate from") and (
        "production model page" in text or "model module" in text
    ):
        wnba_assists_v16.render_wnba_assists_hub(None, None, None, None)
        st.stop()
    return _ASSISTS_PREVIOUS_INFO(body, *args, **kwargs)


st.info = _assists_step16_info


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
        "kyre_sports_ai_preserved_daily_picks_v10_plus_wnba_assists_v16_distribution.py",
        "exec",
    ),
    globals(),
    globals(),
)
