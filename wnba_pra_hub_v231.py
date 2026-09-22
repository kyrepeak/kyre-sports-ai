"""WNBA PRA V2.3.1 fast-loading command-center bridge."""
from __future__ import annotations

import streamlit as st

import wnba_pra_hub_v23 as v23
from wnba_data_v231 import (
    current_season,
    data_health,
    empirical_profile,
    game_for_team,
    logo_url,
    official_roster,
    player_form_table,
    player_game_log,
    schedule_for_date,
    slate_player_pool,
    team_player_pool,
)

MODEL_VERSION = "PRA V2.3.1"

# Replace V2.3's sequential form-table request with the bounded concurrent
# transport, while preserving the existing command-center presentation.
v23.hub.current_season = current_season
v23.hub.data_health = data_health
v23.hub.empirical_profile = empirical_profile
v23.hub.game_for_team = game_for_team
v23.hub.logo_url = logo_url
v23.hub.official_roster = official_roster
v23.hub.player_form_table = player_form_table
v23.hub.player_game_log = player_game_log
v23.hub.schedule_for_date = schedule_for_date
v23.hub.slate_player_pool = slate_player_pool
v23.hub.team_player_pool = team_player_pool
v23.hub.MODEL_VERSION = MODEL_VERSION


def _hero_v231(day):
    st.markdown(
        '<div class="w2-hero">'
        '<div class="w2-kicker">KYRE SPORTS AI • WNBA PRA INTELLIGENCE</div>'
        '<div class="w2-title">🏀 WNBA PRA Command Center — V2.3.1</div>'
        '<div class="w2-sub">Fast-loading WNBA-only slate intelligence with game cards, season P/R/A, Last 10, Last 5 and a slate-wide PRA baseline scanner. Season, L10 and L5 player feeds now load in parallel so the page paints much faster on a cold cache.</div>'
        '<div class="w2-pills">'
        f'<div class="w2-pill">📅 Slate <b>{v23._e(day)}</b></div>'
        '<div class="w2-pill">🧠 <b>PRA V2.3.1</b></div>'
        '<div class="w2-pill">🔒 <b>WNBA-only data</b></div>'
        '<div class="w2-pill">⚡ <b>Parallel player feeds</b></div>'
        '</div></div>',
        unsafe_allow_html=True,
    )


v23.hub._hero = _hero_v231
v23.hub._game_card = v23._game_card
v23.hub._slate_tab = v23._slate_tab


def render_wnba_pra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.markdown(v23.EXTRA_CSS, unsafe_allow_html=True)
    st.caption("🔒 WNBA league isolation active • PRA V2.3.1 • fast parallel P/R/A form loading")
    return v23.hub.render_wnba_pra_hub(section_header, status_info, team_logo, h)
