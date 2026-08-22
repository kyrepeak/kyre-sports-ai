'''Kyre Sports AI entrypoint — Daily Picks V32 + isolated WNBA production routes.

This cache-safe wrapper preserves the exact application at commit
6b5958d729c3999fc0188518a9dc4fb8ee63803c and applies the existing isolated WNBA
routes without changing source-model math.

Daily Picks V32 preserves the verified V31.1 checkpointed Run-All-7 master controller
and the complete V21 seven-market production/verification surface. Step 11 adds only
post-controller source-native finalization plus a visual Daily Picks board: Rebounds
Steps 18-20, Assists Steps 18-20, Moneyline Step 8 and Game Total Step 8 remain owned
by their existing source modules; PRA, Points and Spread retain their existing source
payload contracts. No Step-11 Monte Carlo simulation is launched, no projection or
probability math is copied/changed, and the existing seven-market common-schema,
safety, protection, ranking, selection and final-production guard remain authoritative.

The visual Daily Picks board shows the best source-qualified row from each connected
market and the guarded overall Daily Picks rows. Player headshots use already-loaded
player IDs with ESPN primary / WNBA fallback image URLs; team logos use ESPN. The
image layer is presentation-only and never participates in qualification or ranking.

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
import wnba_daily_picks_hub_v32 as wnba_daily_picks_v32
import wnba_assists_hub_v20 as wnba_assists_v20
import wnba_points_hub_v19845 as wnba_points_v19845
import wnba_pra_hub_v361 as wnba_pra_v361
import wnba_spread_hub_v161 as wnba_spread_v161
import wnba_moneyline_hub_v15 as wnba_moneyline_v15
import wnba_game_total_hub_v15 as wnba_game_total_v15

# The preserved application imports this historical module name for Daily Picks.
sys.modules["wnba_daily_picks_hub_v4"] = wnba_daily_picks_v32

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
        "kyre_sports_ai_preserved_app_plus_daily_picks_v32_finalize_visual_board_assists_v20_points_v19845_pra_v361_spread_v161_moneyline_v15_game_total_v15_runtime_nav.py",
        "exec",
    ),
    globals(),
    globals(),
)
