"""WNBA PRA V2.2 UI bridge with hard WNBA-only league isolation."""

import streamlit as st
import wnba_pra_hub_v2 as hub
from wnba_data_v22 import (
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

hub.current_season = current_season
hub.data_health = data_health
hub.empirical_profile = empirical_profile
hub.game_for_team = game_for_team
hub.logo_url = logo_url
hub.official_roster = official_roster
hub.player_form_table = player_form_table
hub.player_game_log = player_game_log
hub.schedule_for_date = schedule_for_date
hub.slate_player_pool = slate_player_pool
hub.team_player_pool = team_player_pool
hub.MODEL_VERSION = "PRA V2.2"


def render_wnba_pra_hub(section_header=None, status_info=None, team_logo=None, h=None):
    st.caption("🔒 WNBA league isolation active • non-WNBA team IDs are rejected before rendering.")
    return hub.render_wnba_pra_hub(section_header, status_info, team_logo, h)
