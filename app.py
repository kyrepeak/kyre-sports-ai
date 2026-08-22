'''Kyre Sports AI entrypoint — Daily Picks V28.1 + isolated WNBA production routes.

This cache-safe wrapper preserves the exact application at commit
6b5958d729c3999fc0188518a9dc4fb8ee63803c and applies the existing isolated WNBA
routes without changing source-model math.

Daily Picks V28.1 preserves the complete V21 seven-market production/verification
surface and the independently verified controller Steps 1-6: shell, 7/7 preflight,
PRA 5M, Points 5M, Rebounds native Step 17, and Assists native Step 17. Step 7
keeps the current Spread V1.6.1 execution adapter through its native V1.6 Step-7
5,000,000-draw Monte Carlo boundary and repairs only the controller's Step-5 module
traversal so it follows the same source chain as the working Spread page:
V1.6.1 -> V1.6 -> V1.5.2 -> V1.5 -> V1.4._render_step5.

The adapter preserves exact-day availability, Steps 1-6 source readiness, exactly
5,000,000 unique final-margin draws per eligible game, 20 x 250,000 streaming
batches, coherent same-game reuse across books, source convergence and native
Step-7 persistence. Moneyline and Game Total execution adapters remain unwired and
Run All 7 remains disabled until every adapter is independently verified.

Existing isolated routes remain unchanged: Assists V20, Points V1.9.8.4.5, PRA
V3.6.1, Spread V1.6.1, Moneyline V1.5 and Game Total V1.5. The runtime WNBA market
selectbox patch continues to expose Points, Rebounds, Assists, PRA, Spread,
Moneyline, Game Total and Daily Picks while preserving PRA at index 3/default.
'''
from __future__ import annotations

import subprocess
import sys
import urllib.request

import streamlit as st
import wnba_daily_picks_hub_v281 as wnba_daily_picks_v281
import wnba_assists_hub_v20 as wnba_assists_v20
import wnba_points_hub_v19845 as wnba_points_v19845
import wnba_pra_hub_v361 as wnba_pra_v361
import wnba_spread_hub_v161 as wnba_spread_v161
import wnba_moneyline_hub_v15 as wnba_moneyline_v15
import wnba_game_total_hub_v15 as wnba_game_total_v15

# The preserved application imports this historical module name for Daily Picks.
sys.modules["wnba_daily_picks_hub_v4"] = wnba_daily_picks_v281

# The preserved application imports V1.9.8.4.1 directly. The wrapper patches only
# the live Points preflight/readiness/sanity quarantine helpers on render.
sys.modules["wnba_points_hub_v19841"] = wnba_points_v19845

# Cache-safe PRA route.
sys.modules["wnba_pra_hub_v321"] = wnba_pra_v361

# Preserve existing fallback behavior while intercepting only unfinished WNBA
# pages that now have isolated production/foundation modules.
_PREVIOUS_INFO = st.info


def _wnba_market_route_info(body, *args, **kwargs):
    text = str(body)
    unfinished = "production model page" in text or "model module" in text
    if text.startswith("WNBA Assists is separate from") and unfinished:
        wnba_assists_v20.render_wnba_assists_hub(None, None, None, None)
        st.stop()
    if text.startswith("WNBA Spread is separate from") and unfinished:
        wnba_spread_v161.render_wnba_spread_hub(None, None, None, None)
        st.stop()
    if text.startswith("WNBA Moneyline is separate from") and unfinished:
        wnba_moneyline_v15.render_wnba_moneyline_hub(None, None, None, None)
        st.stop()
    if text.startswith("WNBA Game Total is separate from") and unfinished:
        wnba_game_total_v15.render_wnba_game_total_hub(None, None, None, None)
        st.stop()
    return _PREVIOUS_INFO(body, *args, **kwargs)


st.info = _wnba_market_route_info

# Runtime navigation boundary.
_PREVIOUS_SELECTBOX = st.selectbox
_WNBA_MARKET_OPTIONS = [
    "Points",
    "Rebounds",
    "Assists",
    "PRA",
    "Spread",
    "Moneyline",
    "Game Total",
    "Daily Picks",
]


def _wnba_market_selectbox(label, options, *args, **kwargs):
    key = str(kwargs.get("key") or "")
    label_text = str(label or "")
    is_wnba_market = key == "ks_wnba_market_touch" or "WNBA Market" in label_text
    if is_wnba_market:
        options = list(_WNBA_MARKET_OPTIONS)
    return _PREVIOUS_SELECTBOX(label, options, *args, **kwargs)


st.selectbox = _wnba_market_selectbox

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
        "kyre_sports_ai_preserved_app_plus_daily_picks_v281_controller_spread_chain_repair_assists_v20_points_v19845_pra_v361_spread_v161_moneyline_v15_game_total_v15_runtime_nav.py",
        "exec",
    ),
    globals(),
    globals(),
)
