'''Kyre Sports AI entrypoint — exact frozen MLB/WNBA production + frozen NFL V1.8 + isolated MLB Pitcher K V1.0.12 Top-5 evidence reasons.

Frozen MLB/WNBA application source:
    421568e098d0c305f26584c65e6244c65bf77e62

That commit contains the last verified pre-NFL app.py plus the isolated nfl_hub_v1
file. This entrypoint does not patch historical source text, does not alter any
unrelated MLB/WNBA model module, and does not depend on nested wrapper routes.

NFL V1.8 remains the frozen Moneyline checkpoint. It preserves the verified Slate
foundation, Steps 1-7, 5,000,000-draw Monte Carlo and Final Decision grading. No
further NFL Moneyline behavior is changed here.

MLB Pitcher Strikeouts alone is compatibility-routed from the frozen historical
V1.0.7 import name to V1.0.12. The existing Strongest Pitcher Strikeout O/U Top-5
ordering remains unchanged and probability-based. V1.0.12 preserves V1.0.11's
evidence-based Pick Strength and adds compact Supports / Concerns explanations
inside each already-ranked Top-5 card using the exact same evidence thresholds.
Projection math, sportsbook parsing, line grading, Monte Carlo, candidate pool and
Top-5 ranking remain V1.0.7 behavior. Every other MLB and WNBA route remains on
the exact frozen production source.

Hot-reload guard: the preserved MLB/WNBA shell historically aliases hit_hub_v131
to a later presentation wrapper at runtime. Streamlit keeps sys.modules alive
between reruns, so this entrypoint restores the real V13.1 base before replaying
the frozen shell and clears only the dependent Hit UI presentation modules. This
prevents stale alias recursion without changing Hit Model V13 behavior.
'''
from __future__ import annotations

import importlib.util
from pathlib import Path
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
# redirected to V1.0.12. No other MLB/WNBA import is changed.
import mlb_pitcher_k_hub_v1012 as mlb_pitcher_k_v1012
sys.modules["mlb_pitcher_k_hub_v107"] = mlb_pitcher_k_v1012


def _restore_real_hit_v131_for_hot_reload():
    """Repair only stale Hit-UI presentation aliases left by Streamlit reruns."""
    for name in list(sys.modules):
        if name == "hit_hub_v131" or name == "hit_hub_v132" or name.startswith("mlb_hit_hub_v13"):
            sys.modules.pop(name, None)

    path = Path(__file__).with_name("hit_hub_v131.py")
    spec = importlib.util.spec_from_file_location("hit_hub_v131", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not restore real hit_hub_v131 module for frozen app boot.")
    module = importlib.util.module_from_spec(spec)
    sys.modules["hit_hub_v131"] = module
    spec.loader.exec_module(module)
    if not hasattr(module, "HIT_CSS"):
        raise RuntimeError("Restored hit_hub_v131 is missing HIT_CSS.")


# The frozen shell later creates its own compatibility alias intentionally. Reset
# the real base first on every rerun so its imports always begin from a clean state.
_restore_real_hit_v131_for_hot_reload()


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
        "kyre_sports_ai_frozen_pre_nfl_plus_frozen_nfl_v18_plus_pitcher_k_v1012_top5_evidence_reasons.py",
        "exec",
    ),
    globals(),
    globals(),
)
