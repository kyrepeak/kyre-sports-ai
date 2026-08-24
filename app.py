"""Kyre Sports AI entrypoint — frozen MLB/WNBA production + isolated presentation routes.

Frozen MLB/WNBA application source:
    421568e098d0c305f26584c65e6244c65bf77e62

NFL Moneyline V1.8 remains frozen. MLB Pitcher Strikeouts V1.0.17 remains the
additive headshot layer on top of the verified V1.0.16 checkpoint. MLB H+R+RBI
remains routed through V1.0.15 Steps 1-11 plus the final Top-5 evidence summary.

WNBA Points is routed through V1.9.8.4.7 at the presentation boundary. The
validated V1.9.8.4.5 projection, exact SportsGameOdds transport, 5M/10M Monte
Carlo, calibration, candidate hierarchy, persistence and readiness gates remain
unchanged. V1.9.8.4.7 now forwards to the completed Step-12 presentation stack.

WNBA Spread is routed through V1.6.2 at the historical V1.6.1 boundary. The
verified V1.6.1 exact-day availability repair, independent margin model,
SportsGameOdds spread market, analytical probability, 5M Monte Carlo,
convergence and final grading remain unchanged. V1.6.2 adds only Top-5 visual
Card Step 1 for the exact current final one-candidate-per-game payload.

WNBA Rebounds + Assists is a new isolated route through wnba_ra_hub_v1. Step 1
adds only verified slate/player identity, ESPN headshots/team logos and existing
descriptive REB+AST baselines. It does not change or import the existing
Rebounds, Assists, PRA or Points production math.

Streamlit preserves sys.modules across reruns. The frozen shell intentionally
imports historical WNBA module names, so stale wrapper objects can survive a
deploy. Before installing the active Points and Spread presentation routes, this
entrypoint clears only their respective WNBA module families and reimports each
chain from disk. The new R+A selector intercept clears only wnba_ra_* modules
before rendering its isolated page. Every unrelated market remains untouched.

Every other MLB/WNBA route continues to execute from the exact frozen production
source. Frozen NFL V1.8 is isolated from the MLB/WNBA replay.
"""
from __future__ import annotations

import importlib
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


_NAV_CSS = r"""
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
"""


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


def _render_wnba_ra_route():
    """Render only the isolated WNBA Rebounds + Assists route and stop frozen replay."""
    for name in list(sys.modules):
        if name.startswith("wnba_ra_"):
            sys.modules.pop(name, None)
    importlib.invalidate_caches()

    import wnba_ra_hub_v1 as wnba_ra_v1

    wnba_ra_v1.render_wnba_ra_hub(None, None, None, None)
    st.stop()


def _sport_selectbox_with_nfl(label, options, *args, **kwargs):
    key = str(kwargs.get("key") or "")
    label_text = str(label or "")
    is_sport_widget = key == "ks_sport_touch" or label_text.strip() == "🏟️ Sport"
    is_wnba_market_widget = key == "ks_wnba_market_touch" or "WNBA Market" in label_text

    if is_sport_widget:
        try:
            values = list(options)
        except Exception:
            values = ["MLB", "WNBA"]
        if "NFL" not in values:
            values.append("NFL")
        options = values

    if is_wnba_market_widget:
        try:
            values = list(options)
        except Exception:
            values = []
        ra_market = "Rebounds + Assists"
        if ra_market not in values:
            try:
                insert_at = values.index("Assists") + 1
            except ValueError:
                insert_at = min(3, len(values))
            values.insert(insert_at, ra_market)
        options = values

    selected = _NATIVE_SELECTBOX(label, options, *args, **kwargs)

    if is_wnba_market_widget and str(selected) == "Rebounds + Assists":
        _render_wnba_ra_route()

    return selected


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


def _install_hrrbi_final_route():
    """Route the frozen H+R+RBI V1.0.1 import to V1.0.15 final Top-5 evidence layer."""
    import mlb_hrrbi_hub_v115 as hrrbi_v115

    sys.modules["mlb_hrrbi_hub_v101"] = hrrbi_v115


def _clear_wnba_points_hot_reload_modules():
    """Remove only stale WNBA Points modules/aliases before rebuilding the chain."""
    for name in list(sys.modules):
        if name.startswith("wnba_points_hub_v") or name.startswith("wnba_points_v"):
            sys.modules.pop(name, None)
    importlib.invalidate_caches()


def _install_wnba_points_h2h_route():
    """Install V1.9.8.4.7 after a clean Points-only import-graph rebuild."""
    _clear_wnba_points_hot_reload_modules()

    import wnba_points_hub_v19847 as points_v19847

    base = getattr(points_v19847, "base", None)
    if base is None or not hasattr(base, "ui") or not hasattr(base, "v171"):
        raise RuntimeError("WNBA Points V1.9.8.4.7 compatibility base failed to initialize.")

    # The frozen pre-NFL shell imports V1.9.8.4.5 directly.
    sys.modules["wnba_points_hub_v19845"] = points_v19847


def _clear_wnba_spread_hot_reload_modules():
    """Remove only stale Spread modules before rebuilding the V1.6.2 chain."""
    for name in list(sys.modules):
        if name.startswith("wnba_spread_"):
            sys.modules.pop(name, None)
    importlib.invalidate_caches()


def _install_wnba_spread_top5_route():
    """Route the frozen V1.6.1 Spread boundary to V1.6.2 presentation only."""
    _clear_wnba_spread_hot_reload_modules()

    # V1.6.2 imports the genuine V1.6.1 module before this historical alias is
    # installed, so the exact-day availability repair remains part of its base.
    import wnba_spread_hub_v162 as spread_v162

    base = getattr(spread_v162, "base", None)
    if base is None or not hasattr(base, "_render_step7"):
        raise RuntimeError("WNBA Spread V1.6.2 compatibility base failed to initialize.")

    # The frozen pre-NFL shell imports V1.6.1 directly. Redirect only that public
    # presentation boundary; V1.6.2 retains the genuine V1.6.1 module internally.
    sys.modules["wnba_spread_hub_v161"] = spread_v162


# Reset known hot-reload-sensitive import chains before every frozen-shell replay.
_restore_real_hit_v131_for_hot_reload()
_clear_mlb_hot_reload_wrappers()
_install_hrrbi_candidate_pool_compat()
_install_hrrbi_final_route()
_install_wnba_points_h2h_route()
_install_wnba_spread_top5_route()


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
        "kyre_sports_ai_frozen_pre_nfl_plus_frozen_nfl_v18_pitcher_k_v1017_hrrbi_v115_wnba_points_v19847_spread_v162_ra_v1_hot_reload_safe.py",
        "exec",
    ),
    globals(),
    globals(),
)
