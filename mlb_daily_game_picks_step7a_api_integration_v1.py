"""Step 7A: bind the existing Kyre Sports API feed to MLB Daily Game Picks.

Step 5.2 already owns the certified API transport and exact official MLB game-ID
join. Step 6G already owns the frozen 25% graduated-production runtime. Step 7A
does not rebuild either system: it installs Step 6G exactly as before, reads the
Step 5.2 session result created by that chain, and exposes a page-boundary
integration state.

If the API/live-market state is unavailable or inconsistent, no new UI is shown
and the page continues through the frozen Step 6 behavior.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

import mlb_daily_game_picks_live_market_context_v1 as step52
import mlb_daily_game_picks_step6g_controlled_graduation_v1 as step6g
from sports_api.mlb_step7a_daily_game_picks_api_integration_v1 import (
    evaluate_daily_game_picks_api_integration,
)

VERSION = "MLB DAILY PICKS STEP 7A • KYRE SPORTS API PAGE INTEGRATION"
_STATE_KEY = "mlb_step7a_daily_game_picks_api_integration_v1"


def install_step7a_daily_game_picks_api_integration(games_df) -> dict[str, Any]:
    """Install frozen Step 6, then advertise API integration only if proven."""
    step6_state = step6g.install_step6g_controlled_graduation_layer(games_df)
    live_state = dict(st.session_state.get(step52._STATE_KEY) or {})
    state = evaluate_daily_game_picks_api_integration(live_state, step6_state)
    st.session_state[_STATE_KEY] = state

    if state.get("api_integration_active") is True:
        count = int(state.get("attached_game_count") or 0)
        noun = "game" if count == 1 else "games"
        st.caption(
            f"⚙️ Kyre Sports API connected • FanDuel live market context • "
            f"{count} exact-ID {noun} attached • frozen Step 6 model/ranking preserved"
        )
    return state


__all__ = [
    "VERSION",
    "install_step7a_daily_game_picks_api_integration",
]
