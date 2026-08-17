"""V19.2.1 hot-reload-safe market binding for the V19.2 live edge dashboard."""

import pandas as pd
import streamlit as st

import live_game_hub_v192 as base
from live_odds_feed import get_bookmakers, render_connection_setup, snapshots_for_games

MODEL_VERSION = "V19.2"


def _market_sync(s, game):
    key = render_connection_setup(f"v192_{game['game_pk']}")
    if not key:
        return None
    try:
        snaps = snapshots_for_games(pd.DataFrame([game]), key, get_bookmakers())
    except Exception as exc:
        st.warning(f"Live sportsbook prices could not refresh right now: {exc}")
        return None

    snap = snaps.get(int(game["game_pk"])) if snaps else None
    if not snap:
        st.caption("📡 No matching in-play sportsbook market is available from the selected books right now.")
        return None

    rows = snap.get("rows") or []
    age = base._freshest_age(rows)
    age_text = f"{age}s old" if age is not None else "timestamp unavailable"
    st.markdown(
        f'<div class="mk-head"><div class="mk-title">📡 Live Market Dashboard</div>'
        f'<div class="mk-sub">{get_bookmakers()} • prices refresh about once per minute on the free feed • freshest quote {age_text}</div></div>',
        unsafe_allow_html=True,
    )

    sync = st.checkbox(
        "🔄 Sync V19.2 settlement lines to current sportsbook spread + total",
        value=True,
        key=f"v192_sync_{game['game_pk']}",
    )
    if sync:
        pk = int(game["game_pk"])
        home_line = base._nearest_run_line(snap.get("home_spread"))
        total_line = snap.get("total_line")
        if home_line is not None:
            st.session_state[f"v19_rl_team_{pk}"] = s["home_team"]
            st.session_state[f"v19_rl_{pk}_{s['home_team']}"] = home_line
        current_total = float(s["away_runs"] + s["home_runs"])
        if total_line is not None and float(total_line) >= current_total + 0.5:
            st.session_state[f"v19_total_{pk}"] = float(total_line)
    return snap


# _enhanced_panel resolves this global at runtime, so patching it also handles
# Streamlit hot reloads where the older V19.1 module may still be cached.
base._market_sync = _market_sync


def render_live_hub(games_df, section_header, status_info, team_logo, h):
    return base.render_live_hub(games_df, section_header, status_info, team_logo, h)
