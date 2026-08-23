'''Kyre Sports AI entrypoint — frozen MLB/WNBA + isolated NFL V1 foundation route repair.

This wrapper preserves the verified MLB/WNBA application stack and adds only an
isolated NFL V1 navigation/foundation route.

NFL V1 route repair:
- fixes the failed first bridge, which incorrectly expected an inherited app-text
  patch helper inside the immediate preserved wrapper;
- patches nested historical app.py reads instead, so the existing wrapper chain is
  allowed to resolve normally until the real touch-navigation source is reached;
- uses real newline-aware navigation markers rather than escaped literal \\n text;
- when NFL is selected, renders nfl_hub_v1 and stops before MLB/WNBA bootstrap.

MLB/WNBA model math, routing modules, Monte Carlo, ranking, qualification,
sportsbook, calibration and persistence behavior remain unchanged.
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

# Preserve all existing production compatibility aliases exactly as before.
sys.modules["hit_hub_v131"] = hit_hub_v132
sys.modules["mlb_hit_hub_v133"] = mlb_hit_hub_v1315
sys.modules["wnba_daily_picks_hub_v4"] = wnba_daily_picks_v34
sys.modules["wnba_points_hub_v19841"] = wnba_points_v19845
sys.modules["wnba_pra_hub_v321"] = wnba_pra_v3612

# Preserve the currently verified isolated WNBA market fallbacks.
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

# Preserve current WNBA market options.
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


NFL_MARKETS_SOURCE = '''    else:
        market = st.selectbox(
            "🏈 NFL Market",
            [
                "Slate",
                "Moneyline",
                "Spread",
                "Game Total",
                "Passing Yards",
                "Rushing Yards",
                "Receiving Yards",
                "Receptions",
                "Passing TDs",
                "Anytime TD",
                "Daily Picks",
            ],
            index=0,
            key="ks_nfl_market_touch",
        )
'''

NFL_ROUTE_SOURCE = '''if sport == "NFL":
    from nfl_hub_v1 import render_nfl_hub

    render_nfl_hub(market)
    st.stop()

'''


def _patch_nfl_source(value):
    """Patch only the historical touch-navigation app source when encountered."""
    is_bytes = isinstance(value, (bytes, bytearray))
    text = value.decode("utf-8") if is_bytes else str(value)

    # Idempotent: once the NFL touch route exists, never patch the source again.
    if 'key="ks_nfl_market_touch"' in text:
        return value

    # The verified historical touch-nav shell uses this exact two-sport selector.
    sport_marker = '["MLB", "WNBA"],'
    wnba_start = '''    else:
        market = st.selectbox(
            "🎯 WNBA Market",'''
    route_boundary = '''if sport == "WNBA" and market == "PRA":'''
    wnba_end = '''            key="ks_wnba_market_touch",
        )

'''

    # This is not the touch-nav layer yet; leave wrapper source completely alone.
    if sport_marker not in text or wnba_start not in text or route_boundary not in text:
        return value

    text = text.replace(sport_marker, '["MLB", "WNBA", "NFL"],', 1)
    text = text.replace(
        wnba_start,
        '''    elif sport == "WNBA":
        market = st.selectbox(
            "🎯 WNBA Market",''',
        1,
    )

    # Insert the NFL market branch immediately after the WNBA selectbox.
    boundary_pos = text.find(route_boundary)
    if boundary_pos == -1:
        return value
    prefix = text[:boundary_pos]
    suffix = text[boundary_pos:]
    last_wnba_end = prefix.rfind(wnba_end)
    if last_wnba_end == -1:
        return value
    insertion_point = last_wnba_end + len(wnba_end)
    prefix = prefix[:insertion_point] + NFL_MARKETS_SOURCE + "\n" + prefix[insertion_point:]
    text = prefix + NFL_ROUTE_SOURCE + suffix

    return text.encode("utf-8") if is_bytes else text


# Critical fix: the current production entrypoint is a chain of preserved wrappers.
# Patch every nested `git show <commit>:app.py` read until the real touch-nav shell
# appears. All non-touch-nav wrapper source passes through byte-for-byte unchanged.
_ORIGINAL_CHECK_OUTPUT = subprocess.check_output


def _nfl_nested_app_check_output(*args, **kwargs):
    result = _ORIGINAL_CHECK_OUTPUT(*args, **kwargs)
    try:
        cmd = args[0] if args else kwargs.get("args")
        if isinstance(cmd, (list, tuple)) and len(cmd) >= 3:
            if str(cmd[0]) == "git" and str(cmd[1]) == "show" and str(cmd[2]).endswith(":app.py"):
                return _patch_nfl_source(result)
    except Exception:
        pass
    return result


subprocess.check_output = _nfl_nested_app_check_output

# Load the exact pre-NFL production entrypoint. The nested interception above
# safely carries the NFL navigation patch down to the historical touch-nav shell.
PREVIOUS_APP_COMMIT = "8c9cd1b468ae84be7abc92d54a04dc09d665f9e7"
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
            # Fallback still gets the same scoped NFL patch attempt.
            return _patch_nfl_source(response.read().decode("utf-8"))


source = _load_previous_app()
exec(
    compile(
        source,
        "kyre_sports_ai_frozen_mlb_wnba_plus_nfl_v1_nested_route_repair.py",
        "exec",
    ),
    globals(),
    globals(),
)
