'''Kyre Sports AI entrypoint — frozen MLB/WNBA + isolated NFL V1 foundation.

This cache-safe wrapper preserves the exact application at commit
6b5958d729c3999fc0188518a9dc4fb8ee63803c and applies isolated production routes
without changing existing MLB/WNBA source-model math.

MLB and WNBA remain frozen at their current production checkpoints. Existing
isolated WNBA routes remain Daily Picks V34, Assists V20, Points V1.9.8.4.5,
PRA V3.6.12, Spread V1.6.1, Moneyline V1.5 and Game Total V1.5. PRA V3.6.12
remains the frozen verified Step-5 presentation baseline.

NFL V1 adds only a third Sport navigation option and an isolated NFL Command
Center foundation route. NFL V1 has a verified ESPN NFL date/slate layer, team
identity, scores/status/venue/broadcast display and reserved market navigation.
No NFL projection, sportsbook grading, Monte Carlo, qualification, ranking or
recommendation logic is active yet. MLB/WNBA modules are not called by NFL V1.
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
import wnba_pra_hub_v3612 as wnba_pra_v3612
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

# Frozen PRA Step-5 production baseline: V3.6.11 behavior behind V3.6.12 checkpoint.
sys.modules["wnba_pra_hub_v321"] = wnba_pra_v3612

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

# Runtime WNBA market boundary remains exactly as before.
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


# NFL V1 is injected only into the inherited touch-navigation shell. This patch is
# intentionally text-scoped to the Sport/Market UI. When NFL is selected, the
# isolated nfl_hub_v1 renderer runs and st.stop() prevents any MLB/WNBA bootstrap.
def _patch_nfl_source(value):
    is_bytes = isinstance(value, (bytes, bytearray))
    text = value.decode("utf-8") if is_bytes else str(value)

    if '["MLB", "WNBA"],' in text and '["MLB", "WNBA", "NFL"],' not in text:
        text = text.replace('["MLB", "WNBA"],', '["MLB", "WNBA", "NFL"],', 1)

    wnba_branch = '''    else:\n        market = st.selectbox(\n            "🎯 WNBA Market",'''
    if wnba_branch in text and 'ks_nfl_market_touch' not in text:
        text = text.replace(
            wnba_branch,
            '''    elif sport == "WNBA":\n        market = st.selectbox(\n            "🎯 WNBA Market",''',
            1,
        )
        wnba_end = '''            key="ks_wnba_market_touch",\n        )'''
        nfl_nav = '''            key="ks_wnba_market_touch",\n        )\n    else:\n        market = st.selectbox(\n            "🏈 NFL Market",\n            [\n                "Slate",\n                "Moneyline",\n                "Spread",\n                "Game Total",\n                "Passing Yards",\n                "Rushing Yards",\n                "Receiving Yards",\n                "Receptions",\n                "Passing TDs",\n                "Anytime TD",\n                "Daily Picks",\n            ],\n            index=0,\n            key="ks_nfl_market_touch",\n        )\n\nif sport == "NFL":\n    from nfl_hub_v1 import render_nfl_hub\n    render_nfl_hub(market)\n    st.stop()'''
        if wnba_end in text:
            text = text.replace(wnba_end, nfl_nav, 1)

    return text.encode("utf-8") if is_bytes else text


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

# The preserved V6b wrapper already patches every inherited app.py text read. Add
# the isolated NFL navigation patch to that existing pipeline so it reaches the
# historical touch-nav shell without rewriting MLB/WNBA implementation code.
_inherited_return = '    return text.encode("utf-8") if is_bytes else text'
_inherited_replacement = (
    '    text = _patch_nfl_source(text)\n'
    '    return text.encode("utf-8") if is_bytes else text'
)
if _inherited_return not in source:
    raise RuntimeError("NFL V1 bridge could not locate inherited app-text patch boundary.")
source = source.replace(_inherited_return, _inherited_replacement, 1)

exec(
    compile(
        source,
        "kyre_sports_ai_frozen_mlb_wnba_plus_nfl_v1_foundation_route.py",
        "exec",
    ),
    globals(),
    globals(),
)
