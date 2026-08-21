'''Kyre Sports AI entrypoint — Daily Picks V19 + Assists V20 + Points preflight repair + PRA V3.6.1 speed route + WNBA Spread V1.6.1 + Moneyline V1.0.

This cache-safe wrapper preserves the exact application at commit
6b5958d729c3999fc0188518a9dc4fb8ee63803c and applies six isolated routes plus
one navigation-only compatibility patch:

1) WNBA Daily Picks' historical V4 import is rebound to Daily Picks V19. V19
   preserves the complete V18/V17 four-market production and verification layers,
   then appends only a read-only fifth-market Spread connector, common-schema,
   safety, cross-market ranking, Top-5 selection and final production guard.
2) The unfinished WNBA Assists fallback opens the completed Assists V20 page.
3) The preserved Points V1.9.8.4.1 import is rebound to V1.9.8.4.5. V1.9.8.4.2
   preserves full upcoming-game projection+exact-market coverage while excluding
   raw sportsbook player quotes that have no current projection. V1.9.8.4.3 then
   repairs the inherited sanity gate so a >35% Points deviation is a hard blocker
   only when the scoring-rate change is unexplained. V1.9.8.4.4 unifies the exact
   button/diagnostic readiness contract and accepts only a hardened last-3-game
   active-roster fallback when the official current-roster endpoint is unavailable,
   while restoring the strict V1.9 position matchup gate. V1.9.8.4.5 keeps that
   strict sanity rule but quarantines an unsafe player row before simulation rather
   than deadlocking every other verified distribution; full safe game coverage is
   still required after quarantine.
4) The preserved PRA V3.2.1 compatibility import is rebound to PRA V3.6.1.
   V3.6.1 preserves V3.6 model/grading/simulation math and only reuses duplicate
   Step-5 game projections + per-player variance calculations inside one render.
   The memo is reset on every Streamlit rerun; SportsGameOdds refresh is unchanged.
5) The unfinished WNBA Spread fallback opens isolated Spread V1.6.1. V1.6 keeps
   the actual 5,000,000-draw Step-7 Monte Carlo. V1.6.1 repairs only the Spread
   Step-3 cold-start availability handoff by forcing the selected Spread date into
   the verified roster pool/cache key and reconciling covered-team status with
   per-player verification. Projection/probability/Monte Carlo math is unchanged.
6) WNBA Moneyline is added to the inherited WNBA MARKET selector and its unfinished
   fallback opens isolated Moneyline V1.0. V1.0 is foundation-only: verified
   Eastern-date slate, clock-safe pregame eligibility, team context and exact-day
   current availability. Sportsbook moneyline, model win probability, fair odds,
   Monte Carlo, grading and Daily Picks remain OFF.

The selector patch is deliberately applied only to a loaded app.py source that
contains a real Streamlit selectbox. It does not rewrite wrapper source literals,
which prevents the older Daily Picks navigation patch from removing Moneyline.

No PRA projection/grading/calibration math, Rebounds, MLB, Assists production math,
Points projection math, Spread source-model math, existing Monte Carlo math, or
existing Daily Picks connector logic is modified.
'''
from __future__ import annotations

import subprocess
import sys
import urllib.request

import streamlit as st
import wnba_daily_picks_hub_v19 as wnba_daily_picks_v19
import wnba_assists_hub_v20 as wnba_assists_v20
import wnba_points_hub_v19845 as wnba_points_v19845
import wnba_pra_hub_v361 as wnba_pra_v361
import wnba_spread_hub_v161 as wnba_spread_v161
import wnba_moneyline_hub_v10 as wnba_moneyline_v10

# The preserved application imports this historical module name for Daily Picks.
sys.modules["wnba_daily_picks_hub_v4"] = wnba_daily_picks_v19

# The preserved application imports V1.9.8.4.1 directly. The new wrapper imported
# the genuine V1.9.8.4.1 module before this alias is installed, then patches only
# the live Points preflight coverage + explainable sanity + unified roster/button
# readiness + player-level sanity quarantine helpers on render.
sys.modules["wnba_points_hub_v19841"] = wnba_points_v19845

# Cache-safe PRA route: the preserved application imports this compatibility name
# before it later aliases the older V2.8.2 path. Rebinding here guarantees a
# long-lived Streamlit process cannot keep the pre-performance V3.6 object.
sys.modules["wnba_pra_hub_v321"] = wnba_pra_v361

# Preserve the existing fallback behavior while intercepting only unfinished
# WNBA pages that now have isolated production/foundation modules.
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
        wnba_moneyline_v10.render_wnba_moneyline_hub(None, None, None, None)
        st.stop()
    return _PREVIOUS_INFO(body, *args, **kwargs)


st.info = _wnba_market_route_info

# The real WNBA selector lives several preserved app.py layers below this wrapper.
# Patch only the actual shell containing a Streamlit selectbox. In particular, do
# NOT mutate the older wrapper whose source merely contains these option lists as
# string literals for its own Daily Picks compatibility transform.
_ORIGINAL_CHECK_OUTPUT = subprocess.check_output
_WNBA_MARKETS_BASE = '["Points", "Rebounds", "Assists", "PRA", "Spread", "Game Total"]'
_WNBA_MARKETS_DAILY = '["Points", "Rebounds", "Assists", "PRA", "Spread", "Game Total", "Daily Picks"]'
_WNBA_MARKETS_MONEYLINE = '["Points", "Rebounds", "Assists", "PRA", "Spread", "Moneyline", "Game Total", "Daily Picks"]'


def _inject_moneyline_selector(value):
    is_bytes = isinstance(value, (bytes, bytearray))
    text = value.decode("utf-8") if is_bytes else str(value)

    # A wrapper may contain the option-list text only as a replacement literal.
    # Requiring an actual selectbox call keeps those wrappers untouched.
    if "selectbox(" not in text or "Moneyline" in text:
        return value

    patched = text.replace(_WNBA_MARKETS_DAILY, _WNBA_MARKETS_MONEYLINE, 1)
    if patched == text:
        patched = text.replace(_WNBA_MARKETS_BASE, _WNBA_MARKETS_MONEYLINE, 1)

    return patched.encode("utf-8") if is_bytes else patched


def _moneyline_selector_check_output(*args, **kwargs):
    result = _ORIGINAL_CHECK_OUTPUT(*args, **kwargs)
    try:
        cmd = args[0] if args else kwargs.get("args")
        if isinstance(cmd, (list, tuple)) and len(cmd) >= 3:
            if str(cmd[0]) == "git" and str(cmd[1]) == "show" and str(cmd[2]).endswith(":app.py"):
                return _inject_moneyline_selector(result)
    except Exception:
        pass
    return result


# Keep this installed while the preserved app chain resolves its real UI shell.
# The older compatibility wrapper will call this function first and then apply its
# own existing Daily Picks/Points/Rebounds patches to the returned source.
subprocess.check_output = _moneyline_selector_check_output

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
        "kyre_sports_ai_preserved_app_plus_daily_picks_v19_assists_v20_points_v19845_pra_v361_spread_v161_moneyline_v10_selector_fix.py",
        "exec",
    ),
    globals(),
    globals(),
)
