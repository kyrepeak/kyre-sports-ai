'''Kyre Sports AI entrypoint — Daily Picks V34 + isolated WNBA production routes.

This cache-safe wrapper preserves the exact application at commit
6b5958d729c3999fc0188518a9dc4fb8ee63803c and applies isolated production routes
without changing source-model math.

Daily Picks remains V34. Existing isolated WNBA routes remain Assists V20, Points
V1.9.8.4.5, PRA V3.6.5, Spread V1.6.1, Moneyline V1.5 and Game Total V1.5.
PRA V3.6.5 preserves the full V3.6.2/V3.6.1 production model, the Step-9 Final
Top-5 identity presentation and the V2.8 Minutes + Role Top-5 identity cards. It
adds only a verified ESPN player-ID fallback under the exact same normalized key
used by the Step-5 card renderer. Projection, qualification, Monte Carlo, ranking,
final-ready gates and selection logic are unchanged.

MLB 1+ Hit is routed through Hit UI V13.15 FINAL. Steps 1-11 retain the verified
presentation/context layers for batter/team identity, opposing starter, official
BvP history, pitch mix/platoon, park/weather/bullpen environment, PA opportunity,
recent form/contact quality, opponent run prevention/fielding, bullpen arms/
handedness pressure, starter workload/TTO and home-plate umpire/zone context.
Step 12 adds audit-only production verification: native V13 engine bindings,
V13.3 full-slate candidate-pool binding, history/calibration binding, Monte Carlo
payload/convergence, probability order, lineup labels, Steps 1-11 card presence and
proof that presentation rendering does not mutate the modeled result payload.
Step 12 performs no new simulation, reranking, calibration write or model feature
write. Hit Model V13 projection, Monte Carlo, full-slate lineup handling, ranking,
confidence, calibration and persistence remain unchanged.
'''
from __future__ import annotations

import subprocess
import sys
import urllib.request

import streamlit as st
import hit_hub_v132 as hit_hub_v132
import mlb_hit_hub_v134 as mlb_hit_hub_v134
import mlb_hit_hub_v135 as mlb_hit_hub_v135
import mlb_hit_hub_v136 as mlb_hit_hub_v136
import mlb_hit_hub_v137 as mlb_hit_hub_v137
import mlb_hit_hub_v138 as mlb_hit_hub_v138
import mlb_hit_hub_v139 as mlb_hit_hub_v139
import mlb_hit_hub_v13102 as mlb_hit_hub_v13102
import mlb_hit_hub_v1311 as mlb_hit_hub_v1311
import mlb_hit_hub_v1312 as mlb_hit_hub_v1312
import mlb_hit_hub_v1313 as mlb_hit_hub_v1313
import mlb_hit_hub_v1314 as mlb_hit_hub_v1314
import mlb_hit_hub_v1315 as mlb_hit_hub_v1315
import wnba_daily_picks_hub_v34 as wnba_daily_picks_v34
import wnba_assists_hub_v20 as wnba_assists_v20
import wnba_points_hub_v19845 as wnba_points_v19845
import wnba_pra_hub_v365 as wnba_pra_v365
import wnba_spread_hub_v161 as wnba_spread_v161
import wnba_moneyline_hub_v15 as wnba_moneyline_v15
import wnba_game_total_hub_v15 as wnba_game_total_v15

# Preserve the earlier V13.1 compatibility binding for any historical direct path.
sys.modules["hit_hub_v131"] = hit_hub_v132

# The preserved application imports V13.3. Route that historical presentation
# boundary to the completed V13.15 audit/freeze wrapper. Source-model math stays V13.
sys.modules["mlb_hit_hub_v133"] = mlb_hit_hub_v1315

# The preserved application imports this historical module name for Daily Picks.
sys.modules["wnba_daily_picks_hub_v4"] = wnba_daily_picks_v34

# The preserved application imports V1.9.8.4.1 directly. The wrapper patches only
# the live Points preflight/readiness/sanity quarantine helpers on render.
sys.modules["wnba_points_hub_v19841"] = wnba_points_v19845

# Cache-safe PRA route with normalized Step-5 identity reliability plus Final identity.
sys.modules["wnba_pra_hub_v321"] = wnba_pra_v365

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
        "kyre_sports_ai_preserved_app_plus_mlb_hit_v1315_final_audit_freeze_daily_picks_v34_points_qualification_cache_repair_assists_v20_points_v19845_pra_v365_step5_normalized_headshot_reliability_spread_v161_moneyline_v15_game_total_v15_runtime_nav.py",
        "exec",
    ),
    globals(),
    globals(),
)
