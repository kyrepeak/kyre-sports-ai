'''Kyre Sports AI entrypoint — exact frozen MLB/WNBA production + isolated NFL V1.8 runtime route + isolated MLB Pitcher K V1.0.8 Step 1.

Frozen MLB/WNBA application source:
    421568e098d0c305f26584c65e6244c65bf77e62

That commit contains the last verified pre-NFL app.py plus the isolated nfl_hub_v1
file. This entrypoint does not patch historical source text, does not alter any
MLB/WNBA model module, and does not depend on nested git-show/raw-GitHub wrapper
paths.

NFL routing is handled at the live Streamlit navigation boundary:
1. while MLB/WNBA is active, only the real Sport selectbox is extended with NFL;
2. after the user selects NFL, the next Streamlit rerun is intercepted before the
   frozen MLB/WNBA app executes;
3. an isolated NFL Sport/Market navigation row and nfl_hub_v18 page are rendered;
4. selecting MLB or WNBA again returns directly to the untouched frozen app.

NFL V1.8 is the frozen Moneyline checkpoint. It preserves the verified Slate V1
foundation and Moneyline Steps 1-3.6, Step 4A historical team-strength baseline,
Step 4B matchup/home-field features, Step 4C calibrated BASE P(win), Step 5.1
sportsbook Moneyline/freshness, Step 6 5,000,000-draw model-only Monte Carlo,
Step 7 no-vig edge/fair-price/EV diagnostics, and V1.8 Final Decision grading.
During preseason, unresolved Step-3 game-plan/QB-rotation information still forces
GATED final output. No further NFL Moneyline behavior is changed here.

MLB Pitcher Strikeouts alone is compatibility-routed from the frozen historical
V1.0.7 import name to V1.0.8. V1.0.8 adds Step 1 — Verified Pitcher Slate only:
official MLB probable-starter slots plus handedness, ERA, WHIP, K/9, season Ks and
starts. Pitcher K projection math, workload/opponent-K modeling, sportsbook parsing,
line grading, Monte Carlo and rankings remain V1.0.7 behavior. Every other MLB and
WNBA route remains on the exact frozen production source.
'''
from __future__ import annotations

import subprocess
import sys
import urllib.request

import streamlit as st


FROZEN_PRE_NFL_COMMIT = "421568e098d0c305f26584c65e6244c65bf77e62"
FROZEN_RAW_URL = (
    "https://raw.githubusercontent.com/kyrepeak/kyre-sports-ai/"
    f"{FROZEN_PRE_NFL_COMMIT}/app.py"
)

NFL_MARKETS = [
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
]


_NAV_CSS = r'''
<style>
.knfl-route-note{
    display:flex;align-items:center;gap:7px;margin:2px 0 10px;padding:8px 11px;
    border:1px solid rgba(125,242,194,.23);border-radius:12px;
    color:#9ef3d0;background:rgba(34,197,94,.055);font-size:.72rem;font-weight:850;
}
div[data-testid="stSelectbox"] label p{
    color:#dbeafe !important;font-size:.78rem !important;font-weight:900 !important;
    letter-spacing:.055em !important;text-transform:uppercase !important;
}
div[data-testid="stSelectbox"] div[data-baseweb="select"] > div{
    min-height:58px !important;border-radius:15px !important;
}
@media(max-width:640px){
    div[data-testid="stSelectbox"] div[data-baseweb="select"] > div{min-height:62px !important;}
}
</style>
'''


# ---------------------------------------------------------------------------
# NFL ACTIVE ROUTE — FROZEN V1.8 CHECKPOINT
# ---------------------------------------------------------------------------
if str(st.session_state.get("ks_sport_touch") or "").upper() == "NFL":
    st.markdown(_NAV_CSS, unsafe_allow_html=True)

    nav1, nav2 = st.columns([1, 1], gap="small")
    with nav1:
        selected_sport = st.selectbox(
            "🏟️ Sport",
            ["MLB", "WNBA", "NFL"],
            key="ks_sport_touch",
        )
    with nav2:
        selected_market = st.selectbox(
            "🏈 NFL Market",
            NFL_MARKETS,
            index=0,
            key="ks_nfl_market_touch",
        )

    if str(selected_sport).upper() != "NFL":
        st.rerun()

    st.markdown(
        '<div class="knfl-route-note">🏈 NFL → isolated command center active • MLB/WNBA production paused and untouched</div>',
        unsafe_allow_html=True,
    )

    from nfl_hub_v18 import render_nfl_hub

    render_nfl_hub(selected_market)
    st.stop()


# ---------------------------------------------------------------------------
# FROZEN MLB / WNBA ROUTE
# ---------------------------------------------------------------------------
_NATIVE_SELECTBOX = st.selectbox


def _sport_selectbox_with_nfl(label, options, *args, **kwargs):
    key = str(kwargs.get("key") or "")
    label_text = str(label or "")
    is_sport_widget = key == "ks_sport_touch" or label_text.strip() == "🏟️ Sport"

    if is_sport_widget:
        try:
            values = list(options)
        except Exception:
            values = ["MLB", "WNBA"]
        if "NFL" not in values:
            values.append("NFL")
        options = values

    return _NATIVE_SELECTBOX(label, options, *args, **kwargs)


st.selectbox = _sport_selectbox_with_nfl

# Isolated MLB Pitcher Strikeouts compatibility route. The preserved historical
# application imports mlb_pitcher_k_hub_v107; only that exact module name is
# redirected to V1.0.8. No other MLB/WNBA import is changed.
import mlb_pitcher_k_hub_v108 as mlb_pitcher_k_v108
sys.modules["mlb_pitcher_k_hub_v107"] = mlb_pitcher_k_v108


def _load_frozen_pre_nfl_app() -> str:
    try:
        return subprocess.check_output(
            ["git", "show", f"{FROZEN_PRE_NFL_COMMIT}:app.py"],
            text=True,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        with urllib.request.urlopen(FROZEN_RAW_URL, timeout=15) as response:
            return response.read().decode("utf-8")


source = _load_frozen_pre_nfl_app()
compile(source, "<kyre_frozen_pre_nfl_app_preflight>", "exec")

exec(
    compile(
        source,
        "kyre_sports_ai_frozen_pre_nfl_plus_frozen_nfl_v18_plus_pitcher_k_v108_step1.py",
        "exec",
    ),
    globals(),
    globals(),
)
