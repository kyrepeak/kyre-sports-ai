"""V19.1 live game wrapper: V19 state engine + real live sportsbook market sync."""

import pandas as pd
import streamlit as st

import live_game_hub_v19 as base
from live_odds_feed import (
    get_bookmakers,
    render_connection_setup,
    render_snapshot,
    snapshots_for_games,
)

MODEL_VERSION = "V19.1"
UI_VERSION = "LIVE UI 15.1"

_ORIGINAL_LIVE_MODEL_PANEL = base._live_model_panel
_ALLOWED_RL = [-3.5, -2.5, -1.5, -1.0, 1.0, 1.5, 2.5, 3.5]


def _nearest_run_line(value):
    try:
        value = float(value)
    except Exception:
        return None
    return min(_ALLOWED_RL, key=lambda x: abs(x - value))


def _market_sync(s, game):
    key = render_connection_setup(f"v191_{game['game_pk']}")
    if not key:
        return None

    try:
        snaps = snapshots_for_games(pd.DataFrame([game]), key, get_bookmakers())
    except Exception as exc:
        st.warning(f"Live sportsbook prices could not refresh right now: {exc}")
        return None

    snap = snaps.get(int(game["game_pk"]))
    if not snap:
        st.caption("📡 The game is live, but the selected sportsbooks are not currently returning a matching in-play market.")
        return None

    render_snapshot(snap, title="📈 Live Sportsbook Odds — ML • Run Line • Total")
    sync = st.checkbox(
        "🔄 Sync V19 run line + total to the live sportsbook market",
        value=True,
        key=f"v191_sync_{game['game_pk']}",
        help="When enabled, the settlement line used by V19 follows the current consensus line returned by your selected books.",
    )
    if not sync:
        return snap

    pk = int(game["game_pk"])
    home_line = _nearest_run_line(snap.get("home_spread"))
    total_line = snap.get("total_line")

    if home_line is not None:
        st.session_state[f"v19_rl_team_{pk}"] = s["home_team"]
        st.session_state[f"v19_rl_{pk}_{s['home_team']}"] = home_line

    current_total = float(s["away_runs"] + s["home_runs"])
    if total_line is not None and float(total_line) >= current_total + 0.5:
        st.session_state[f"v19_total_{pk}"] = float(total_line)

    return snap


def _enhanced_live_model_panel(s, game):
    if s.get("state") != "LIVE":
        return _ORIGINAL_LIVE_MODEL_PANEL(s, game)

    st.markdown(
        '<div class="lv-market-head"><div class="lv-market-title">📡 V19.1 Market Sync</div>'
        '<div class="lv-market-sub">Live MLB state updates about every 10 seconds. Sportsbook prices refresh roughly once per minute on the free-data configuration, then V19 compares its state-aware fair odds to the current market.</div></div>',
        unsafe_allow_html=True,
    )
    _market_sync(s, game)
    _ORIGINAL_LIVE_MODEL_PANEL(s, game)


# Patch V19 only once in this Python process. Its render path resolves the
# module-global function at runtime, so the upgraded panel is used everywhere.
if not getattr(base, "_v191_market_sync_installed", False):
    base._live_model_panel = _enhanced_live_model_panel
    base._v191_market_sync_installed = True


def render_live_hub(games_df, section_header, status_info, team_logo, h):
    base._inject_css()
    verified = base._verified_df(games_df)
    st.markdown(
        '<div class="lv-wrap"><div class="lv-kicker">KYRE SPORTS AI • REAL-TIME MLB • LIVE MARKET SYNC</div></div>',
        unsafe_allow_html=True,
    )
    section_header(
        "MLB Live Intelligence — V19.1",
        "Premium live game center + state-aware ML/run-line/total simulation + current sportsbook market sync.",
    )
    if verified.empty:
        st.info("No verified games are available on this selected slate.")
        return
    base._body(verified, section_header)
