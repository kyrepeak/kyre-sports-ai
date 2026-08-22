'''Kyre Sports AI entrypoint — Daily Picks V34 + isolated WNBA production routes.

This cache-safe wrapper preserves the exact application at commit
6b5958d729c3999fc0188518a9dc4fb8ee63803c and applies the existing isolated WNBA
routes without changing source-model math.

Daily Picks V34 preserves the verified V31.1 checkpointed Run-All-7 master controller,
V32 Step-11 source-native finalization, V33 one-qualified-winner-per-market visual
aggregation, and the complete V21 seven-market production/verification surface.
V34 repairs only the live Standardizer-V2 -> V1.1 source-contract binding used by
Points after Streamlit hot deploys, so a native model_qualified Points row cannot
be masked by a later MONITOR LINEUP presentation state. No pick is forced.

Rebounds Steps 18-20, Assists Steps 18-20, Moneyline Step 8 and Game Total Step 8
remain owned by their existing source modules; PRA, Points and Spread retain their
existing source payload contracts. No Step-11 Monte Carlo simulation is launched,
no projection/probability math is copied or changed, and the existing Daily Picks
safety, protection, ranking and final-production guard remain authoritative.

The visual Daily Picks board shows the best source-qualified row from each connected
market and a diversified guarded overall board. Player headshots use already-loaded
player IDs with ESPN primary / WNBA fallback image URLs; team logos use ESPN. The
image layer is presentation-only and never participates in qualification or ranking.

MLB 1+ Hit is routed through Hit UI V13.2 for Step 1 visual identity only. The
existing verified MLB player_id/team_id values are used to render official MLB
batter headshots and team logos on the Top-5 cards. Hit Model V13 projection,
Monte Carlo, lineup, ranking, calibration and persistence contracts remain unchanged.

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
import hit_hub_v132 as hit_hub_v132
import wnba_daily_picks_hub_v34 as wnba_daily_picks_v34
import wnba_assists_hub_v20 as wnba_assists_v20
import wnba_points_hub_v19845 as wnba_points_v19845
import wnba_pra_hub_v361 as wnba_pra_v361
import wnba_spread_hub_v161 as wnba_spread_v161
import wnba_moneyline_hub_v15 as wnba_moneyline_v15
import wnba_game_total_hub_v15 as wnba_game_total_v15

# The preserved MLB application imports this historical Hit UI module directly.
# Rebind only that presentation route to V13.2; the wrapped V13.1 model workflow
# remains the owner of scan/model/ranking/calibration behavior.
sys.modules["hit_hub_v131"] = hit_hub_v132

# The preserved application imports this historical module name for Daily Picks.
sys.modules["wnba_daily_picks_hub_v4"] = wnba_daily_picks_v34

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
        "kyre_sports_ai_preserved_app_plus_mlb_hit_v132_visual_identity_daily_picks_v34_points_qualification_cache_repair_assists_v20_points_v19845_pra_v361_spread_v161_moneyline_v15_game_total_v15_runtime_nav.py",
        "exec",
    ),
    globals(),
    globals(),
)
