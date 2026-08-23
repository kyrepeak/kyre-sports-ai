'''Kyre Sports AI entrypoint — exact frozen MLB/WNBA production + isolated NFL V1.4.2 runtime route.

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
3. an isolated NFL Sport/Market navigation row and nfl_hub_v142 page are rendered;
4. selecting MLB or WNBA again returns directly to the untouched frozen app.

NFL V1.4.2 preserves the verified Slate V1 foundation and Moneyline Steps 1-3.6,
plus Step 4A's repaired historical team-strength baseline. Step 4B adds raw
opponent interaction, recent-form separation and verified home/neutral-site
features. The feature layer is transparent and intentionally does NOT expose a
calibrated win probability. Step 3 remains a final-output preseason safety gate.
Sportsbook pricing, calibrated P(win), Monte Carlo, ranking, edge/EV and
recommendations remain OFF. All other NFL markets remain reserved. MLB/WNBA
production remains frozen and untouched.
'''
from __future__ import annotations

import subprocess
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
# NFL ACTIVE ROUTE
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

    from nfl_hub_v142 import render_nfl_hub

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
        "kyre_sports_ai_frozen_pre_nfl_plus_direct_runtime_nfl_v142_moneyline_step4b_matchup_features.py",
        "exec",
    ),
    globals(),
    globals(),
)
