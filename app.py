'''Kyre Sports AI entrypoint — exact frozen MLB/WNBA production + frozen NFL V1.8 + isolated MLB presentation routes.

Frozen MLB/WNBA application source:
    421568e098d0c305f26584c65e6244c65bf77e62

NFL Moneyline V1.8 remains frozen. MLB Pitcher Strikeouts V1.0.17 remains the
additive headshot layer on top of the verified V1.0.16 checkpoint. MLB H+R+RBI is
now routed through V1.0.3 Steps 1-2: official MLB batter/team visual identity plus
opposing probable-starter photo and official season ERA/WHIP/K context on the
strongest-probability cards. Every underlying H+R+RBI candidate, projection,
Monte Carlo and ranking calculation remains V1.0/V1.0.1. Every other MLB/WNBA
route continues to execute from the exact frozen production source.

Streamlit hot-reload guard: the frozen application uses long compatibility-wrapper
chains for Hit and MLB Daily Game Picks. Streamlit preserves sys.modules between
reruns, so stale wrapper modules can survive a code deploy and then be reused with
an incompatible import graph. Before replaying the frozen shell, this entrypoint
restores the real Hit V13.1 base and clears cached MLB Daily Game Picks/H+R+RBI
wrapper modules so the frozen source can import them cleanly.

H+R+RBI compatibility repair: the frozen production shell intentionally aliases
`mlb_hit_hub_v133` to the final V13.15 Hit presentation wrapper. H+R+RBI V1.0
imports V13.3's `_candidate_pool` helper through that historical module name, while
V13.15 keeps the exact V13.3 scanner under its `active` binding but did not re-export
that helper. We restore only that missing compatibility symbol by pointing
V13.15 `_candidate_pool` to `V13.15.active._candidate_pool`. No candidate-pool
logic, Hit probability, H+R+RBI projection, Monte Carlo, ranking, Pitcher-K, WNBA
or NFL model math is changed.
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
# app imports mlb_pitcher_k_hub_v107; only that exact name is redirected.
import mlb_pitcher_k_hub_v1017 as mlb_pitcher_k_v1017
sys.modules["mlb_pitcher_k_hub_v107"] = mlb_pitcher_k_v1017


def _restore_real_hit_v131_for_hot_reload():
    """Repair stale Hit-UI presentation aliases left by Streamlit reruns."""
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


def _clear_mlb_hot_reload_wrappers():
    """Clear stale Daily Picks and H+R+RBI wrappers before frozen-shell replay."""
    for name in list(sys.modules):
        if name.startswith("mlb_daily_game_picks_v") or name.startswith("mlb_hrrbi_hub_v"):
            sys.modules.pop(name, None)


def _install_hrrbi_candidate_pool_compat():
    """Re-export the exact verified V13.3 candidate pool through the V13.15 alias."""
    import mlb_hit_hub_v1315 as hit_v1315

    active = getattr(hit_v1315, "active", None)
    candidate_pool = getattr(active, "_candidate_pool", None)
    if candidate_pool is None:
        raise RuntimeError(
            "H+R+RBI compatibility repair failed: verified Hit V13.3 candidate pool is unavailable."
        )
    hit_v1315._candidate_pool = candidate_pool


def _install_hrrbi_step2_route():
    """Route the frozen H+R+RBI V1.0.1 import to V1.0.3 presentation Steps 1-2."""
    import mlb_hrrbi_hub_v103 as hrrbi_v103

    sys.modules["mlb_hrrbi_hub_v101"] = hrrbi_v103


# Reset known hot-reload-sensitive import chains before every frozen-shell replay.
_restore_real_hit_v131_for_hot_reload()
_clear_mlb_hot_reload_wrappers()
_install_hrrbi_candidate_pool_compat()
_install_hrrbi_step2_route()


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
        "kyre_sports_ai_frozen_pre_nfl_plus_frozen_nfl_v18_pitcher_k_v1017_hrrbi_v103_step2_starter.py",
        "exec",
    ),
    globals(),
    globals(),
)
